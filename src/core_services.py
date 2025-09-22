"""
Core services for RC Agent Phase 1 implementation.
Includes data router, validation, and constraint management.
"""

import json
import os
from typing import Dict, List, Any, Tuple, Optional, Union
from data_models import (
    ScenarioSummary, ElementMetrics, ValidationReport,
    OptimizationSpec, Constraint, OptimizationObjective
)


class DataRouter:
    """Routes data requests to appropriate Phase A or Phase B processing"""

    def __init__(self, data_dir: str = "data"):
        # Always use absolute path relative to the project root
        if not os.path.isabs(data_dir):
            # Get the project root directory (parent of src)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(script_dir)
            self.data_dir = os.path.join(project_root, data_dir)
        else:
            self.data_dir = data_dir

        self.phase_a_data: Optional[Dict[str, ScenarioSummary]] = None
        self.phase_b_data: Optional[Dict[str, Any]] = None

    def load_phase_a_data(self) -> Dict[str, ScenarioSummary]:
        """Load shop_drawings.json for Phase A (selection)"""
        if self.phase_a_data is None:
            file_path = os.path.join(self.data_dir, "shop_drawings.json")

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Phase A data file not found: {file_path}")

            with open(file_path, 'r') as f:
                data = json.load(f)

            self.phase_a_data = {}
            for rs_id, scenario_data in data.items():
                self.phase_a_data[rs_id] = ScenarioSummary.from_dict(rs_id, scenario_data)

        return self.phase_a_data

    def load_phase_b_data(self, rs_id: str) -> Dict[str, Any]:
        """Load Phase B data - supports both unified and individual solution files"""

        # Option 1: Try solution-specific file first (new two-step workflow)
        solution_file_path = os.path.join(self.data_dir, f"{rs_id}.json")
        if os.path.exists(solution_file_path):
            with open(solution_file_path, 'r') as f:
                solution_data = json.load(f)

            # If the file contains just the solution data directly
            if "by_element" in solution_data:
                return solution_data
            # If the file contains the solution wrapped in an object
            elif rs_id in solution_data:
                return solution_data[rs_id]
            else:
                # Assume the entire file is the solution data
                return solution_data

        # Option 2: Fall back to unified BIM file (original workflow)
        if self.phase_b_data is None:
            unified_file_path = os.path.join(self.data_dir, "shop_drawings_structuBIM.json")

            if not os.path.exists(unified_file_path):
                raise FileNotFoundError(
                    f"Phase B data not found. Tried:\n"
                    f"1. Solution-specific file: {solution_file_path}\n"
                    f"2. Unified BIM file: {unified_file_path}\n"
                    f"Please upload either '{rs_id}.json' or 'shop_drawings_structuBIM.json'"
                )

            with open(unified_file_path, 'r') as f:
                self.phase_b_data = json.load(f)

        if rs_id not in self.phase_b_data:
            raise ValueError(f"RS ID {rs_id} not found in unified BIM data")

        return self.phase_b_data[rs_id]

    def detect_data_type(self, data_input: Union[str, Dict]) -> str:
        """Detect whether input is Phase A or Phase B data"""
        if isinstance(data_input, str):
            # Assume it's an RS ID for Phase B
            return "phase_b"
        elif isinstance(data_input, dict):
            # Check structure to determine phase
            if "by_element" in str(data_input):
                return "phase_b"
            else:
                return "phase_a"
        return "unknown"

    def check_phase_b_availability(self, rs_id: str) -> Dict[str, Any]:
        """Check what Phase B data is available for a given solution"""
        solution_file_path = os.path.join(self.data_dir, f"{rs_id}.json")
        unified_file_path = os.path.join(self.data_dir, "shop_drawings_structuBIM.json")

        result = {
            "rs_id": rs_id,
            "solution_specific_file": {
                "path": solution_file_path,
                "exists": os.path.exists(solution_file_path),
                "filename": f"{rs_id}.json"
            },
            "unified_file": {
                "path": unified_file_path,
                "exists": os.path.exists(unified_file_path),
                "filename": "shop_drawings_structuBIM.json"
            },
            "data_available": False,
            "recommended_action": ""
        }

        # Check if solution-specific file exists
        if result["solution_specific_file"]["exists"]:
            result["data_available"] = True
            result["recommended_action"] = f"Phase B data ready: {rs_id}.json found"
            return result

        # Check if unified file exists and contains the solution
        if result["unified_file"]["exists"]:
            try:
                with open(unified_file_path, 'r') as f:
                    unified_data = json.load(f)
                if rs_id in unified_data:
                    result["data_available"] = True
                    result["recommended_action"] = f"Phase B data ready: {rs_id} found in unified file"
                else:
                    result["recommended_action"] = f"Upload {rs_id}.json to proceed with Phase 2 analysis"
            except Exception as e:
                result["recommended_action"] = f"Error reading unified file: {e}"
        else:
            result["recommended_action"] = f"Upload {rs_id}.json to proceed with Phase 2 analysis"

        return result

    def list_available_solutions(self) -> Dict[str, List[str]]:
        """List all available solutions in Phase A and Phase B data"""
        result = {
            "phase_a_solutions": [],
            "phase_b_solutions": [],
            "individual_solution_files": []
        }

        # Check Phase A solutions
        try:
            phase_a_data = self.load_phase_a_data()
            result["phase_a_solutions"] = list(phase_a_data.keys())
        except Exception:
            result["phase_a_solutions"] = []

        # Check unified Phase B file
        unified_file_path = os.path.join(self.data_dir, "shop_drawings_structuBIM.json")
        if os.path.exists(unified_file_path):
            try:
                with open(unified_file_path, 'r') as f:
                    unified_data = json.load(f)
                result["phase_b_solutions"] = list(unified_data.keys())
            except Exception:
                result["phase_b_solutions"] = []

        # Check individual solution files
        if os.path.exists(self.data_dir):
            for filename in os.listdir(self.data_dir):
                if filename.endswith('.json') and filename not in ['shop_drawings.json', 'shop_drawings_structuBIM.json']:
                    # Extract solution ID from filename
                    solution_id = filename[:-5]  # Remove .json extension
                    result["individual_solution_files"].append(solution_id)

        return result


class ConstraintManager:
    """Manages optimization constraints and objectives"""

    @staticmethod
    def parse_constraint_string(constraint_str: str) -> Constraint:
        """Parse constraint from string like 'cost <= 450000'"""
        # Simple parser for basic constraints
        operators = ['<=', '>=', '==', '<', '>', '=']

        for op in operators:
            if op in constraint_str:
                parts = constraint_str.split(op)
                if len(parts) == 2:
                    parameter = parts[0].strip().lower()
                    value = float(parts[1].strip())
                    operator = op if op != '=' else '=='
                    return Constraint(parameter, operator, value)

        raise ValueError(f"Could not parse constraint: {constraint_str}")

    @staticmethod
    def create_optimization_spec(
        primary_objective: str,
        constraints: List[str] = None,
        weights: Dict[str, float] = None
    ) -> OptimizationSpec:
        """Create optimization spec from user input"""

        # Map string objectives to enum
        objective_map = {
            "cost": OptimizationObjective.MINIMIZE_COST,
            "minimize_cost": OptimizationObjective.MINIMIZE_COST,
            "co2": OptimizationObjective.MINIMIZE_CO2,
            "minimize_co2": OptimizationObjective.MINIMIZE_CO2,
            "duration": OptimizationObjective.MINIMIZE_DURATION,
            "minimize_duration": OptimizationObjective.MINIMIZE_DURATION,
            "manhours": OptimizationObjective.MINIMIZE_MANHOURS,
            "minimize_manhours": OptimizationObjective.MINIMIZE_MANHOURS,
            "constructibility": OptimizationObjective.MAXIMIZE_CONSTRUCTIBILITY,
            "maximize_constructibility": OptimizationObjective.MAXIMIZE_CONSTRUCTIBILITY,
        }

        primary_obj = objective_map.get(primary_objective.lower())
        if not primary_obj:
            raise ValueError(f"Unknown objective: {primary_objective}")

        # Parse constraints
        constraint_objects = []
        if constraints:
            for constraint_str in constraints:
                constraint_objects.append(
                    ConstraintManager.parse_constraint_string(constraint_str)
                )

        return OptimizationSpec(
            primary_objective=primary_obj,
            constraints=constraint_objects,
            weights=weights or {}
        )


class DataValidator:
    """Validates data integrity and consistency"""

    @staticmethod
    def validate_phase_a_data(scenarios: Dict[str, ScenarioSummary]) -> ValidationReport:
        """Validate Phase A scenario data"""
        errors = []
        warnings = []

        # Check for missing data
        if not scenarios:
            errors.append("No scenario data found")
            return ValidationReport(False, errors, warnings, {})

        # Validate each scenario
        for rs_id, scenario in scenarios.items():
            # Check for negative values
            if scenario.steel_cost < 0:
                errors.append(f"{rs_id}: Steel cost cannot be negative")
            if scenario.concrete_cost < 0:
                errors.append(f"{rs_id}: Concrete cost cannot be negative")
            if scenario.manhours < 0:
                errors.append(f"{rs_id}: Manhours cannot be negative")
            if scenario.duration_days <= 0:
                errors.append(f"{rs_id}: Duration must be positive")

            # Check for reasonable ranges
            if scenario.constructibility_index < 1 or scenario.constructibility_index > 5:
                warnings.append(f"{rs_id}: Constructibility index {scenario.constructibility_index} outside typical range 1-5")

            if scenario.steel_tonnage <= 0:
                errors.append(f"{rs_id}: Steel tonnage must be positive")

        # Calculate summary statistics
        total_cost_range = (
            min(s.total_cost for s in scenarios.values()),
            max(s.total_cost for s in scenarios.values())
        )

        data_summary = {
            "total_scenarios": len(scenarios),
            "rs_ids": list(scenarios.keys()),
            "cost_range": total_cost_range,
            "avg_duration": sum(s.duration_days for s in scenarios.values()) / len(scenarios),
            "avg_co2": sum(s.co2_tonnes for s in scenarios.values()) / len(scenarios)
        }

        is_valid = len(errors) == 0

        return ValidationReport(is_valid, errors, warnings, data_summary)

    @staticmethod
    def validate_phase_b_data(bim_data: Dict[str, Any]) -> ValidationReport:
        """Validate Phase B BIM data"""
        errors = []
        warnings = []

        # Check for required structure
        if "by_element" not in bim_data:
            errors.append("BIM data missing 'by_element' structure")
            return ValidationReport(False, errors, warnings, {})

        # Count elements and analyze structure
        element_count = 0
        total_rebar_weight = 0
        complex_elements = 0

        for level_name, level_data in bim_data["by_element"].items():
            for element_id, element_data in level_data.items():
                element_count += 1

                # Check required fields
                required_fields = [
                    "bar_types", "bars_total", "complexity_score",
                    "total_rebar_weight", "vol_concreto"
                ]

                for field in required_fields:
                    if field not in element_data:
                        errors.append(f"Element {element_id}: Missing required field '{field}'")

                if "total_rebar_weight" in element_data:
                    total_rebar_weight += element_data["total_rebar_weight"]

                if "complexity_score" in element_data and element_data["complexity_score"] > 3.0:
                    complex_elements += 1

        data_summary = {
            "total_elements": element_count,
            "building_levels": list(bim_data["by_element"].keys()),
            "total_rebar_weight": total_rebar_weight,
            "complex_elements": complex_elements,
            "complexity_ratio": complex_elements / element_count if element_count > 0 else 0
        }

        is_valid = len(errors) == 0

        return ValidationReport(is_valid, errors, warnings, data_summary)


class ExplainabilityService:
    """Provides explanations for recommendations and decisions"""

    @staticmethod
    def explain_selection(
        recommended_rs: str,
        spec: OptimizationSpec,
        scenarios: Dict[str, ScenarioSummary],
        scores: List
    ) -> str:
        """Generate explanation for solution selection"""

        recommended_scenario = scenarios[recommended_rs]

        explanation = f"""
## Selection Rationale for {recommended_rs}

**Primary Objective**: {spec.primary_objective.value}

**Selected Solution Performance**:
- Total Cost: ${recommended_scenario.total_cost:,.0f}
- Duration: {recommended_scenario.duration_days} days
- CO₂ Emissions: {recommended_scenario.co2_tonnes} tonnes
- Constructibility Index: {recommended_scenario.constructibility_index:.2f}
- Manhours: {recommended_scenario.manhours:,}

**Key Decision Factors**:
1. **Objective Alignment**: This solution best meets the primary objective of {spec.primary_objective.value}
2. **Constraint Compliance**: All specified constraints are satisfied
3. **Balanced Performance**: Strong performance across multiple criteria

**Alternatives Considered**: {len(scenarios)} total solutions evaluated

**Risk Assessment**:
- Cost competitiveness: {'High' if recommended_scenario.total_cost <= min(s.total_cost for s in scenarios.values()) * 1.1 else 'Medium'}
- Schedule confidence: {'High' if recommended_scenario.duration_days <= min(s.duration_days for s in scenarios.values()) * 1.1 else 'Medium'}
- Technical complexity: {'Low' if recommended_scenario.constructibility_index >= 2.5 else 'High'}
"""

        return explanation.strip()