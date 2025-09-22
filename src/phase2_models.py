"""
Phase 2 data models and contracts for RC Agent execution planning.
Handles detailed BIM data structures and execution planning objects.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import json
from datetime import datetime, timedelta


class RiskLevel(Enum):
    """Risk assessment levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CrewType(Enum):
    """Types of construction crews"""
    REBAR_PLACING = "rebar_placing"
    CONCRETE_POURING = "concrete_pouring"
    FORMWORK = "formwork"
    FINISHING = "finishing"


class QualityIssueType(Enum):
    """Types of quality issues"""
    REINFORCEMENT_RATIO = "reinforcement_ratio"
    STIRRUP_SPACING = "stirrup_spacing"
    CONNECTOR_PLACEMENT = "connector_placement"
    BAR_DIAMETER = "bar_diameter"
    COVERAGE = "coverage"


class QualityStatus(Enum):
    """Quality check statuses"""
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class InsightPriority(Enum):
    """Priority levels for constructibility insights"""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class BarSpecification:
    """Detailed bar specification from BIM data"""
    diameter: str  # e.g., "3/4\"", "5/8\""
    count: int
    weight: float  # kg
    length_total: float  # meters

    @property
    def weight_per_bar(self) -> float:
        """Calculate weight per individual bar"""
        return self.weight / self.count if self.count > 0 else 0


@dataclass
class ElementDetail:
    """Detailed element information from BIM"""
    element_id: str
    level_name: str
    bar_types: int
    bars_by_diameter: Dict[str, BarSpecification]
    stirrups_by_diameter: Dict[str, BarSpecification]
    connectors_by_diameter: Dict[str, BarSpecification]
    heads_by_diameter: Dict[str, BarSpecification]

    # Geometric properties
    surface_area: float
    vol_concreto: float
    total_rebar_weight: float

    # Complexity metrics
    complexity_score: float
    complexity_modifier: float
    labor_hours_modifier: float

    @classmethod
    def from_bim_data(cls, element_id: str, level_name: str, data: Dict[str, Any]) -> 'ElementDetail':
        """Create ElementDetail from BIM JSON data"""

        def parse_diameter_data(diameter_dict: Dict[str, Dict[str, Union[int, float]]]) -> Dict[str, BarSpecification]:
            """Parse diameter data into BarSpecification objects"""
            specs = {}
            for diameter, values in diameter_dict.items():
                if values.get('n', 0) > 0:  # Only include diameters with actual bars
                    specs[diameter] = BarSpecification(
                        diameter=diameter,
                        count=values['n'],
                        weight=values['w'],
                        length_total=values['w'] / cls._get_weight_per_meter(diameter)
                    )
            return specs

        return cls(
            element_id=element_id,
            level_name=level_name,
            bar_types=data.get('bar_types', 0),
            bars_by_diameter=parse_diameter_data(data.get('bars_by_diameter', {})),
            stirrups_by_diameter=parse_diameter_data(data.get('stirrups_by_diameter', {})),
            connectors_by_diameter=parse_diameter_data(data.get('connectors_by_diameter', {})),
            heads_by_diameter=parse_diameter_data(data.get('heads_by_diameter', {})),
            surface_area=data.get('surface_area', 0.0),
            vol_concreto=data.get('vol_concreto', 0.0),
            total_rebar_weight=data.get('total_rebar_weight', 0.0),
            complexity_score=data.get('complexity_score', 0.0),
            complexity_modifier=data.get('complexity_modifier', 1.0),
            labor_hours_modifier=data.get('labor_hours_modifier', 0.0)
        )

    @staticmethod
    def _get_weight_per_meter(diameter: str) -> float:
        """Get approximate weight per meter for rebar diameter"""
        # Standard rebar weights (kg/m) - approximate values
        weights = {
            "3/8\"": 0.56,
            "1/2\"": 0.99,
            "5/8\"": 1.55,
            "3/4\"": 2.24,
            "7/8\"": 3.04,
            "1\"": 3.96
        }
        return weights.get(diameter, 2.0)  # Default fallback


@dataclass
class ElementRisk:
    """Risk assessment for construction element"""
    element_id: str
    level_name: str
    risk_level: RiskLevel
    risk_score: float  # 0-1 scale
    risk_factors: List[str]
    mitigation_suggestions: List[str]
    estimated_delay_days: float
    probability_of_issues: float  # 0-1 scale


@dataclass
class CrewRequirement:
    """Crew requirement for an element or phase"""
    crew_type: CrewType
    crew_size: int
    estimated_hours: float
    skill_level: str  # "junior", "intermediate", "senior"
    equipment_needed: List[str]


@dataclass
class ConstructionTask:
    """Individual construction task"""
    task_id: str
    element_id: str
    level_name: str
    task_name: str
    duration_hours: float
    crew_requirements: List[CrewRequirement]
    predecessors: List[str]  # Task IDs that must complete first
    material_requirements: Dict[str, float]  # material_type -> quantity


@dataclass
class ProcurementItem:
    """Material procurement item"""
    material_type: str
    specification: str  # e.g., "3/4\" rebar"
    quantity_needed: float
    unit: str  # "kg", "pieces", "m"
    delivery_date: datetime
    lead_time_days: int
    supplier: Optional[str] = None
    cost_per_unit: Optional[float] = None


@dataclass
class QualityCheck:
    """Quality control check"""
    check_id: str
    element_id: str
    check_type: QualityIssueType
    description: str
    status: str  # "pending", "passed", "failed"
    severity: RiskLevel
    inspector: Optional[str] = None
    check_date: Optional[datetime] = None
    resolution: Optional[str] = None


@dataclass
class ExecutionPlan:
    """Complete execution plan for a solution"""
    rs_id: str
    plan_date: datetime

    # Element analysis
    elements: List[ElementDetail]
    risk_assessment: List[ElementRisk]

    # Scheduling
    construction_tasks: List[ConstructionTask]
    critical_path: List[str]  # Task IDs
    total_duration_days: float

    # Resources
    crew_plan: Dict[str, List[CrewRequirement]]  # level_name -> crew requirements
    procurement_plan: List[ProcurementItem]

    # Quality
    quality_checks: List[QualityCheck]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "rs_id": self.rs_id,
            "plan_date": self.plan_date.isoformat(),
            "total_elements": len(self.elements),
            "high_risk_elements": len([r for r in self.risk_assessment if r.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]]),
            "total_tasks": len(self.construction_tasks),
            "critical_path_tasks": len(self.critical_path),
            "total_duration_days": self.total_duration_days,
            "procurement_items": len(self.procurement_plan),
            "quality_checks": len(self.quality_checks)
        }


@dataclass
class ConstructibilityInsight:
    """Constructibility improvement suggestion"""
    insight_id: str
    category: str  # "simplification", "standardization", "staging"
    title: str
    description: str
    elements_affected: List[str]
    potential_savings: Dict[str, float]  # "cost", "time", "complexity"
    implementation_effort: str  # "low", "medium", "high"
    priority: int  # 1-5 scale


@dataclass
class SICUpdate:
    """Short Interval Control update"""
    update_id: str
    date: datetime

    # Progress tracking
    completed_tasks: List[str]
    delayed_tasks: List[str]
    upcoming_tasks: List[str]

    # Resource status
    crew_utilization: Dict[str, float]  # crew_type -> utilization %
    material_status: Dict[str, str]  # material -> status

    # Adjustments
    schedule_adjustments: List[str]
    resource_reallocations: List[str]
    procurement_updates: List[str]

    # Metrics
    schedule_variance_days: float
    cost_variance_percent: float
    quality_issues_count: int


@dataclass
class Phase2Report:
    """Comprehensive Phase 2 execution report"""
    report_id: str
    rs_id: str
    report_date: datetime
    report_type: str  # "risk_assessment", "crew_plan", "procurement", "qa_qc", "constructibility"

    # Summary metrics
    summary: Dict[str, Any]

    # Detailed sections
    sections: Dict[str, Any]

    # Recommendations
    recommendations: List[str]
    action_items: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "report_id": self.report_id,
            "rs_id": self.rs_id,
            "report_date": self.report_date.isoformat(),
            "report_type": self.report_type,
            "summary": self.summary,
            "sections": self.sections,
            "recommendations": self.recommendations,
            "action_items": self.action_items
        }