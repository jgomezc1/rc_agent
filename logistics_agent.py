#!/usr/bin/env python3
"""
ProDet+StructuBIM Logistics Agent

Creates high-leverage logistics intelligence and operations plans for
reinforcement construction: storage, handling, sequencing, and communication.

From fixed, engineer-approved solutions (no design edits).
Bars arrive pre-cut and bent.
"""

import os
import json
import pandas as pd
import numpy as np
from openai import OpenAI
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timedelta

# Import file generators
from file_generators import FileGenerator

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# Define tool schemas for OpenAI function calling
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "analyze_congestion",
            "description": "Analyze and identify the most congested/complex elements in specified floor range. Returns detailed data about elements including complexity scores, bar counts, and weights.",
            "parameters": {
                "type": "object",
                "properties": {
                    "floor_start": {
                        "type": "integer",
                        "description": "Starting floor number (e.g., 1 for Floor 1/PISO 2)"
                    },
                    "floor_end": {
                        "type": "integer",
                        "description": "Ending floor number (e.g., 5 for Floor 5/PISO 5)"
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Number of most congested elements to return",
                        "default": 10
                    }
                },
                "required": ["floor_start", "floor_end"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_yard_layout",
            "description": "Generate a professional 2D yard layout diagram (PDF) showing crane coverage, storage zones, aisles, and dimensions. Useful for site planning and team coordination.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Optional custom filename (without extension). If not provided, uses timestamp."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_crane_safety",
            "description": "Generate comprehensive crane safety guidelines document (PDF) with specifications, safety zones, and operational procedures. Ready for team distribution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Optional custom filename (without extension)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_unloading_schedule",
            "description": "Generate detailed truck unloading schedule (Excel) with 3 sheets: truck arrivals, unloading sequence, and summary statistics. Based on actual project data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Optional custom filename (without extension)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_zone_allocation",
            "description": "Generate zone allocation map (PDF) showing bundle-to-zone assignments with utilization metrics. Can be filtered by floor range and limited to top N most congested elements.",
            "parameters": {
                "type": "object",
                "properties": {
                    "floor_start": {
                        "type": "integer",
                        "description": "Starting floor number for filtering allocations"
                    },
                    "floor_end": {
                        "type": "integer",
                        "description": "Ending floor number for filtering allocations"
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Limit to top N most congested elements",
                        "default": 20
                    },
                    "filename": {
                        "type": "string",
                        "description": "Optional custom filename (without extension)"
                    }
                },
                "required": []
            }
        }
    }
]


@dataclass
class SiteParameters:
    """Site-specific parameters for logistics planning."""
    # Yard dimensions
    yard_width: float = 30.0  # meters
    yard_depth: float = 40.0  # meters
    no_go_zones: List[Dict] = None
    storage_surface: str = "ground"  # ground/racks/mixed

    # Crane setup
    crane_center_x: float = 15.0  # meters
    crane_center_y: float = 20.0  # meters
    crane_max_radius: float = 25.0  # meters
    crane_capacity: float = 10.0  # tonnes
    num_cranes: int = 1

    # Access & movement
    truck_gate_x: float = 0.0
    truck_gate_y: float = 0.0
    gate_time_windows: List[Tuple[str, str]] = None  # [(start, end), ...]
    aisle_width: float = 4.0  # meters
    one_way_paths: bool = False

    # Stacking rules
    max_stack_height: int = 3  # bundles
    max_stack_weight: float = 5.0  # tonnes

    # Crew & schedule
    crew_size: int = 8
    shifts_per_day: int = 1
    working_hours: Tuple[str, str] = ("07:00", "17:00")

    # Safety
    safety_buffer: float = 2.0  # meters from crane radius
    weather_sensitive: bool = True

    def __post_init__(self):
        if self.no_go_zones is None:
            self.no_go_zones = []
        if self.gate_time_windows is None:
            self.gate_time_windows = [("08:00", "16:00")]


class LogisticsAgent:
    """ProDet+StructuBIM Logistics Agent for construction operations planning."""

    def __init__(
        self,
        despiece_path: str = "data/despiece.xlsx",
        analysis_path: str = "data/processedAnalysis.json",
        site_params: Optional[SiteParameters] = None,
        api_key: Optional[str] = None
    ):
        """Initialize the logistics agent."""
        print("="*80)
        print("ProDet+StructuBIM LOGISTICS AGENT")
        print("="*80)

        # Load API key
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required")

        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o"

        # Site parameters
        self.site = site_params or SiteParameters()

        # Load data
        print("\n[1/3] Loading reinforcement solution data...")
        self.despiece_data = self._load_despiece(despiece_path)
        self.analysis_data = self._load_analysis(analysis_path)
        print("[OK] Solution data loaded")

        # Prepare logistics intelligence
        print("[2/3] Processing logistics intelligence...")
        self.logistics_summary = self._prepare_logistics_summary()
        print("[OK] Logistics intelligence ready")

        # Conversation history
        self.conversation_history = []

        # Output directory
        self.output_dir = Path("logistics_outputs")
        self.output_dir.mkdir(exist_ok=True)

        # File generator
        self.file_gen = FileGenerator(output_dir=str(self.output_dir))

        print("[3/3] Agent initialized")
        print(f"[OK] Output directory: {self.output_dir}")
        print("[OK] File generation ready")
        print("\n" + "="*80)
        print("Ready for logistics planning.")
        print("Type your request or 'help' for examples.")
        print("="*80)

    def _load_despiece(self, path: str) -> Dict[str, pd.DataFrame]:
        """Load all sheets from despiece.xlsx."""
        sheets = {}

        # Sheet 1: Summary per floor
        sheets['resumen'] = pd.read_excel(path, sheet_name='Resumen_Refuerzo', skiprows=1)

        # Sheet 2: Longitudinal bars per element
        sheets['long_elemento'] = pd.read_excel(path, sheet_name='RefLong_PorElemento', skiprows=2)

        # Sheet 3: Total longitudinal
        sheets['long_total'] = pd.read_excel(path, sheet_name='RefLong_Total', skiprows=2)

        # Sheet 4: Transverse per element
        sheets['trans_elemento'] = pd.read_excel(path, sheet_name='RefTrans_PorElemento', skiprows=2)

        # Sheet 5: Total transverse
        sheets['trans_total'] = pd.read_excel(path, sheet_name='RefTrans_Total', skiprows=2)

        return sheets

    def _load_analysis(self, path: str) -> Dict[str, Any]:
        """Load processedAnalysis.json."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Extract the solution (assumes single solution in file)
        solution_key = list(data.keys())[0]
        return data[solution_key]

    def _prepare_logistics_summary(self) -> str:
        """Prepare comprehensive logistics summary for AI context."""
        analysis = self.analysis_data

        # Overall metrics
        total_elements = analysis.get('detailed_elements', 0)
        total_bar_types = analysis.get('bar_types', 0)
        total_concrete = analysis.get('concrete_volume', 0)

        # Floor analysis
        floors = list(analysis.get('by_story', {}).keys())
        num_floors = len(floors)

        # Element complexity analysis
        complexity_scores = []
        labor_modifiers = []
        element_weights = []

        for floor_name, floor_data in analysis.get('by_element', {}).items():
            for elem_name, elem_data in floor_data.items():
                if isinstance(elem_data, dict):
                    complexity_scores.append(elem_data.get('complexity_score', 0))
                    labor_modifiers.append(elem_data.get('labor_hours_modifier', 0))
                    element_weights.append(elem_data.get('total_rebar_weight', 0))

        avg_complexity = np.mean(complexity_scores) if complexity_scores else 0
        max_complexity = max(complexity_scores) if complexity_scores else 0
        total_weight = sum(element_weights)

        # Bar diameter analysis
        bar_diameters = set()
        for floor_data in analysis.get('by_element', {}).values():
            for elem_data in floor_data.values():
                if isinstance(elem_data, dict):
                    bars_by_dia = elem_data.get('bars_by_diameter', {})
                    bar_diameters.update(bars_by_dia.keys())

        summary = f"""
REINFORCEMENT SOLUTION LOGISTICS SUMMARY
==========================================

OVERALL METRICS:
- Total structural elements: {total_elements}
- Total bar types/configurations: {total_bar_types}
- Total concrete volume: {total_concrete:.1f} m³
- Total rebar weight: {total_weight:.1f} kg
- Number of floors: {num_floors}

COMPLEXITY ANALYSIS:
- Average element complexity: {avg_complexity:.2f}
- Maximum element complexity: {max_complexity:.2f}
- Labor productivity range: {min(labor_modifiers):.2f} to {max(labor_modifiers):.2f}

BAR DIAMETERS IN USE:
{', '.join(sorted(bar_diameters))}

FLOORS (bottom to top):
{', '.join(floors)}

SITE CONSTRAINTS:
- Yard: {self.site.yard_width}m × {self.site.yard_depth}m
- Crane: center ({self.site.crane_center_x}, {self.site.crane_center_y}), radius {self.site.crane_max_radius}m
- Max stack: {self.site.max_stack_height} bundles, {self.site.max_stack_weight} tonnes
- Aisle width: {self.site.aisle_width}m
- Crew size: {self.site.crew_size} workers
- Working hours: {self.site.working_hours[0]} - {self.site.working_hours[1]}

KEY LOGISTICS PRINCIPLES:
1. NO design changes - all bars pre-cut and bent as specified
2. Contiguous construction - lower floors first unless overridden
3. Minimize handling touches
4. Optimize crane hook utilization
5. Prevent stockouts and yard saturation
6. Safety buffers: {self.site.safety_buffer}m from crane operations
"""
        return summary

    def generate_yard_layout(self, zones: List[Dict] = None, filename: str = None) -> str:
        """Generate yard layout PDF based on site parameters."""
        if zones is None:
            # Create default zones based on yard dimensions
            zones = self._create_default_zones()

        filepath = self.file_gen.generate_yard_layout_pdf(
            yard_width=self.site.yard_width,
            yard_depth=self.site.yard_depth,
            crane_x=self.site.crane_center_x,
            crane_y=self.site.crane_center_y,
            crane_radius=self.site.crane_max_radius,
            zones=zones,
            aisle_width=self.site.aisle_width,
            filename=filename
        )
        return filepath

    def generate_unloading_schedule(self, trucks: List[Dict], bundles: List[Dict], filename: str = None) -> str:
        """Generate unloading schedule Excel file."""
        filepath = self.file_gen.generate_unloading_schedule_excel(
            trucks=trucks,
            bundles=bundles,
            filename=filename
        )
        return filepath

    def generate_zone_allocation(self, zones: List[Dict], allocations: List[Dict], filename: str = None) -> str:
        """Generate zone allocation PDF."""
        filepath = self.file_gen.generate_zone_allocation_pdf(
            zones=zones,
            allocations=allocations,
            filename=filename
        )
        return filepath

    def generate_crane_safety(self, filename: str = None) -> str:
        """Generate crane safety guidelines PDF."""
        crane_params = {
            'max_radius': self.site.crane_max_radius,
            'capacity': self.site.crane_capacity,
            'center_x': self.site.crane_center_x,
            'center_y': self.site.crane_center_y,
            'safety_buffer': self.site.safety_buffer
        }

        safety_zones = [
            {
                'name': 'Exclusion Zone',
                'description': 'No personnel allowed during active lift operations',
                'restrictions': f'{self.site.safety_buffer * 2}m radius from lift point - Hard barrier required'
            },
            {
                'name': 'Restricted Access Zone',
                'description': 'Essential personnel only with full PPE and authorization',
                'restrictions': f'Within {self.site.crane_max_radius}m crane radius, outside exclusion zone'
            }
        ]

        procedures = [
            'Conduct comprehensive pre-operation inspection of crane and rigging equipment',
            'Verify load weight does not exceed rated capacity with safety factor',
            'Ensure all non-essential personnel are clear of exclusion zones',
            'Maintain continuous communication between operator and signal person',
            'Inspect all rigging before each lift - reject if damaged',
            'Never swing loads over personnel',
            'Monitor weather - cease if wind exceeds 30 km/h',
            'Implement lockout/tagout during maintenance'
        ]

        filepath = self.file_gen.generate_crane_safety_pdf(
            crane_params=crane_params,
            safety_zones=safety_zones,
            procedures=procedures,
            filename=filename
        )
        return filepath

    def _create_default_zones(self) -> List[Dict]:
        """Create default zone layout."""
        zones = []
        yard_w = self.site.yard_width
        yard_d = self.site.yard_depth
        aisle = self.site.aisle_width

        # Storage zone A (left)
        zones.append({
            'id': 'STORAGE-A',
            'x': 2,
            'y': 2,
            'width': (yard_w - aisle - 4) / 2,
            'depth': yard_d * 0.4,
            'type': 'storage',
            'max_weight': 5000
        })

        # Storage zone B (right)
        zones.append({
            'id': 'STORAGE-B',
            'x': yard_w / 2 + aisle / 2,
            'y': 2,
            'width': (yard_w - aisle - 4) / 2,
            'depth': yard_d * 0.4,
            'type': 'storage',
            'max_weight': 5000
        })

        # Main aisle
        zones.append({
            'id': 'AISLE-1',
            'x': yard_w / 2 - aisle / 2,
            'y': 2,
            'width': aisle,
            'depth': yard_d * 0.4,
            'type': 'aisle',
            'max_weight': 0
        })

        # Loading zone
        zones.append({
            'id': 'LOADING',
            'x': 2,
            'y': yard_d * 0.5,
            'width': yard_w - 4,
            'depth': yard_d * 0.25,
            'type': 'loading',
            'max_weight': 3000
        })

        # Staging zone
        zones.append({
            'id': 'STAGING',
            'x': 2,
            'y': yard_d * 0.8,
            'width': yard_w - 4,
            'depth': yard_d * 0.15,
            'type': 'staging',
            'max_weight': 2000
        })

        return zones

    def _create_sample_unloading_data(self) -> Tuple[List[Dict], List[Dict]]:
        """Create sample truck and bundle data based on actual project data."""
        # Use data from despiece to create realistic bundles
        trucks = []
        bundles = []

        # Generate 3 sample trucks
        base_time = datetime.strptime("08:00", "%H:%M")
        for i in range(3):
            truck_id = f"TRUCK-{i+1:03d}"
            arrival_time = (base_time + timedelta(hours=i*2.5)).strftime("%H:%M")
            trucks.append({
                'id': truck_id,
                'arrival_time': arrival_time,
                'capacity': 20  # tonnes
            })

        # Get some actual bundles from RefLong_Total sheet
        if hasattr(self, 'reflong_total') and not self.reflong_total.empty:
            # Take first 8 bundles from data
            sample_bundles = self.reflong_total.head(8)
            zones = ['STORAGE-A', 'STORAGE-B', 'STAGING']

            for idx, (_, row) in enumerate(sample_bundles.iterrows()):
                truck_idx = idx // 3  # Distribute across 3 trucks
                bundle_id = f"BUNDLE-{row.get('Despiece', f'B{idx+1}')}"
                weight_kg = row.get('Peso Total (kg)', 500)

                bundles.append({
                    'id': bundle_id[:20],  # Truncate long IDs
                    'truck_id': f"TRUCK-{truck_idx+1:03d}",
                    'weight': int(weight_kg),
                    'zone': zones[idx % len(zones)],
                    'unload_seq': (idx % 3) + 1,
                    'duration': max(10, int(weight_kg / 40))  # ~40kg/min unload rate
                })
        else:
            # Fallback: create generic bundles
            for i in range(8):
                truck_idx = i // 3
                bundles.append({
                    'id': f"BUNDLE-F{5+i//3}-L{i%3+1:02d}",
                    'truck_id': f"TRUCK-{truck_idx+1:03d}",
                    'weight': 450 + i * 20,
                    'zone': ['STORAGE-A', 'STORAGE-B', 'STAGING'][i % 3],
                    'unload_seq': (i % 3) + 1,
                    'duration': 12 + i
                })

        return trucks, bundles

    def _create_sample_allocations(self, top_n: int = 20, floor_range: Tuple[int, int] = None) -> List[Dict]:
        """Create zone allocations based on actual project data, prioritizing most congested elements."""
        allocations = []
        zones = ['STORAGE-A', 'STORAGE-B', 'STAGING']

        # Get actual element data from processedAnalysis.json
        by_element = self.analysis_data.get('by_element', {})

        # Collect all elements with their metrics
        all_elements = []
        for floor_name, floor_elements in by_element.items():
            # Filter by floor range if specified
            if floor_range:
                import re
                floor_num_match = re.search(r'(\d+)', floor_name)
                if floor_num_match:
                    floor_num = int(floor_num_match.group(1))
                    if not (floor_range[0] <= floor_num <= floor_range[1]):
                        continue

            for element_id, element_data in floor_elements.items():
                complexity = element_data.get('complexity_score', 0)
                longitudinal_bars = element_data.get('longitudinal_bars_total', 0)
                stirrups = element_data.get('stirrups_total', 0)
                weight = element_data.get('total_rebar_weight', 0)

                all_elements.append({
                    'floor': floor_name,
                    'element': element_id,
                    'complexity': complexity,
                    'longitudinal_bars': longitudinal_bars,
                    'stirrups': stirrups,
                    'weight': weight
                })

        # Sort by complexity (most congested first)
        all_elements.sort(key=lambda x: x['complexity'], reverse=True)

        # Take top N elements
        top_elements = all_elements[:top_n]

        # Create allocations
        for idx, elem in enumerate(top_elements):
            zone = zones[idx % len(zones)]
            bundle_id = f"{elem['floor']}-{elem['element']}"

            allocations.append({
                'zone_id': zone,
                'bundle_id': bundle_id[:30],  # Truncate if too long
                'weight': int(elem['weight']) if elem['weight'] > 0 else 500,
                'floor': elem['floor']
            })

        return allocations

    def analyze_congestion(self, floor_start: int, floor_end: int, top_n: int = 10) -> Dict[str, Any]:
        """
        Tool: Analyze and identify most congested elements in floor range.

        Args:
            floor_start: Starting floor number (1-based, maps to PISO 2+)
            floor_end: Ending floor number
            top_n: Number of top elements to return

        Returns:
            Dictionary with analysis results and top congested elements
        """
        by_element = self.analysis_data.get('by_element', {})

        # Collect elements within floor range
        elements_in_range = []
        for floor_name, floor_elements in by_element.items():
            # Extract floor number
            import re
            floor_num_match = re.search(r'(\d+)', floor_name)
            if floor_num_match:
                floor_num = int(floor_num_match.group(1))
                # Map user floor numbers (1-5) to actual PISO numbers (2-6)
                if not (floor_start <= floor_num <= floor_end):
                    continue

            for element_id, element_data in floor_elements.items():
                elements_in_range.append({
                    'floor': floor_name,
                    'element_id': element_id,
                    'complexity_score': element_data.get('complexity_score', 0),
                    'longitudinal_bars_total': element_data.get('longitudinal_bars_total', 0),
                    'stirrups_total': element_data.get('stirrups_total', 0),
                    'bars_total': element_data.get('bars_total', 0),
                    'total_rebar_weight': element_data.get('total_rebar_weight', 0),
                    'bar_types': element_data.get('bar_types', 0),
                    'labor_hours_modifier': element_data.get('labor_hours_modifier', 0)
                })

        # Sort by complexity (descending)
        elements_in_range.sort(key=lambda x: x['complexity_score'], reverse=True)

        # Get top N
        top_elements = elements_in_range[:top_n]

        # Calculate summary stats
        total_elements = len(elements_in_range)
        avg_complexity = np.mean([e['complexity_score'] for e in elements_in_range]) if elements_in_range else 0
        total_weight = sum([e['total_rebar_weight'] for e in elements_in_range])

        return {
            'floor_range': f'Floor {floor_start} to {floor_end}',
            'total_elements_in_range': total_elements,
            'average_complexity': round(avg_complexity, 2),
            'total_weight_kg': round(total_weight, 1),
            'top_congested_elements': top_elements,
            'analysis_date': datetime.now().isoformat()
        }

    def _get_detailed_elements_data(self, floors: List[str] = None) -> str:
        """Get detailed element data for specific floors."""
        analysis = self.analysis_data

        if floors is None:
            # Get all floors from by_story
            floors = list(analysis.get('by_story', {}).keys())

        detailed_data = []
        detailed_data.append("DETAILED ELEMENT DATA (by_element from processedAnalysis.json):")
        detailed_data.append("="*80)

        # by_element structure: Floor → Element → Data
        by_element = analysis.get('by_element', {})

        all_elements = []

        # Iterate through floors
        for floor_name, floor_elements in by_element.items():
            # Filter if specific floors requested
            if floors and floor_name not in floors:
                continue

            # Iterate through elements in this floor
            for element_id, element_data in floor_elements.items():
                complexity = element_data.get('complexity_score', 0)
                longitudinal_bars = element_data.get('longitudinal_bars_total', 0)
                stirrups = element_data.get('stirrups_total', 0)
                bars_total = element_data.get('bars_total', 0)
                weight = element_data.get('total_rebar_weight', 0)
                bar_types = element_data.get('bar_types', 0)
                labor_mod = element_data.get('labor_hours_modifier', 0)

                all_elements.append({
                    'floor': floor_name,
                    'element': element_id,
                    'complexity': complexity,
                    'longitudinal_bars_total': longitudinal_bars,
                    'stirrups_total': stirrups,
                    'bars_total': bars_total,
                    'weight': weight,
                    'bar_types': bar_types,
                    'labor_mod': labor_mod
                })

        # Sort by complexity (descending)
        all_elements.sort(key=lambda x: x['complexity'], reverse=True)

        # Group by floor for display
        current_floor = None
        for elem in all_elements[:50]:  # Top 50 most complex elements
            if elem['floor'] != current_floor:
                current_floor = elem['floor']
                detailed_data.append(f"\n{current_floor}:")
                detailed_data.append("-" * 80)

            detailed_data.append(
                f"  {elem['element']:15s} | "
                f"Complex: {elem['complexity']:5.2f} | "
                f"LongBars: {elem['longitudinal_bars_total']:4d} | "
                f"Stirrups: {elem['stirrups_total']:4d} | "
                f"TotalBars: {elem['bars_total']:4d} | "
                f"Weight: {elem['weight']:7.1f}kg | "
                f"Types: {elem['bar_types']:2d} | "
                f"Labor: {elem['labor_mod']:+5.2f}"
            )

        detailed_data.append("\n" + "="*80)
        detailed_data.append(f"Total elements shown: {min(50, len(all_elements))}")
        detailed_data.append(f"Sorted by complexity_score (highest first)")

        return "\n".join(detailed_data)

    def ask(self, user_prompt: str) -> str:
        """Process user request with OpenAI function calling and tool execution."""

        # Build system message
        system_message = f"""You are the ProDet+StructuBIM Logistics Agent.

You create high-leverage logistics intelligence and operations plans for reinforced concrete construction.

NON-NEGOTIABLE CONSTRAINTS:
- NO design changes - bars are pre-cut and bent, never modify geometry
- Contiguous construction - build from lower floors upward
- All optimization is logistics/sequence/space only

{self.logistics_summary}

YOUR CAPABILITIES:
1. Dynamic yard planning (2D layouts, slotting, space-time optimization)
2. Inventory forecasting (rolling demand, stockout risk, saturation curves)
3. Congestion-aware installation sequencing (rank hard installs, micro-playbooks)
4. Micro-training & task cards (element-specific, <2min read)
5. Exception handling (missing bundles, crane down, resequencing)
6. Stakeholder communications (supplier, site lead, PM briefs)
7. What-if logistics scenarios (weather, delays, crane changes)
8. Cross-project learning (capture outcomes, suggest templates)

TOOLS AVAILABLE:
You have access to the following tools via function calling:
- analyze_congestion: Identify most congested elements in a floor range
- generate_yard_layout: Create yard layout diagram PDF
- generate_crane_safety: Create crane safety guidelines PDF
- generate_unloading_schedule: Create truck unloading schedule Excel
- generate_zone_allocation: Create zone allocation map PDF with floor filtering

Use these tools whenever they would help answer the user's request.

RESPONSE GUIDELINES:
- Be operational, concise, visual
- Quantify everything: handling touches, hook utilization, stockout risk, etc.
- Be decisive - recommend one option with clear reasoning
- Use tools proactively when they add value
- If data is missing, state assumptions explicitly

Answer the user's request with actionable logistics intelligence.
"""

        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": user_prompt
        })

        # Build messages
        messages = [
            {"role": "system", "content": system_message}
        ] + self.conversation_history

        # Track tool results
        tool_results = []

        try:
            # Initial API call with function calling
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=2000
            )

            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

            # If AI wants to use tools
            if tool_calls:
                # Add AI's message to conversation
                messages.append(response_message)

                # Execute each tool call
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    print(f"\n[TOOL CALL] {function_name} with args: {function_args}")

                    # Execute the appropriate function
                    if function_name == "analyze_congestion":
                        result = self.analyze_congestion(
                            floor_start=function_args.get('floor_start'),
                            floor_end=function_args.get('floor_end'),
                            top_n=function_args.get('top_n', 10)
                        )
                        function_response = json.dumps(result)

                    elif function_name == "generate_yard_layout":
                        filepath = self.generate_yard_layout(
                            filename=function_args.get('filename')
                        )
                        function_response = json.dumps({
                            "status": "success",
                            "filepath": str(filepath),
                            "message": "Yard layout PDF generated successfully"
                        })
                        tool_results.append(f"Yard Layout: {filepath}")

                    elif function_name == "generate_crane_safety":
                        filepath = self.generate_crane_safety(
                            filename=function_args.get('filename')
                        )
                        function_response = json.dumps({
                            "status": "success",
                            "filepath": str(filepath),
                            "message": "Crane safety guidelines PDF generated successfully"
                        })
                        tool_results.append(f"Crane Safety Guidelines: {filepath}")

                    elif function_name == "generate_unloading_schedule":
                        trucks, bundles = self._create_sample_unloading_data()
                        filepath = self.generate_unloading_schedule(
                            trucks=trucks,
                            bundles=bundles,
                            filename=function_args.get('filename')
                        )
                        function_response = json.dumps({
                            "status": "success",
                            "filepath": str(filepath),
                            "message": "Unloading schedule Excel generated successfully"
                        })
                        tool_results.append(f"Unloading Schedule: {filepath}")

                    elif function_name == "generate_zone_allocation":
                        zones = self._create_default_zones()
                        floor_range = None
                        if function_args.get('floor_start') and function_args.get('floor_end'):
                            floor_range = (function_args['floor_start'], function_args['floor_end'])

                        allocations = self._create_sample_allocations(
                            top_n=function_args.get('top_n', 20),
                            floor_range=floor_range
                        )
                        filepath = self.generate_zone_allocation(
                            zones=zones,
                            allocations=allocations,
                            filename=function_args.get('filename')
                        )
                        function_response = json.dumps({
                            "status": "success",
                            "filepath": str(filepath),
                            "message": "Zone allocation PDF generated successfully",
                            "elements_allocated": len(allocations)
                        })
                        tool_results.append(f"Zone Allocation Map: {filepath}")

                    else:
                        function_response = json.dumps({
                            "status": "error",
                            "message": f"Unknown function: {function_name}"
                        })

                    # Add function response to messages
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": function_response
                    })

                # Get final response from AI after tool execution
                final_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=2000
                )

                answer = final_response.choices[0].message.content

            else:
                # No tool calls, just use the response
                answer = response_message.content

            # Add AI's final answer to history
            self.conversation_history.append({
                "role": "assistant",
                "content": answer
            })

            # Append generated files info to answer
            if tool_results:
                answer += "\n\n" + "="*60 + "\n"
                answer += "GENERATED FILES (ready to open):\n"
                answer += "="*60 + "\n"
                for result in tool_results:
                    answer += f"[OK] {result}\n"
                answer += "="*60 + "\n"
                answer += "All files saved in the logistics_outputs/ folder.\n"
                answer += "You can open them directly from there.\n"

            return answer

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return error_msg
    def run_interactive(self):
        """Run interactive chat loop."""
        print("\nSTART LOGISTICS PLANNING:")
        print("-" * 80)

        while True:
            try:
                prompt = input("\nYou: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n\nGoodbye!")
                break

            if not prompt:
                continue

            # Exit commands
            if prompt.lower() in ['quit', 'exit', 'bye']:
                print("\nGoodbye!")
                break

            # Help command
            if prompt.lower() == 'help':
                self._show_help()
                continue

            # Site command
            if prompt.lower() == 'site':
                self._show_site_params()
                continue

            # Summary command
            if prompt.lower() == 'summary':
                print("\n" + self.logistics_summary)
                continue

            # Clear history
            if prompt.lower() == 'clear':
                self.conversation_history = []
                print("\n[OK] Conversation cleared")
                continue

            # Process request
            print("\nAgent: ", end="", flush=True)
            answer = self.ask(prompt)
            print(answer)
            print("-" * 80)

    def _show_help(self):
        """Show help with example prompts."""
        print("\n" + "="*80)
        print("LOGISTICS AGENT - HELP")
        print("="*80)
        print("\nCOMMANDS:")
        print("  help     - Show this help")
        print("  site     - Show site parameters")
        print("  summary  - Show logistics summary")
        print("  clear    - Clear conversation history")
        print("  quit     - Exit")

        print("\nEXAMPLE PROMPTS:")

        print("\n1. YARD PLANNING:")
        print("  - Create an initial yard layout for tomorrow's delivery")
        print("  - Generate unloading plan for two trucks arriving at 8am")
        print("  - Show yard occupancy over the next week")

        print("\n2. INVENTORY & FORECASTING:")
        print("  - Forecast steel demand for next 5 days")
        print("  - Check stockout risk for 3/4\" bars")
        print("  - When should I order more 5/8\" bars?")

        print("\n3. INSTALLATION SEQUENCING:")
        print("  - Which elements on Floor 7 are hardest to install?")
        print("  - Create installation sequence for Floor 5")
        print("  - Generate pick list for tomorrow")

        print("\n4. TASK CARDS & TRAINING:")
        print("  - Generate task card for element V-7")
        print("  - Create installation playbook for Floor 3")
        print("  - Task cards for all Floor 12 elements in Spanish")

        print("\n5. EXCEPTION HANDLING:")
        print("  - Bundle B-112 is missing, resequence today's work")
        print("  - Crane down for 3 hours, what's the impact?")
        print("  - Weather delay until noon, adjust schedule")

        print("\n6. STAKEHOLDER COMMUNICATIONS:")
        print("  - Generate supplier brief for next week's deliveries")
        print("  - Create site lead run sheet for tomorrow")
        print("  - PM risk brief for this week")

        print("\n7. WHAT-IF SCENARIOS:")
        print("  - Compare early delivery vs on-time delivery")
        print("  - What if gate closes 10am-12pm tomorrow?")
        print("  - Scenario: use 2 cranes instead of 1")

        print("\n8. LEARNING & TEMPLATES:")
        print("  - Save this week's metrics")
        print("  - Suggest yard template for similar projects")
        print("="*80)

    def _show_site_params(self):
        """Show current site parameters."""
        print("\n" + "="*80)
        print("SITE PARAMETERS")
        print("="*80)
        print(f"\nYard: {self.site.yard_width}m × {self.site.yard_depth}m")
        print(f"Crane: ({self.site.crane_center_x}, {self.site.crane_center_y}), "
              f"radius {self.site.crane_max_radius}m, capacity {self.site.crane_capacity}t")
        print(f"Stacking: max {self.site.max_stack_height} bundles, "
              f"{self.site.max_stack_weight}t per stack")
        print(f"Aisles: {self.site.aisle_width}m width")
        print(f"Crew: {self.site.crew_size} workers, {self.site.shifts_per_day} shift(s)")
        print(f"Hours: {self.site.working_hours[0]} - {self.site.working_hours[1]}")
        print(f"Safety buffer: {self.site.safety_buffer}m")
        print("="*80)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="ProDet+StructuBIM Logistics Agent"
    )
    parser.add_argument(
        "--despiece",
        default="data/despiece.xlsx",
        help="Path to despiece.xlsx"
    )
    parser.add_argument(
        "--analysis",
        default="data/processedAnalysis.json",
        help="Path to processedAnalysis.json"
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenAI API key"
    )

    args = parser.parse_args()

    try:
        # Create agent with default site parameters
        agent = LogisticsAgent(
            despiece_path=args.despiece,
            analysis_path=args.analysis,
            api_key=args.api_key
        )

        # Run interactive mode
        agent.run_interactive()

    except Exception as e:
        print(f"\n[!] Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
