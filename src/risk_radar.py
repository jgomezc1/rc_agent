"""
Element Risk Radar system for Phase 2 execution planning.
Analyzes construction elements to identify risks and bottlenecks.
"""

import math
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from phase2_models import (
    ElementDetail, ElementRisk, RiskLevel, BarSpecification
)
from core_services import DataRouter


class RiskRadar:
    """Element risk assessment and bottleneck identification system"""

    def __init__(self):
        self.data_router = DataRouter()

        # Risk thresholds (configurable)
        self.complexity_thresholds = {
            RiskLevel.LOW: 2.0,
            RiskLevel.MEDIUM: 3.0,
            RiskLevel.HIGH: 4.0,
            RiskLevel.CRITICAL: 5.0
        }

        self.labor_modifier_thresholds = {
            RiskLevel.LOW: 0.5,
            RiskLevel.MEDIUM: 1.0,
            RiskLevel.HIGH: 2.0,
            RiskLevel.CRITICAL: 3.0
        }

    def analyze_solution_risks(self, rs_id: str) -> List[ElementRisk]:
        """Perform comprehensive risk analysis for a solution"""
        # Load BIM data
        bim_data = self.data_router.load_phase_b_data(rs_id)

        # Parse elements
        elements = self._parse_bim_elements(bim_data)

        # Assess risks for each element
        risks = []
        for element in elements:
            risk = self._assess_element_risk(element)
            risks.append(risk)

        # Sort by risk score (highest first)
        risks.sort(key=lambda x: x.risk_score, reverse=True)

        return risks

    def _parse_bim_elements(self, bim_data: Dict) -> List[ElementDetail]:
        """Parse BIM data into ElementDetail objects"""
        elements = []

        if "by_element" not in bim_data:
            return elements

        for level_name, level_data in bim_data["by_element"].items():
            for element_id, element_data in level_data.items():
                element = ElementDetail.from_bim_data(element_id, level_name, element_data)
                elements.append(element)

        return elements

    def _assess_element_risk(self, element: ElementDetail) -> ElementRisk:
        """Assess risk for a single element"""
        risk_factors = []
        risk_score = 0.0

        # Complexity-based risk assessment
        complexity_risk = self._assess_complexity_risk(element)
        risk_score += complexity_risk["score"]
        risk_factors.extend(complexity_risk["factors"])

        # Labor intensity risk
        labor_risk = self._assess_labor_risk(element)
        risk_score += labor_risk["score"]
        risk_factors.extend(labor_risk["factors"])

        # Material complexity risk
        material_risk = self._assess_material_risk(element)
        risk_score += material_risk["score"]
        risk_factors.extend(material_risk["factors"])

        # Geometric complexity risk
        geometric_risk = self._assess_geometric_risk(element)
        risk_score += geometric_risk["score"]
        risk_factors.extend(geometric_risk["factors"])

        # Normalize risk score (0-1 scale)
        risk_score = min(risk_score / 4.0, 1.0)

        # Determine risk level
        risk_level = self._determine_risk_level(risk_score)

        # Generate mitigation suggestions
        mitigation_suggestions = self._generate_mitigation_suggestions(element, risk_factors)

        # Estimate potential delays
        delay_estimate = self._estimate_delay_potential(element, risk_score)

        # Calculate probability of issues
        issue_probability = self._calculate_issue_probability(element, risk_score)

        return ElementRisk(
            element_id=element.element_id,
            level_name=element.level_name,
            risk_level=risk_level,
            risk_score=risk_score,
            risk_factors=risk_factors,
            mitigation_suggestions=mitigation_suggestions,
            estimated_delay_days=delay_estimate,
            probability_of_issues=issue_probability
        )

    def _assess_complexity_risk(self, element: ElementDetail) -> Dict:
        """Assess risk based on complexity score"""
        score = element.complexity_score
        factors = []
        risk_value = 0.0

        if score > 4.0:
            factors.append(f"Very high complexity score: {score:.2f}")
            risk_value = 1.0
        elif score > 3.0:
            factors.append(f"High complexity score: {score:.2f}")
            risk_value = 0.7
        elif score > 2.5:
            factors.append(f"Moderate complexity score: {score:.2f}")
            risk_value = 0.4
        elif score > 2.0:
            factors.append(f"Elevated complexity score: {score:.2f}")
            risk_value = 0.2

        # Factor in complexity modifier
        if element.complexity_modifier != 1.0:
            modifier_impact = abs(element.complexity_modifier - 1.0)
            if modifier_impact > 0.2:
                factors.append(f"Significant complexity modifier: {element.complexity_modifier:.2f}")
                risk_value += modifier_impact * 0.3

        return {"score": risk_value, "factors": factors}

    def _assess_labor_risk(self, element: ElementDetail) -> Dict:
        """Assess risk based on labor hour modifiers"""
        modifier = element.labor_hours_modifier
        factors = []
        risk_value = 0.0

        if modifier > 3.0:
            factors.append(f"Extremely high labor requirement: +{modifier:.1f}x hours")
            risk_value = 1.0
        elif modifier > 2.0:
            factors.append(f"Very high labor requirement: +{modifier:.1f}x hours")
            risk_value = 0.8
        elif modifier > 1.0:
            factors.append(f"Increased labor requirement: +{modifier:.1f}x hours")
            risk_value = 0.5
        elif modifier > 0.5:
            factors.append(f"Moderately increased labor: +{modifier:.1f}x hours")
            risk_value = 0.3

        # Negative modifiers can also indicate risk (unusual conditions)
        if modifier < -1.0:
            factors.append(f"Unusual labor conditions: {modifier:.1f}x hours")
            risk_value = max(risk_value, 0.4)

        return {"score": risk_value, "factors": factors}

    def _assess_material_risk(self, element: ElementDetail) -> Dict:
        """Assess risk based on material complexity"""
        factors = []
        risk_value = 0.0

        # Bar type diversity risk
        if element.bar_types > 15:
            factors.append(f"Very high bar type diversity: {element.bar_types} types")
            risk_value += 0.8
        elif element.bar_types > 10:
            factors.append(f"High bar type diversity: {element.bar_types} types")
            risk_value += 0.5
        elif element.bar_types > 6:
            factors.append(f"Moderate bar type diversity: {element.bar_types} types")
            risk_value += 0.3

        # Diameter variety risk
        total_diameters = len(element.bars_by_diameter) + len(element.stirrups_by_diameter)
        if total_diameters > 4:
            factors.append(f"Multiple rebar diameters: {total_diameters} different sizes")
            risk_value += 0.3

        # Heavy rebar concentration risk
        total_weight = element.total_rebar_weight
        if total_weight > 500:
            factors.append(f"Heavy rebar concentration: {total_weight:.0f} kg")
            risk_value += 0.4
        elif total_weight > 300:
            factors.append(f"Moderate rebar weight: {total_weight:.0f} kg")
            risk_value += 0.2

        return {"score": min(risk_value, 1.0), "factors": factors}

    def _assess_geometric_risk(self, element: ElementDetail) -> Dict:
        """Assess risk based on geometric properties"""
        factors = []
        risk_value = 0.0

        # Surface area complexity
        surface_area = element.surface_area
        if surface_area > 15:
            factors.append(f"Large surface area: {surface_area:.1f} m²")
            risk_value += 0.3
        elif surface_area > 10:
            factors.append(f"Moderate surface area: {surface_area:.1f} m²")
            risk_value += 0.1

        # Concrete volume
        volume = element.vol_concreto
        if volume > 4:
            factors.append(f"Large concrete volume: {volume:.1f} m³")
            risk_value += 0.2

        # Reinforcement density
        if volume > 0:
            density = element.total_rebar_weight / volume
            if density > 150:  # kg/m³
                factors.append(f"High reinforcement density: {density:.0f} kg/m³")
                risk_value += 0.4
            elif density > 100:
                factors.append(f"Moderate reinforcement density: {density:.0f} kg/m³")
                risk_value += 0.2

        return {"score": min(risk_value, 1.0), "factors": factors}

    def _determine_risk_level(self, risk_score: float) -> RiskLevel:
        """Determine risk level from score"""
        if risk_score >= 0.8:
            return RiskLevel.CRITICAL
        elif risk_score >= 0.6:
            return RiskLevel.HIGH
        elif risk_score >= 0.3:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _generate_mitigation_suggestions(self, element: ElementDetail, risk_factors: List[str]) -> List[str]:
        """Generate mitigation suggestions based on risk factors"""
        suggestions = []

        # Complexity mitigation
        if any("complexity" in factor.lower() for factor in risk_factors):
            suggestions.append("Consider design simplification or staging")
            suggestions.append("Assign experienced crew with complexity training")
            suggestions.append("Allow additional time for layout and inspection")

        # Labor mitigation
        if any("labor" in factor.lower() for factor in risk_factors):
            suggestions.append("Pre-plan crew sequencing and resource allocation")
            suggestions.append("Consider overlapping crews or extended shifts")
            suggestions.append("Implement additional supervision and coordination")

        # Material mitigation
        if any("bar type" in factor.lower() or "diameter" in factor.lower()):
            suggestions.append("Implement material staging and organization systems")
            suggestions.append("Use color coding or tagging for different bar types")
            suggestions.append("Plan delivery sequencing to match construction progress")

        # Weight/density mitigation
        if any("weight" in factor.lower() or "density" in factor.lower()):
            suggestions.append("Plan for crane coverage and lifting equipment")
            suggestions.append("Consider bar pre-fabrication where possible")
            suggestions.append("Schedule concrete pours to minimize rebar exposure time")

        # Generic suggestions for high-risk elements
        if len(risk_factors) > 3:
            suggestions.append("Conduct detailed pre-construction planning meeting")
            suggestions.append("Implement enhanced quality control checkpoints")
            suggestions.append("Consider mock-up or trial installation")

        return suggestions

    def _estimate_delay_potential(self, element: ElementDetail, risk_score: float) -> float:
        """Estimate potential delay in days"""
        # Base delay estimation based on element size and risk
        base_days = element.vol_concreto * 0.5  # 0.5 days per m³ as baseline

        # Risk multiplier
        risk_multiplier = 1.0 + (risk_score * 2.0)  # 1x to 3x multiplier

        # Complexity factor
        complexity_factor = 1.0 + (element.complexity_score / 10.0)

        estimated_delay = base_days * risk_multiplier * complexity_factor

        return min(estimated_delay, 10.0)  # Cap at 10 days

    def _calculate_issue_probability(self, element: ElementDetail, risk_score: float) -> float:
        """Calculate probability of construction issues (0-1 scale)"""
        # Base probability from risk score
        base_probability = risk_score * 0.8  # Max 80% from risk alone

        # Adjust based on historical factors (simulated)
        complexity_adjustment = min(element.complexity_score / 5.0, 0.15)
        labor_adjustment = min(abs(element.labor_hours_modifier) / 5.0, 0.1)

        total_probability = base_probability + complexity_adjustment + labor_adjustment

        return min(total_probability, 0.95)  # Cap at 95%

    def identify_critical_path_risks(self, risks: List[ElementRisk]) -> List[str]:
        """Identify elements that could impact critical path"""
        critical_elements = []

        for risk in risks:
            # High-risk elements with significant delay potential
            if (risk.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] and
                risk.estimated_delay_days > 2.0):
                critical_elements.append(risk.element_id)

        return critical_elements

    def generate_risk_summary(self, risks: List[ElementRisk]) -> Dict[str, Any]:
        """Generate summary statistics for risk assessment"""
        if not risks:
            return {}

        total_elements = len(risks)
        risk_counts = {level: 0 for level in RiskLevel}

        for risk in risks:
            risk_counts[risk.risk_level] += 1

        avg_risk_score = sum(r.risk_score for r in risks) / total_elements
        total_delay_potential = sum(r.estimated_delay_days for r in risks)
        high_probability_issues = len([r for r in risks if r.probability_of_issues > 0.6])

        return {
            "total_elements": total_elements,
            "risk_distribution": {level.value: count for level, count in risk_counts.items()},
            "average_risk_score": round(avg_risk_score, 3),
            "total_delay_potential_days": round(total_delay_potential, 1),
            "high_probability_issues": high_probability_issues,
            "critical_path_risks": len(self.identify_critical_path_risks(risks)),
            "risk_level_percentages": {
                level.value: round((count / total_elements) * 100, 1)
                for level, count in risk_counts.items()
            }
        }