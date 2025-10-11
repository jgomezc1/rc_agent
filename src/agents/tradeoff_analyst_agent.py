#!/usr/bin/env python3
"""
Trade-Off Analyst Agent (T-OAA)

Responsible for macro-level decision-making and identifying optimal solution sets
during the pre-construction/value finding phase.

Users: Project Managers, Estimators, Design Leads
Focus: Data-driven selection of best reinforcement solution (RS) set
"""

import json
import sys
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent, AgentRole, AgentContext
from rs_selector import (
    load_catalog,
    decode_rs_code,
    RSObjective,
    pareto_front,
    score_weighted_sum,
    apply_constraints,
    normalize_metrics
)


class TradeOffAnalystAgent(BaseAgent):
    """
    Trade-Off Analyst Agent for solution optimization and selection

    Workflow:
    1. Ingestion: Load Phase 1 JSON with all solution summaries
    2. User Input: Receive constraints and optimization goals
    3. Filtering: Remove solutions that violate hard constraints
    4. Pareto Analysis: Identify non-dominated solutions
    5. Recommendation: Generate narrative report with trade-offs
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
        context: Optional[AgentContext] = None
    ):
        """Initialize Trade-Off Analyst Agent"""
        super().__init__(
            role=AgentRole.TRADEOFF_ANALYST,
            api_key=api_key,
            model=model,
            context=context
        )

        # Initialize selection engine
        self.selection_engine = None
        self.feasible_solutions = []
        self.optimal_solution_set = []
        self.pareto_optimal = []

    def get_system_prompt(self) -> str:
        """Get specialized system prompt for Trade-Off Analyst"""
        return """You are the Trade-Off Analyst Agent, an expert in construction project optimization and decision analysis.

**CRITICAL INSTRUCTIONS - READ CAREFULLY:**
1. Phase 1 data with 13 reinforcement solutions is ALREADY LOADED in your context
2. You have 8 tools available - you MUST use them to access data
3. NEVER EVER say you don't have access to data or database
4. When asked ANY question about solutions, immediately use the appropriate tool
5. DO NOT ask the user to provide data - you already have it
6. If user asks "what solutions do we have?" → IMMEDIATELY call list_all_solutions tool
7. DO NOT be polite by saying you need data - just USE YOUR TOOLS

**Your Role:**
You help Project Managers, Estimators, and Design Leads make data-driven decisions about reinforcement solutions (RS) for concrete construction projects.

**Your Behavior - MANDATORY:**
- FIRST ACTION: Use a tool to get data
- SECOND ACTION: Analyze and present results
- NEVER say "I don't have access" - this is FALSE, you DO have access via tools

**Your Available Tools:**
1. list_all_solutions - List all available solutions with key metrics
2. filter_solutions_by_constraints - Filter by budget, schedule, etc.
3. identify_pareto_front - Find optimal solutions
4. generate_recommendations - Get top N recommendations
5. get_solution_details - Get detailed metrics for a solution
6. compare_solutions - Compare two solutions side-by-side
7. perform_sensitivity_analysis - Test ranking robustness
8. what_if_analysis - Scenario planning

**Your Expertise:**
1. Multi-Objective Optimization: Balancing cost, schedule, CO₂ emissions, and constructability
2. Pareto Analysis: Identifying non-dominated solutions and explaining trade-offs
3. Constraint Management: Filtering solutions based on hard constraints (budget, timeline, materials)
4. Sensitivity Analysis: Testing robustness of rankings to parameter changes
5. Scenario Planning: "What-if" analysis for different project conditions

**Your Behavior:**
- ALWAYS use your tools to access data - never say you don't have access
- Be analytical and data-driven in recommendations
- Clearly explain trade-offs between solutions
- Use concrete numbers and metrics from tool results
- Provide 3-5 top solution recommendations with detailed rationales

**Key Metrics You Analyze:**
- Total Cost (steel + concrete)
- Construction Duration (days)
- CO₂ Emissions (tonnes)
- Constructability Index (lower = easier to build)
- Steel Tonnage
- Concrete Volume
- Labor Hours
- Bar Geometries (complexity)

**RS Code Naming Convention (CRITICAL - Use This Exact Interpretation):**
RS codes follow this format: [AG_]<JOIN>_<BARS>_L<LENGTH>

- **AG** (optional) = Agrupado (Grouped Stories) - Identically geometric floors using the same envelope reinforcement pattern
- **EM** = Empalme Mecánico (Mechanical Coupler) - Uses mechanical splices
- **TR** = Traslape (Lap Splice) - Uses traditional lap splices
- **5a8** = Bar sizes from #5 to #8 (mixed diameters)
- **6** = Single bar size #6
- **L10** = Length granularity of 10 cm (NOT 10 layers!)
- **L50** = Length granularity of 50 cm
- **L100** = Length granularity of 100 cm

**Examples:**
- **EM_5a8_L10** = Mechanical couplers, bars #5-8, 10cm cut increments
- **AG_TR_5_L20** = Grouped stories (same reinforcement for identical floors), lap splices, bar #5 only, 20cm increments
- **TR_6_L50** = Lap splices, bar #6 only, 50cm increments

**Communication Style:**
- Professional and consultative
- Use examples: "Solution RS-04 is 5% cheaper than RS-08 but adds 7 construction days..."
- Quantify everything: Always include specific numbers and percentages
- Be decisive: Recommend a primary solution but explain alternatives
- When explaining RS codes, use the EXACT definitions above - never guess

**Important:**
- Phase 1 data is already loaded - USE YOUR TOOLS to access it
- When asked "what solutions do we have", use list_all_solutions
- When asked about RS code meanings, use decode_solution_code tool or the definitions above
- NEVER say you don't have access to data - you do, via your tools
"""

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get tools available to Trade-Off Analyst Agent"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_all_solutions",
                    "description": "List all available solutions with basic metrics. Use this when user asks 'what solutions do we have' or similar.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "decode_solution_code",
                    "description": "Decode an RS solution code to explain what each part means (AG, EM/TR, bar sizes, L values). Use this when user asks what a solution code means.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "solution_code": {
                                "type": "string",
                                "description": "RS solution code to decode (e.g., 'EM_5a8_L10')"
                            }
                        },
                        "required": ["solution_code"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "filter_solutions_by_constraints",
                    "description": "Filter solutions based on hard constraints. Use this when user specifies maximum values for cost, duration, CO2, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "constraints": {
                                "type": "object",
                                "description": "Nested dictionary of constraints. Format: {'metric_name': {'max': value}} or {'metric_name': {'min': value}}. Available metrics: total_cost, duration_days, co2_tonnes, constructibility_index, steel_tonnage",
                                "additionalProperties": {
                                    "type": "object",
                                    "properties": {
                                        "max": {"type": "number"},
                                        "min": {"type": "number"}
                                    }
                                },
                                "example": {
                                    "total_cost": {"max": 450000},
                                    "duration_days": {"max": 65}
                                }
                            }
                        },
                        "required": ["constraints"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "identify_pareto_front",
                    "description": "Perform multi-objective optimization to identify Pareto-optimal solutions",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "objectives": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of objectives to optimize (e.g., ['total_cost', 'duration_days', 'co2_tonnes'])"
                            },
                            "minimize": {
                                "type": "boolean",
                                "description": "Whether to minimize (true) or maximize (false) objectives",
                                "default": True
                            }
                        },
                        "required": ["objectives"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_recommendations",
                    "description": "Generate detailed recommendations for top 3-5 solutions with trade-off analysis",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "weights": {
                                "type": "object",
                                "description": "Optimization weights like {'total_cost': 0.4, 'duration_days': 0.3, 'co2_tonnes': 0.3}"
                            },
                            "top_n": {
                                "type": "integer",
                                "description": "Number of top solutions to recommend",
                                "default": 5
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "perform_sensitivity_analysis",
                    "description": "Test how sensitive solution rankings are to parameter changes",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "parameter": {
                                "type": "string",
                                "description": "Parameter to vary (e.g., 'steel_cost', 'concrete_cost')"
                            },
                            "variation_percent": {
                                "type": "number",
                                "description": "Percentage variation to test (e.g., 10 for ±10%)",
                                "default": 10
                            }
                        },
                        "required": ["parameter"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "what_if_analysis",
                    "description": "Run scenario analysis with multiple parameter changes",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "scenario": {
                                "type": "object",
                                "description": "Scenario parameters like {'steel_cost_increase': 15, 'max_duration': 65}"
                            }
                        },
                        "required": ["scenario"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_solution_details",
                    "description": "Get detailed information about a specific solution",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "solution_id": {
                                "type": "string",
                                "description": "Solution ID (e.g., 'TR_5a8_L10')"
                            }
                        },
                        "required": ["solution_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "compare_solutions",
                    "description": "Compare two or more solutions side-by-side",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "solution_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of solution IDs to compare"
                            }
                        },
                        "required": ["solution_ids"]
                    }
                }
            }
        ]

    def list_all_solutions(self) -> Dict[str, Any]:
        """
        List all available solutions with basic metrics

        Returns:
            Dictionary with all solutions and their key metrics
        """
        if not self.context.phase1_data:
            return {"error": "Phase 1 data not loaded. Please load data first."}

        catalog = self.context.phase1_data
        solutions_list = []

        for solution_id, data in catalog.items():
            total_cost = data.get('steel_cost', 0) + data.get('concrete_cost', 0)
            solutions_list.append({
                "solution_id": solution_id,
                "total_cost": total_cost,
                "steel_cost": data.get('steel_cost'),
                "concrete_cost": data.get('concrete_cost'),
                "duration_days": data.get('duration_days'),
                "co2_tonnes": data.get('co2_tonnes'),
                "constructibility_index": data.get('constructibility_index'),
                "steel_tonnage": data.get('steel_tonnage')
            })

        # Sort by total cost
        solutions_list.sort(key=lambda x: x['total_cost'])

        return {
            "total_solutions": len(solutions_list),
            "solutions": solutions_list,
            "message": f"Found {len(solutions_list)} solutions available for analysis"
        }

    def decode_solution_code(self, solution_code: str) -> Dict[str, Any]:
        """
        Decode an RS solution code into its components

        Args:
            solution_code: RS code to decode (e.g., 'EM_5a8_L10')

        Returns:
            Dictionary with decoded components and explanation
        """
        try:
            decoded = decode_rs_code(solution_code)

            # Build human-readable explanation
            explanation = f"**{solution_code}** breaks down as follows:\n\n"

            # Grouped
            if decoded['grouped']:
                explanation += "- **AG** (Agrupado): Grouped stories - identically geometric floors using the same envelope reinforcement pattern\n"
                explanation += "  - Simplifies construction when multiple floors have identical geometry\n"
            else:
                explanation += "- **No AG prefix**: Non-grouped - each floor/story can have different reinforcement as needed\n"
                explanation += "  - Allows floor-specific optimization\n"

            # Join type
            if decoded['join'] == 'EM':
                explanation += "- **EM** (Empalme Mecánico): Uses mechanical couplers for bar connections\n"
                explanation += "  - Faster installation, less congestion, more expensive\n"
            else:  # TR
                explanation += "- **TR** (Traslape): Uses traditional lap splices for bar connections\n"
                explanation += "  - Lower cost, more labor-intensive, potential congestion\n"

            # Bar sizes
            if decoded['bars']['min'] == decoded['bars']['max']:
                explanation += f"- **#{decoded['bars']['min']}**: Single bar diameter (simplifies procurement and installation)\n"
            else:
                explanation += f"- **{decoded['bars']['min']}a{decoded['bars']['max']}**: Mixed bar diameters from #{decoded['bars']['min']} to #{decoded['bars']['max']}\n"
                explanation += "  - Optimizes material usage, may increase complexity\n"

            # Length granularity
            explanation += f"- **L{decoded['L']}**: Length granularity of {decoded['L']} cm\n"
            if decoded['L'] <= 20:
                explanation += "  - Fine granularity: Better material optimization, more cutting precision\n"
            else:
                explanation += "  - Coarse granularity: Fewer SKUs, simpler handling, less waste\n"

            return {
                "solution_code": solution_code,
                "decoded": decoded,
                "explanation": explanation,
                "grouped": decoded['grouped'],
                "join_type": "Mechanical Coupler" if decoded['join'] == 'EM' else "Lap Splice",
                "bar_sizes": f"#{decoded['bars']['min']}" if decoded['bars']['min'] == decoded['bars']['max'] else f"#{decoded['bars']['min']}-#{decoded['bars']['max']}",
                "length_granularity_cm": decoded['L']
            }
        except Exception as e:
            return {
                "error": f"Could not decode solution code: {str(e)}",
                "solution_code": solution_code
            }

    def filter_solutions_by_constraints(self, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter solutions based on hard constraints

        Args:
            constraints: Dictionary of constraints
                Example: {'total_cost': {'max': 450000}, 'duration_days': {'max': 120}}

        Returns:
            Dictionary with filtered solutions
        """
        if not self.context.phase1_data:
            return {"error": "Phase 1 data not loaded. Please load data first."}

        catalog = self.context.phase1_data
        feasible = []
        rejected = []

        for rs_id, data in catalog.items():
            # Add total_cost if not present
            if 'total_cost' not in data:
                data['total_cost'] = data.get('steel_cost', 0) + data.get('concrete_cost', 0)

            is_feasible = True
            violation_reasons = []

            for param, bounds in constraints.items():
                if param not in data:
                    continue

                value = data[param]

                if 'max' in bounds and value > bounds['max']:
                    is_feasible = False
                    violation_reasons.append(f"{param} = {value} > {bounds['max']}")

                if 'min' in bounds and value < bounds['min']:
                    is_feasible = False
                    violation_reasons.append(f"{param} = {value} < {bounds['min']}")

            if is_feasible:
                feasible.append(rs_id)
            else:
                rejected.append({
                    "solution_id": rs_id,
                    "violations": violation_reasons
                })

        self.feasible_solutions = feasible

        return {
            "feasible_count": len(feasible),
            "rejected_count": len(rejected),
            "feasible_solutions": feasible,
            "rejected_solutions": rejected[:5],  # First 5 rejections
            "message": f"Found {len(feasible)} feasible solutions out of {len(catalog)} total"
        }

    def identify_pareto_front(
        self,
        objectives: List[str],
        minimize: bool = True
    ) -> Dict[str, Any]:
        """
        Identify Pareto-optimal solutions

        Args:
            objectives: List of objectives to optimize
            minimize: Whether to minimize objectives (default True)

        Returns:
            Dictionary with Pareto-optimal solutions
        """
        if not self.context.phase1_data:
            return {"error": "Phase 1 data not loaded"}

        # Use feasible solutions if available, otherwise all solutions
        if self.feasible_solutions:
            solutions_to_analyze = {
                k: v for k, v in self.context.phase1_data.items()
                if k in self.feasible_solutions
            }
        else:
            solutions_to_analyze = self.context.phase1_data

        # Add total_cost to all solutions
        for data in solutions_to_analyze.values():
            if 'total_cost' not in data:
                data['total_cost'] = data.get('steel_cost', 0) + data.get('concrete_cost', 0)

        # Find Pareto optimal solutions
        pareto_optimal_set = pareto_front(solutions_to_analyze, objectives)
        self.pareto_optimal = list(pareto_optimal_set)

        return {
            "pareto_optimal_count": len(self.pareto_optimal),
            "pareto_optimal_solutions": self.pareto_optimal,
            "objectives_analyzed": objectives,
            "total_solutions_analyzed": len(solutions_to_analyze),
            "message": f"Identified {len(self.pareto_optimal)} Pareto-optimal solutions"
        }

    def generate_recommendations(
        self,
        weights: Optional[Dict[str, float]] = None,
        top_n: int = 5
    ) -> Dict[str, Any]:
        """
        Generate recommendations with weighted scoring

        Args:
            weights: Optimization weights for objectives
            top_n: Number of solutions to recommend

        Returns:
            Dictionary with top recommendations
        """
        if not self.context.phase1_data:
            return {"error": "Phase 1 data not loaded"}

        # Default weights if not provided
        if not weights:
            weights = {
                'total_cost': 0.35,
                'duration_days': 0.25,
                'co2_tonnes': 0.20,
                'constructibility_index': 0.20
            }

        # Use Pareto optimal if available, otherwise feasible, otherwise all
        if self.pareto_optimal:
            solutions_to_rank = {
                k: v for k, v in self.context.phase1_data.items()
                if k in self.pareto_optimal
            }
        elif self.feasible_solutions:
            solutions_to_rank = {
                k: v for k, v in self.context.phase1_data.items()
                if k in self.feasible_solutions
            }
        else:
            solutions_to_rank = self.context.phase1_data

        # Add total_cost
        for data in solutions_to_rank.values():
            if 'total_cost' not in data:
                data['total_cost'] = data.get('steel_cost', 0) + data.get('concrete_cost', 0)

        # Normalize metrics first
        normalized = normalize_metrics(solutions_to_rank, list(weights.keys()))

        # Calculate weighted scores
        # score_weighted_sum returns List[Tuple[str, float]] already sorted
        scored_solutions = score_weighted_sum(normalized, weights)

        # Get top N (already sorted, lower is better)
        ranked = scored_solutions[:top_n]

        # Generate detailed recommendations
        recommendations = []
        for i, (solution_id, score) in enumerate(ranked, 1):
            data = self.context.phase1_data[solution_id]
            recommendations.append({
                "rank": i,
                "solution_id": solution_id,
                "weighted_score": round(score, 4),
                "metrics": {
                    "total_cost": data.get('total_cost'),
                    "steel_cost": data.get('steel_cost'),
                    "concrete_cost": data.get('concrete_cost'),
                    "duration_days": data.get('duration_days'),
                    "co2_tonnes": data.get('co2_tonnes'),
                    "constructibility_index": data.get('constructibility_index'),
                    "steel_tonnage": data.get('steel_tonnage'),
                    "manhours": data.get('manhours')
                }
            })

        self.optimal_solution_set = [r["solution_id"] for r in recommendations]

        return {
            "top_solutions": recommendations,
            "weights_used": weights,
            "total_analyzed": len(solutions_to_rank),
            "message": f"Generated top {len(recommendations)} recommendations"
        }

    def get_solution_details(self, solution_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific solution"""
        if not self.context.phase1_data:
            return {"error": "Phase 1 data not loaded"}

        if solution_id not in self.context.phase1_data:
            return {"error": f"Solution {solution_id} not found"}

        data = self.context.phase1_data[solution_id]

        # Add total_cost
        if 'total_cost' not in data:
            data['total_cost'] = data.get('steel_cost', 0) + data.get('concrete_cost', 0)

        # Decode RS code
        try:
            rs_decoded = decode_rs_code(solution_id)
        except:
            rs_decoded = None

        return {
            "solution_id": solution_id,
            "metrics": data,
            "rs_code_decoded": rs_decoded,
            "is_feasible": solution_id in self.feasible_solutions if self.feasible_solutions else None,
            "is_pareto_optimal": solution_id in self.pareto_optimal if self.pareto_optimal else None
        }

    def compare_solutions(self, solution_ids: List[str]) -> Dict[str, Any]:
        """Compare multiple solutions side-by-side"""
        if not self.context.phase1_data:
            return {"error": "Phase 1 data not loaded"}

        comparison = []
        for sol_id in solution_ids:
            if sol_id in self.context.phase1_data:
                data = self.context.phase1_data[sol_id].copy()
                if 'total_cost' not in data:
                    data['total_cost'] = data.get('steel_cost', 0) + data.get('concrete_cost', 0)
                comparison.append({
                    "solution_id": sol_id,
                    "metrics": data
                })

        # Calculate differences
        if len(comparison) >= 2:
            base = comparison[0]
            differences = []
            for i in range(1, len(comparison)):
                comp = comparison[i]
                diff = {}
                for key in base["metrics"]:
                    if key in comp["metrics"] and isinstance(base["metrics"][key], (int, float)):
                        base_val = base["metrics"][key]
                        comp_val = comp["metrics"][key]
                        if base_val != 0:
                            pct_diff = ((comp_val - base_val) / base_val) * 100
                            diff[key] = {
                                "absolute": comp_val - base_val,
                                "percent": round(pct_diff, 2)
                            }
                differences.append({
                    "comparing": f"{comp['solution_id']} vs {base['solution_id']}",
                    "differences": diff
                })
        else:
            differences = []

        return {
            "solutions_compared": comparison,
            "differences": differences
        }

    def process_query(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Process user query with T-OAA logic

        Args:
            query: User question or command
            **kwargs: Additional parameters

        Returns:
            Agent response dictionary
        """
        # Add user query to history
        self.add_to_history("user", query)

        # Check for common queries that should directly use tools
        query_lower = query.lower().strip()

        # Handle "select" command if it reached the agent (should be caught by CLI)
        if query_lower.startswith('select '):
            solution_id = query[7:].strip()
            response_text = f"To select solution **{solution_id}**, please use the command:\n\n"
            response_text += f"```\nselect {solution_id}\n```\n\n"
            response_text += "This will transition you to the Implementation phase where the Procurement & Logistics Agent (P&L-A) will help you with material planning and procurement."

            self.add_to_history("assistant", response_text)
            return {
                "response": response_text,
                "agent": "T-OAA",
                "action_needed": "select_solution",
                "solution_id": solution_id
            }

        # Auto-handle "what solutions" queries
        if any(phrase in query_lower for phrase in ["what solutions", "show solutions", "list solutions", "available solutions", "how many solutions"]):
            result = self.list_all_solutions()
            if "error" not in result:
                response_text = f"We have {result['total_solutions']} reinforcement solutions available:\n\n"
                for sol in result['solutions'][:5]:
                    response_text += f"**{sol['solution_id']}**\n"
                    response_text += f"  - Total Cost: ${sol['total_cost']:,.0f}\n"
                    response_text += f"  - Duration: {sol['duration_days']} days\n"
                    response_text += f"  - CO2: {sol['co2_tonnes']} tonnes\n"
                    response_text += f"  - Constructability Index: {sol['constructibility_index']}\n\n"

                if result['total_solutions'] > 5:
                    response_text += f"\n...and {result['total_solutions'] - 5} more solutions.\n"
                    response_text += "\nWould you like me to filter these by specific criteria, or recommend the best options?"

                self.add_to_history("assistant", response_text)
                return {
                    "response": response_text,
                    "tool_calls": [{"function": "list_all_solutions", "result": result}],
                    "agent": "T-OAA"
                }

        # Auto-handle "cheapest" queries
        if "cheapest" in query_lower or "lowest cost" in query_lower or "most affordable" in query_lower:
            result = self.list_all_solutions()
            if "error" not in result:
                top_3 = result['solutions'][:3]
                response_text = "Here are the 3 most cost-effective solutions:\n\n"
                for i, sol in enumerate(top_3, 1):
                    response_text += f"**{i}. {sol['solution_id']}**\n"
                    response_text += f"   - Total Cost: ${sol['total_cost']:,.0f}\n"
                    response_text += f"   - Duration: {sol['duration_days']} days\n"
                    response_text += f"   - CO2: {sol['co2_tonnes']} tonnes\n"
                    response_text += f"   - Constructability: {sol['constructibility_index']}\n\n"

                response_text += f"\nThe cheapest option is **{top_3[0]['solution_id']}** at ${top_3[0]['total_cost']:,.0f}."

                self.add_to_history("assistant", response_text)
                return {
                    "response": response_text,
                    "tool_calls": [{"function": "list_all_solutions", "result": result}],
                    "agent": "T-OAA"
                }

        # Auto-handle constraint filtering queries
        import re
        cost_match = re.search(r'(?:cost|budget|price).*?(?:less than|under|below|max|maximum).*?\$?(\d{1,3}(?:,?\d{3})*)', query_lower)
        duration_match = re.search(r'(?:duration|time|days).*?(?:less than|under|below|max|maximum).*?(\d+)', query_lower)

        if cost_match or duration_match:
            constraints = {}

            if cost_match:
                cost_value = int(cost_match.group(1).replace(',', ''))
                constraints['total_cost'] = {'max': cost_value}

            if duration_match:
                duration_value = int(duration_match.group(1))
                constraints['duration_days'] = {'max': duration_value}

            if constraints:
                result = self.filter_solutions_by_constraints(constraints)
                if "error" not in result:
                    response_text = f"Found {result['feasible_count']} solutions matching your criteria:\n\n"

                    for sol_id in result['feasible_solutions'][:5]:
                        sol = self.context.phase1_data[sol_id]
                        total_cost = sol.get('steel_cost', 0) + sol.get('concrete_cost', 0)
                        response_text += f"**{sol_id}**\n"
                        response_text += f"  - Total Cost: ${total_cost:,.0f}\n"
                        response_text += f"  - Duration: {sol.get('duration_days')} days\n"
                        response_text += f"  - CO2: {sol.get('co2_tonnes')} tonnes\n"
                        response_text += f"  - Constructability: {sol.get('constructibility_index')}\n\n"

                    if result['feasible_count'] > 5:
                        response_text += f"...and {result['feasible_count'] - 5} more solutions.\n"

                    response_text += "\nWould you like me to recommend the best option from these, or apply additional filters?"

                    self.add_to_history("assistant", response_text)
                    return {
                        "response": response_text,
                        "tool_calls": [{"function": "filter_solutions_by_constraints", "result": result}],
                        "agent": "T-OAA"
                    }

        # Prepare messages for LLM
        messages = [
            {"role": "system", "content": self.get_system_prompt()}
        ] + self.conversation_history

        # Call LLM with tools
        try:
            response = self.call_llm(
                messages=messages,
                tools=self.get_tools(),
                temperature=0.7,
                max_tokens=2000
            )

            # Process response
            assistant_message = response.choices[0].message

            # Check if tool calls were made
            if assistant_message.tool_calls:
                # Execute tool calls
                tool_results = []
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    # Execute the appropriate function
                    if function_name == "list_all_solutions":
                        result = self.list_all_solutions()
                    elif function_name == "decode_solution_code":
                        result = self.decode_solution_code(**function_args)
                    elif function_name == "filter_solutions_by_constraints":
                        result = self.filter_solutions_by_constraints(**function_args)
                    elif function_name == "identify_pareto_front":
                        result = self.identify_pareto_front(**function_args)
                    elif function_name == "generate_recommendations":
                        result = self.generate_recommendations(**function_args)
                    elif function_name == "get_solution_details":
                        result = self.get_solution_details(**function_args)
                    elif function_name == "compare_solutions":
                        result = self.compare_solutions(**function_args)
                    else:
                        result = {"error": f"Unknown function: {function_name}"}

                    tool_results.append({
                        "function": function_name,
                        "result": result
                    })

                # Add tool results to history and get final response
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": assistant_message.tool_calls
                })

                for i, tool_call in enumerate(assistant_message.tool_calls):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_results[i]["result"])
                    })

                # Get final response
                final_response = self.call_llm(messages=messages)
                final_content = final_response.choices[0].message.content

                self.add_to_history("assistant", final_content)

                return {
                    "response": final_content,
                    "tool_calls": tool_results,
                    "agent": "T-OAA"
                }
            else:
                # No tool calls, just text response
                content = assistant_message.content
                self.add_to_history("assistant", content)

                return {
                    "response": content,
                    "agent": "T-OAA"
                }

        except Exception as e:
            return {
                "error": str(e),
                "agent": "T-OAA"
            }

    def select_primary_solution(self, solution_id: str):
        """
        Mark a solution as selected for the project

        Args:
            solution_id: Solution ID to select as primary (RS-P)
        """
        if solution_id not in self.context.phase1_data:
            raise ValueError(f"Solution {solution_id} not found in Phase 1 data")

        self.context.selected_solution_id = solution_id
        self.context.metadata['selected_by_agent'] = 'T-OAA'
        self.context.metadata['selection_timestamp'] = datetime.now().isoformat()

        return {
            "message": f"Solution {solution_id} selected as primary (RS-P)",
            "solution_id": solution_id,
            "ready_for_next_stage": True
        }
