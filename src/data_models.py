"""
Core data models and contracts for RC Agent Phase 1 implementation.
Defines the data structures for optimization specs, scenario summaries, and results.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import json


class OptimizationObjective(Enum):
    """Supported optimization objectives"""
    MINIMIZE_COST = "minimize_cost"
    MINIMIZE_CO2 = "minimize_co2"
    MINIMIZE_DURATION = "minimize_duration"
    MINIMIZE_MANHOURS = "minimize_manhours"
    MAXIMIZE_CONSTRUCTIBILITY = "maximize_constructibility"


@dataclass
class Constraint:
    """Represents a single constraint"""
    parameter: str
    operator: str  # <=, >=, ==, <, >
    value: float
    unit: Optional[str] = None


@dataclass
class OptimizationSpec:
    """Specification for multi-objective optimization"""
    primary_objective: OptimizationObjective
    secondary_objectives: List[OptimizationObjective] = field(default_factory=list)
    constraints: List[Constraint] = field(default_factory=list)
    weights: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        """Set default weights if not provided"""
        if not self.weights:
            self.weights = {
                "cost": 0.4,
                "co2": 0.3,
                "duration": 0.2,
                "constructibility": 0.1
            }


@dataclass
class ScenarioSummary:
    """Data contract for shop_drawings.json scenarios"""
    rs_id: str
    steel_tonnage: float
    concrete_volume: float
    steel_cost: float
    concrete_cost: float
    manhours: int
    duration_days: int
    co2_tonnes: float
    constructibility_index: float
    bar_geometries: int

    @property
    def total_cost(self) -> float:
        """Calculate total cost"""
        return self.steel_cost + self.concrete_cost

    @classmethod
    def from_dict(cls, rs_id: str, data: Dict[str, Any]) -> 'ScenarioSummary':
        """Create from dictionary data"""
        return cls(
            rs_id=rs_id,
            steel_tonnage=data['steel_tonnage'],
            concrete_volume=data['concrete_volume'],
            steel_cost=data['steel_cost'],
            concrete_cost=data['concrete_cost'],
            manhours=data['manhours'],
            duration_days=data['duration_days'],
            co2_tonnes=data['co2_tonnes'],
            constructibility_index=data['constructibility_index'],
            bar_geometries=data['bar_geometries']
        )


@dataclass
class ElementMetrics:
    """Data contract for shop_drawings_structuBIM.json element details"""
    element_id: str
    bar_types: int
    bars_by_diameter: Dict[str, Dict[str, Union[int, float]]]
    bars_total: int
    complexity_score: float
    labor_hours_modifier: float
    total_rebar_weight: float
    vol_concreto: float
    surface_area: float

    @classmethod
    def from_dict(cls, element_id: str, data: Dict[str, Any]) -> 'ElementMetrics':
        """Create from dictionary data"""
        return cls(
            element_id=element_id,
            bar_types=data['bar_types'],
            bars_by_diameter=data['bars_by_diameter'],
            bars_total=data['bars_total'],
            complexity_score=data['complexity_score'],
            labor_hours_modifier=data['labor_hours_modifier'],
            total_rebar_weight=data['total_rebar_weight'],
            vol_concreto=data['vol_concreto'],
            surface_area=data['surface_area']
        )


@dataclass
class SolutionScore:
    """Scoring result for a single solution"""
    rs_id: str
    total_score: float
    objective_scores: Dict[str, float]
    constraint_violations: List[str]
    is_feasible: bool
    rank: Optional[int] = None


@dataclass
class SelectionResult:
    """Result of solution selection process"""
    recommended_solution: str
    all_scores: List[SolutionScore]
    pareto_optimal: List[str]
    rationale: str
    constraints_summary: str
    alternatives: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "recommended_solution": self.recommended_solution,
            "all_scores": [
                {
                    "rs_id": score.rs_id,
                    "total_score": score.total_score,
                    "objective_scores": score.objective_scores,
                    "constraint_violations": score.constraint_violations,
                    "is_feasible": score.is_feasible,
                    "rank": score.rank
                }
                for score in self.all_scores
            ],
            "pareto_optimal": self.pareto_optimal,
            "rationale": self.rationale,
            "constraints_summary": self.constraints_summary,
            "alternatives": self.alternatives
        }


@dataclass
class ValidationReport:
    """Data validation report"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    data_summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "data_summary": self.data_summary
        }


@dataclass
class SensitivityResult:
    """Result of sensitivity analysis"""
    parameter: str
    base_value: float
    shock_percentage: float
    original_ranking: List[str]
    new_ranking: List[str]
    ranking_changes: Dict[str, int]  # rs_id -> rank_change
    impact_score: float  # 0-1, how much the ranking changed

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "parameter": self.parameter,
            "base_value": self.base_value,
            "shock_percentage": self.shock_percentage,
            "original_ranking": self.original_ranking,
            "new_ranking": self.new_ranking,
            "ranking_changes": self.ranking_changes,
            "impact_score": self.impact_score
        }