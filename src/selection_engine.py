"""
Multi-objective selection engine for RC Agent Phase 1.
Implements selection algorithms, Pareto analysis, and sensitivity testing.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from data_models import (
    ScenarioSummary, OptimizationSpec, OptimizationObjective,
    SolutionScore, SelectionResult, SensitivityResult, Constraint
)


class SelectionEngine:
    """Multi-objective optimization and selection engine"""

    def __init__(self):
        self.scenarios: Dict[str, ScenarioSummary] = {}

    def load_scenarios(self, scenarios: Dict[str, ScenarioSummary]) -> None:
        """Load scenario data for optimization"""
        self.scenarios = scenarios

    def evaluate_constraints(self, scenario: ScenarioSummary, constraints: List[Constraint]) -> Tuple[bool, List[str]]:
        """Evaluate if scenario meets all constraints"""
        violations = []

        for constraint in constraints:
            # Map constraint parameter to scenario attribute
            value = self._get_scenario_value(scenario, constraint.parameter)

            if value is None:
                violations.append(f"Unknown parameter: {constraint.parameter}")
                continue

            # Evaluate constraint
            if constraint.operator == "<=":
                if not (value <= constraint.value):
                    violations.append(f"{constraint.parameter} {value} > {constraint.value}")
            elif constraint.operator == ">=":
                if not (value >= constraint.value):
                    violations.append(f"{constraint.parameter} {value} < {constraint.value}")
            elif constraint.operator == "==":
                if not (abs(value - constraint.value) < 1e-6):
                    violations.append(f"{constraint.parameter} {value} != {constraint.value}")
            elif constraint.operator == "<":
                if not (value < constraint.value):
                    violations.append(f"{constraint.parameter} {value} >= {constraint.value}")
            elif constraint.operator == ">":
                if not (value > constraint.value):
                    violations.append(f"{constraint.parameter} {value} <= {constraint.value}")

        return len(violations) == 0, violations

    def _get_scenario_value(self, scenario: ScenarioSummary, parameter: str) -> Optional[float]:
        """Get value from scenario based on parameter name"""
        parameter_map = {
            "cost": scenario.total_cost,
            "total_cost": scenario.total_cost,
            "steel_cost": scenario.steel_cost,
            "concrete_cost": scenario.concrete_cost,
            "co2": scenario.co2_tonnes,
            "co2_tonnes": scenario.co2_tonnes,
            "duration": scenario.duration_days,
            "duration_days": scenario.duration_days,
            "manhours": scenario.manhours,
            "constructibility": scenario.constructibility_index,
            "constructibility_index": scenario.constructibility_index,
            "steel_tonnage": scenario.steel_tonnage,
            "concrete_volume": scenario.concrete_volume,
            "bar_geometries": scenario.bar_geometries
        }
        return parameter_map.get(parameter.lower())

    def calculate_objective_scores(self, spec: OptimizationSpec) -> Dict[str, SolutionScore]:
        """Calculate scores for all scenarios based on optimization spec"""
        scores = {}

        # Get all feasible scenarios first
        feasible_scenarios = {}
        for rs_id, scenario in self.scenarios.items():
            is_feasible, violations = self.evaluate_constraints(scenario, spec.constraints)
            if is_feasible:
                feasible_scenarios[rs_id] = scenario

        if not feasible_scenarios:
            # If no feasible solutions, include all with violations noted
            feasible_scenarios = self.scenarios

        # Normalize values for scoring (0-1 scale)
        normalized_values = self._normalize_values(feasible_scenarios)

        # Calculate weighted scores
        for rs_id, scenario in feasible_scenarios.items():
            is_feasible, violations = self.evaluate_constraints(scenario, spec.constraints)

            # Calculate objective scores
            objective_scores = {}

            # Cost objective (minimize)
            if normalized_values["cost"]:
                cost_score = 1 - normalized_values["cost"][rs_id]  # Lower cost = higher score
                objective_scores["cost"] = cost_score

            # CO2 objective (minimize)
            if normalized_values["co2"]:
                co2_score = 1 - normalized_values["co2"][rs_id]  # Lower CO2 = higher score
                objective_scores["co2"] = co2_score

            # Duration objective (minimize)
            if normalized_values["duration"]:
                duration_score = 1 - normalized_values["duration"][rs_id]  # Lower duration = higher score
                objective_scores["duration"] = duration_score

            # Manhours objective (minimize)
            if normalized_values["manhours"]:
                manhours_score = 1 - normalized_values["manhours"][rs_id]  # Lower manhours = higher score
                objective_scores["manhours"] = manhours_score

            # Constructibility objective (maximize)
            if normalized_values["constructibility"]:
                constructibility_score = normalized_values["constructibility"][rs_id]  # Higher CI = higher score
                objective_scores["constructibility"] = constructibility_score

            # Calculate weighted total score
            total_score = 0
            for metric, weight in spec.weights.items():
                if metric in objective_scores:
                    total_score += weight * objective_scores[metric]

            # Apply penalty for constraint violations
            if not is_feasible:
                total_score *= 0.5  # Penalize infeasible solutions

            scores[rs_id] = SolutionScore(
                rs_id=rs_id,
                total_score=total_score,
                objective_scores=objective_scores,
                constraint_violations=violations,
                is_feasible=is_feasible
            )

        return scores

    def _normalize_values(self, scenarios: Dict[str, ScenarioSummary]) -> Dict[str, Dict[str, float]]:
        """Normalize scenario values to 0-1 scale for scoring"""
        if not scenarios:
            return {}

        normalized = {}

        # Extract values for normalization
        costs = [s.total_cost for s in scenarios.values()]
        co2_values = [s.co2_tonnes for s in scenarios.values()]
        durations = [s.duration_days for s in scenarios.values()]
        manhours = [s.manhours for s in scenarios.values()]
        constructibility = [s.constructibility_index for s in scenarios.values()]

        # Normalize each metric
        normalized["cost"] = self._normalize_list(costs, list(scenarios.keys()))
        normalized["co2"] = self._normalize_list(co2_values, list(scenarios.keys()))
        normalized["duration"] = self._normalize_list(durations, list(scenarios.keys()))
        normalized["manhours"] = self._normalize_list(manhours, list(scenarios.keys()))
        normalized["constructibility"] = self._normalize_list(constructibility, list(scenarios.keys()))

        return normalized

    def _normalize_list(self, values: List[float], rs_ids: List[str]) -> Dict[str, float]:
        """Normalize a list of values to 0-1 scale"""
        if not values or len(set(values)) == 1:
            return {rs_id: 0.5 for rs_id in rs_ids}  # All equal values

        min_val = min(values)
        max_val = max(values)
        range_val = max_val - min_val

        return {
            rs_id: (value - min_val) / range_val
            for rs_id, value in zip(rs_ids, values)
        }

    def find_pareto_optimal(self, scores: Dict[str, SolutionScore]) -> List[str]:
        """Find Pareto-optimal solutions"""
        feasible_scores = {rs_id: score for rs_id, score in scores.items() if score.is_feasible}

        if not feasible_scores:
            return []

        pareto_optimal = []

        for rs_id1, score1 in feasible_scores.items():
            is_dominated = False

            for rs_id2, score2 in feasible_scores.items():
                if rs_id1 == rs_id2:
                    continue

                # Check if score2 dominates score1
                # (score2 is better in all objectives or equal in all and better in at least one)
                dominates = True
                strictly_better_in_one = False

                for objective in score1.objective_scores:
                    if objective in score2.objective_scores:
                        if score2.objective_scores[objective] < score1.objective_scores[objective]:
                            dominates = False
                            break
                        elif score2.objective_scores[objective] > score1.objective_scores[objective]:
                            strictly_better_in_one = True

                if dominates and strictly_better_in_one:
                    is_dominated = True
                    break

            if not is_dominated:
                pareto_optimal.append(rs_id1)

        return pareto_optimal

    def select_solution(self, spec: OptimizationSpec) -> SelectionResult:
        """Main selection method - returns best solution with full analysis"""
        if not self.scenarios:
            raise ValueError("No scenarios loaded")

        # Calculate scores
        scores = self.calculate_objective_scores(spec)

        # Rank solutions
        ranked_scores = sorted(scores.values(), key=lambda x: x.total_score, reverse=True)
        for i, score in enumerate(ranked_scores):
            score.rank = i + 1

        # Find Pareto optimal
        pareto_optimal = self.find_pareto_optimal(scores)

        # Select best solution (highest total score among feasible)
        feasible_scores = [s for s in ranked_scores if s.is_feasible]
        if not feasible_scores:
            # If no feasible solutions, take best overall
            recommended_rs = ranked_scores[0].rs_id
        else:
            recommended_rs = feasible_scores[0].rs_id

        # Generate rationale
        from core_services import ExplainabilityService
        rationale = ExplainabilityService.explain_selection(
            recommended_rs, spec, self.scenarios, ranked_scores
        )

        # Create constraints summary
        constraints_summary = f"Applied {len(spec.constraints)} constraints" if spec.constraints else "No constraints applied"

        # Get alternatives (top 3 other feasible solutions)
        alternatives = [s.rs_id for s in feasible_scores[1:4] if s.rs_id != recommended_rs]

        return SelectionResult(
            recommended_solution=recommended_rs,
            all_scores=ranked_scores,
            pareto_optimal=pareto_optimal,
            rationale=rationale,
            constraints_summary=constraints_summary,
            alternatives=alternatives
        )


class SensitivityAnalyzer:
    """Performs sensitivity analysis on optimization results"""

    def __init__(self, selection_engine: SelectionEngine):
        self.engine = selection_engine

    def analyze_parameter_sensitivity(
        self,
        spec: OptimizationSpec,
        parameter: str,
        shock_percentage: float = 0.1
    ) -> SensitivityResult:
        """Analyze sensitivity to changes in a specific parameter"""

        # Get original ranking
        original_result = self.engine.select_solution(spec)
        original_ranking = [score.rs_id for score in original_result.all_scores if score.is_feasible]

        if not original_ranking:
            raise ValueError("No feasible solutions in original analysis")

        # Create modified scenarios
        modified_scenarios = {}
        base_value = None

        for rs_id, scenario in self.engine.scenarios.items():
            base_param_value = self.engine._get_scenario_value(scenario, parameter)

            if base_param_value is None:
                raise ValueError(f"Unknown parameter: {parameter}")

            if base_value is None:
                base_value = base_param_value

            # Apply shock
            shocked_value = base_param_value * (1 + shock_percentage)

            # Create modified scenario
            modified_scenario = self._modify_scenario_parameter(scenario, parameter, shocked_value)
            modified_scenarios[rs_id] = modified_scenario

        # Temporarily replace scenarios and re-analyze
        original_scenarios = self.engine.scenarios
        self.engine.scenarios = modified_scenarios

        try:
            # Get new ranking
            new_result = self.engine.select_solution(spec)
            new_ranking = [score.rs_id for score in new_result.all_scores if score.is_feasible]

            # Calculate ranking changes
            ranking_changes = {}
            for rs_id in original_ranking:
                if rs_id in new_ranking:
                    old_rank = original_ranking.index(rs_id)
                    new_rank = new_ranking.index(rs_id)
                    ranking_changes[rs_id] = new_rank - old_rank

            # Calculate impact score (how much ranking changed)
            if len(ranking_changes) > 0:
                max_possible_change = len(original_ranking) - 1
                actual_changes = [abs(change) for change in ranking_changes.values()]
                impact_score = sum(actual_changes) / (len(actual_changes) * max_possible_change)
            else:
                impact_score = 0.0

        finally:
            # Restore original scenarios
            self.engine.scenarios = original_scenarios

        return SensitivityResult(
            parameter=parameter,
            base_value=base_value,
            shock_percentage=shock_percentage,
            original_ranking=original_ranking,
            new_ranking=new_ranking,
            ranking_changes=ranking_changes,
            impact_score=impact_score
        )

    def _modify_scenario_parameter(self, scenario: ScenarioSummary, parameter: str, new_value: float) -> ScenarioSummary:
        """Create a new scenario with modified parameter value"""
        # Create a copy and modify the specific parameter
        scenario_dict = {
            'steel_tonnage': scenario.steel_tonnage,
            'concrete_volume': scenario.concrete_volume,
            'steel_cost': scenario.steel_cost,
            'concrete_cost': scenario.concrete_cost,
            'manhours': scenario.manhours,
            'duration_days': scenario.duration_days,
            'co2_tonnes': scenario.co2_tonnes,
            'constructibility_index': scenario.constructibility_index,
            'bar_geometries': scenario.bar_geometries
        }

        # Map parameter to the correct field
        param_map = {
            'steel_cost': 'steel_cost',
            'concrete_cost': 'concrete_cost',
            'cost': 'steel_cost',  # For total cost, modify steel cost as proxy
            'total_cost': 'steel_cost',
            'co2': 'co2_tonnes',
            'co2_tonnes': 'co2_tonnes',
            'duration': 'duration_days',
            'duration_days': 'duration_days',
            'manhours': 'manhours',
            'constructibility': 'constructibility_index',
            'constructibility_index': 'constructibility_index',
            'steel_tonnage': 'steel_tonnage',
            'concrete_volume': 'concrete_volume',
            'bar_geometries': 'bar_geometries'
        }

        field = param_map.get(parameter.lower())
        if field:
            scenario_dict[field] = new_value

        return ScenarioSummary.from_dict(scenario.rs_id, scenario_dict)