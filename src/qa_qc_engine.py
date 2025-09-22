"""
QA/QC Validation Engine for Phase 2 execution planning.
Automated quality control checks and validation against construction standards.
"""

import math
from typing import Dict, List, Tuple, Optional, Set, Any
from datetime import datetime
from dataclasses import dataclass
from phase2_models import (
    ElementDetail, QualityCheck, QualityIssueType, RiskLevel
)


@dataclass
class QualityStandard:
    """Quality standard definition"""
    standard_id: str
    name: str
    parameter: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    target_value: Optional[float] = None
    tolerance: Optional[float] = None
    unit: Optional[str] = None
    severity: RiskLevel = RiskLevel.MEDIUM


@dataclass
class QualityRule:
    """Quality validation rule"""
    rule_id: str
    name: str
    description: str
    check_type: QualityIssueType
    condition: str  # Python expression to evaluate
    severity: RiskLevel
    recommendation: str


class QualityValidator:
    """Quality control validation engine"""

    def __init__(self):
        # Initialize quality standards
        self.standards = self._initialize_quality_standards()
        self.rules = self._initialize_quality_rules()

        # Rebar specifications (standard diameters and properties)
        self.rebar_specs = {
            "3/8\"": {"diameter_mm": 9.5, "area_mm2": 71, "weight_kg_m": 0.56},
            "1/2\"": {"diameter_mm": 12.7, "area_mm2": 127, "weight_kg_m": 0.99},
            "5/8\"": {"diameter_mm": 15.9, "area_mm2": 199, "weight_kg_m": 1.55},
            "3/4\"": {"diameter_mm": 19.1, "area_mm2": 287, "weight_kg_m": 2.24},
            "7/8\"": {"diameter_mm": 22.2, "area_mm2": 387, "weight_kg_m": 3.04},
            "1\"": {"diameter_mm": 25.4, "area_mm2": 507, "weight_kg_m": 3.96}
        }

    def validate_element_quality(self, element: ElementDetail) -> List[QualityCheck]:
        """Perform comprehensive quality validation for an element"""
        checks = []

        # Reinforcement ratio checks
        checks.extend(self._check_reinforcement_ratios(element))

        # Stirrup spacing checks
        checks.extend(self._check_stirrup_spacing(element))

        # Bar diameter combinations
        checks.extend(self._check_bar_diameter_combinations(element))

        # Connector placement validation
        checks.extend(self._check_connector_placement(element))

        # Concrete cover requirements
        checks.extend(self._check_concrete_cover(element))

        # Construction feasibility
        checks.extend(self._check_construction_feasibility(element))

        # Material quantity validation
        checks.extend(self._check_material_quantities(element))

        return checks

    def _initialize_quality_standards(self) -> Dict[str, QualityStandard]:
        """Initialize construction quality standards"""
        standards = {}

        # Reinforcement ratio standards (typical ranges)
        standards["min_reinforcement_ratio"] = QualityStandard(
            standard_id="min_reinforcement_ratio",
            name="Minimum Reinforcement Ratio",
            parameter="reinforcement_ratio",
            min_value=0.002,  # 0.2%
            unit="%",
            severity=RiskLevel.HIGH
        )

        standards["max_reinforcement_ratio"] = QualityStandard(
            standard_id="max_reinforcement_ratio",
            name="Maximum Reinforcement Ratio",
            parameter="reinforcement_ratio",
            max_value=0.04,  # 4%
            unit="%",
            severity=RiskLevel.MEDIUM
        )

        # Stirrup spacing standards
        standards["max_stirrup_spacing"] = QualityStandard(
            standard_id="max_stirrup_spacing",
            name="Maximum Stirrup Spacing",
            parameter="stirrup_spacing",
            max_value=300,  # mm
            unit="mm",
            severity=RiskLevel.HIGH
        )

        # Concrete cover requirements
        standards["min_concrete_cover"] = QualityStandard(
            standard_id="min_concrete_cover",
            name="Minimum Concrete Cover",
            parameter="concrete_cover",
            min_value=25,  # mm
            unit="mm",
            severity=RiskLevel.CRITICAL
        )

        # Bar development length
        standards["min_development_length"] = QualityStandard(
            standard_id="min_development_length",
            name="Minimum Development Length",
            parameter="development_length",
            min_value=200,  # mm
            unit="mm",
            severity=RiskLevel.HIGH
        )

        return standards

    def _initialize_quality_rules(self) -> List[QualityRule]:
        """Initialize quality validation rules"""
        rules = []

        # Reinforcement ratio rule
        rules.append(QualityRule(
            rule_id="reinforcement_ratio_check",
            name="Reinforcement Ratio Validation",
            description="Check if reinforcement ratio is within acceptable limits",
            check_type=QualityIssueType.REINFORCEMENT_RATIO,
            condition="0.002 <= reinforcement_ratio <= 0.04",
            severity=RiskLevel.HIGH,
            recommendation="Adjust reinforcement quantity to meet code requirements"
        ))

        # Stirrup spacing rule
        rules.append(QualityRule(
            rule_id="stirrup_spacing_check",
            name="Stirrup Spacing Validation",
            description="Verify stirrup spacing meets structural requirements",
            check_type=QualityIssueType.STIRRUP_SPACING,
            condition="stirrup_spacing <= 300",
            severity=RiskLevel.HIGH,
            recommendation="Reduce stirrup spacing or increase stirrup density"
        ))

        # Bar diameter compatibility
        rules.append(QualityRule(
            rule_id="bar_diameter_compatibility",
            name="Bar Diameter Compatibility",
            description="Check for compatible bar diameter combinations",
            check_type=QualityIssueType.BAR_DIAMETER,
            condition="max_diameter / min_diameter <= 2.0",
            severity=RiskLevel.MEDIUM,
            recommendation="Consider standardizing bar diameters for construction efficiency"
        ))

        # Connector placement rule
        rules.append(QualityRule(
            rule_id="connector_placement_check",
            name="Connector Placement Validation",
            description="Validate mechanical connector placement and spacing",
            check_type=QualityIssueType.CONNECTOR_PLACEMENT,
            condition="connector_spacing >= 150",
            severity=RiskLevel.MEDIUM,
            recommendation="Ensure adequate spacing between mechanical connectors"
        ))

        return rules

    def _check_reinforcement_ratios(self, element: ElementDetail) -> List[QualityCheck]:
        """Check reinforcement ratios against standards"""
        checks = []

        if element.vol_concreto <= 0:
            return checks

        # Calculate total steel area
        total_steel_area = 0
        for diameter, bar_spec in element.bars_by_diameter.items():
            if diameter in self.rebar_specs:
                area_per_bar = self.rebar_specs[diameter]["area_mm2"]
                total_steel_area += bar_spec.count * area_per_bar

        # Estimate concrete area (simplified - assumes average cross-section)
        concrete_area = element.vol_concreto / (element.surface_area / 4) * 1000000  # Convert to mm²

        if concrete_area > 0:
            reinforcement_ratio = total_steel_area / concrete_area

            # Check against minimum ratio
            if reinforcement_ratio < 0.002:
                checks.append(QualityCheck(
                    check_id=f"{element.element_id}_min_reinforcement",
                    element_id=element.element_id,
                    check_type=QualityIssueType.REINFORCEMENT_RATIO,
                    description=f"Reinforcement ratio {reinforcement_ratio:.4f} below minimum 0.002",
                    status="failed",
                    severity=RiskLevel.HIGH,
                    resolution="Increase reinforcement quantity"
                ))

            # Check against maximum ratio
            elif reinforcement_ratio > 0.04:
                checks.append(QualityCheck(
                    check_id=f"{element.element_id}_max_reinforcement",
                    element_id=element.element_id,
                    check_type=QualityIssueType.REINFORCEMENT_RATIO,
                    description=f"Reinforcement ratio {reinforcement_ratio:.4f} exceeds maximum 0.04",
                    status="failed",
                    severity=RiskLevel.MEDIUM,
                    resolution="Reduce reinforcement density or increase member size"
                ))

            else:
                checks.append(QualityCheck(
                    check_id=f"{element.element_id}_reinforcement_ok",
                    element_id=element.element_id,
                    check_type=QualityIssueType.REINFORCEMENT_RATIO,
                    description=f"Reinforcement ratio {reinforcement_ratio:.4f} within acceptable range",
                    status="passed",
                    severity=RiskLevel.LOW
                ))

        return checks

    def _check_stirrup_spacing(self, element: ElementDetail) -> List[QualityCheck]:
        """Check stirrup spacing requirements"""
        checks = []

        if not element.stirrups_by_diameter:
            # No stirrups found - might be an issue
            checks.append(QualityCheck(
                check_id=f"{element.element_id}_no_stirrups",
                element_id=element.element_id,
                check_type=QualityIssueType.STIRRUP_SPACING,
                description="No stirrups found in element",
                status="failed",
                severity=RiskLevel.HIGH,
                resolution="Add stirrups if required by structural design"
            ))
            return checks

        # Estimate stirrup spacing based on quantity and element dimensions
        total_stirrups = sum(spec.count for spec in element.stirrups_by_diameter.values())

        if total_stirrups > 0 and element.vol_concreto > 0:
            # Rough estimate of spacing (simplified calculation)
            estimated_length = math.sqrt(element.vol_concreto / (element.surface_area / 10))  # Rough member length
            estimated_spacing = (estimated_length * 1000) / total_stirrups  # Convert to mm

            if estimated_spacing > 300:
                checks.append(QualityCheck(
                    check_id=f"{element.element_id}_stirrup_spacing",
                    element_id=element.element_id,
                    check_type=QualityIssueType.STIRRUP_SPACING,
                    description=f"Estimated stirrup spacing {estimated_spacing:.0f}mm exceeds maximum 300mm",
                    status="failed",
                    severity=RiskLevel.HIGH,
                    resolution="Increase stirrup quantity or reduce spacing"
                ))
            else:
                checks.append(QualityCheck(
                    check_id=f"{element.element_id}_stirrup_spacing_ok",
                    element_id=element.element_id,
                    check_type=QualityIssueType.STIRRUP_SPACING,
                    description=f"Estimated stirrup spacing {estimated_spacing:.0f}mm within acceptable range",
                    status="passed",
                    severity=RiskLevel.LOW
                ))

        return checks

    def _check_bar_diameter_combinations(self, element: ElementDetail) -> List[QualityCheck]:
        """Check bar diameter combinations for constructibility"""
        checks = []

        if len(element.bars_by_diameter) <= 1:
            # Single diameter or no bars - no compatibility issues
            return checks

        # Get all diameters used
        diameters_used = list(element.bars_by_diameter.keys())

        # Check for excessive diameter variety
        if len(diameters_used) > 3:
            checks.append(QualityCheck(
                check_id=f"{element.element_id}_diameter_variety",
                element_id=element.element_id,
                check_type=QualityIssueType.BAR_DIAMETER,
                description=f"High bar diameter variety: {len(diameters_used)} different sizes",
                status="failed",
                severity=RiskLevel.MEDIUM,
                resolution="Consider standardizing to fewer bar diameters"
            ))

        # Check diameter ratios for compatibility
        diameter_values = []
        for diameter in diameters_used:
            if diameter in self.rebar_specs:
                diameter_values.append(self.rebar_specs[diameter]["diameter_mm"])

        if len(diameter_values) >= 2:
            max_diameter = max(diameter_values)
            min_diameter = min(diameter_values)
            ratio = max_diameter / min_diameter

            if ratio > 2.5:
                checks.append(QualityCheck(
                    check_id=f"{element.element_id}_diameter_ratio",
                    element_id=element.element_id,
                    check_type=QualityIssueType.BAR_DIAMETER,
                    description=f"Large diameter ratio {ratio:.1f} may cause construction difficulties",
                    status="failed",
                    severity=RiskLevel.MEDIUM,
                    resolution="Consider more compatible diameter combinations"
                ))

        return checks

    def _check_connector_placement(self, element: ElementDetail) -> List[QualityCheck]:
        """Check mechanical connector placement and requirements"""
        checks = []

        total_connectors = 0
        for diameter, connector_spec in element.connectors_by_diameter.items():
            total_connectors += connector_spec.count

        if total_connectors == 0:
            # No connectors - this might be normal
            return checks

        # Check connector to bar ratio
        total_bars = sum(spec.count for spec in element.bars_by_diameter.values())

        if total_bars > 0:
            connector_ratio = total_connectors / total_bars

            if connector_ratio > 0.5:
                checks.append(QualityCheck(
                    check_id=f"{element.element_id}_high_connector_ratio",
                    element_id=element.element_id,
                    check_type=QualityIssueType.CONNECTOR_PLACEMENT,
                    description=f"High connector ratio {connector_ratio:.2f} may indicate design issues",
                    status="failed",
                    severity=RiskLevel.MEDIUM,
                    resolution="Review connector necessity and placement"
                ))

            # Check for adequate connector spacing (simplified)
            if total_connectors > 1 and element.surface_area > 0:
                estimated_spacing = math.sqrt(element.surface_area / total_connectors) * 1000  # Convert to mm

                if estimated_spacing < 150:
                    checks.append(QualityCheck(
                        check_id=f"{element.element_id}_connector_spacing",
                        element_id=element.element_id,
                        check_type=QualityIssueType.CONNECTOR_PLACEMENT,
                        description=f"Tight connector spacing {estimated_spacing:.0f}mm may cause interference",
                        status="failed",
                        severity=RiskLevel.MEDIUM,
                        resolution="Increase connector spacing or reduce quantity"
                    ))

        return checks

    def _check_concrete_cover(self, element: ElementDetail) -> List[QualityCheck]:
        """Check concrete cover requirements (simplified)"""
        checks = []

        # Estimate cover based on element geometry (simplified approach)
        if element.vol_concreto > 0 and element.surface_area > 0:
            # Very rough estimate of member thickness
            estimated_thickness = element.vol_concreto / element.surface_area * 1000  # Convert to mm

            # Assume largest bar diameter
            largest_diameter = 0
            for diameter in element.bars_by_diameter.keys():
                if diameter in self.rebar_specs:
                    bar_diameter = self.rebar_specs[diameter]["diameter_mm"]
                    largest_diameter = max(largest_diameter, bar_diameter)

            # Minimum cover should be at least bar diameter + 25mm
            required_cover = largest_diameter + 25

            # Available cover (very simplified)
            available_cover = (estimated_thickness - largest_diameter) / 2

            if available_cover < required_cover:
                checks.append(QualityCheck(
                    check_id=f"{element.element_id}_concrete_cover",
                    element_id=element.element_id,
                    check_type=QualityIssueType.COVERAGE,
                    description=f"Insufficient concrete cover: {available_cover:.0f}mm < required {required_cover:.0f}mm",
                    status="failed",
                    severity=RiskLevel.HIGH,
                    resolution="Increase member thickness or reduce bar diameter"
                ))

        return checks

    def _check_construction_feasibility(self, element: ElementDetail) -> List[QualityCheck]:
        """Check construction feasibility based on complexity"""
        checks = []

        # Check complexity score
        if element.complexity_score > 4.0:
            checks.append(QualityCheck(
                check_id=f"{element.element_id}_high_complexity",
                element_id=element.element_id,
                check_type=QualityIssueType.BAR_DIAMETER,
                description=f"Very high complexity score {element.complexity_score:.2f} may cause construction issues",
                status="failed",
                severity=RiskLevel.HIGH,
                resolution="Consider design simplification or enhanced construction planning"
            ))

        # Check bar type diversity
        if element.bar_types > 15:
            checks.append(QualityCheck(
                check_id=f"{element.element_id}_bar_type_variety",
                element_id=element.element_id,
                check_type=QualityIssueType.BAR_DIAMETER,
                description=f"High bar type variety ({element.bar_types} types) increases construction complexity",
                status="failed",
                severity=RiskLevel.MEDIUM,
                resolution="Standardize bar types where possible"
            ))

        # Check labor hour modifier
        if abs(element.labor_hours_modifier) > 2.0:
            severity = RiskLevel.HIGH if abs(element.labor_hours_modifier) > 3.0 else RiskLevel.MEDIUM
            checks.append(QualityCheck(
                check_id=f"{element.element_id}_labor_intensity",
                element_id=element.element_id,
                check_type=QualityIssueType.BAR_DIAMETER,
                description=f"Extreme labor hour modifier {element.labor_hours_modifier:.1f} indicates construction challenges",
                status="failed",
                severity=severity,
                resolution="Plan for specialized crew and extended schedule"
            ))

        return checks

    def _check_material_quantities(self, element: ElementDetail) -> List[QualityCheck]:
        """Validate material quantity consistency"""
        checks = []

        # Check weight consistency
        calculated_weight = 0
        for diameter, bar_spec in element.bars_by_diameter.items():
            if diameter in self.rebar_specs:
                weight_per_bar = self.rebar_specs[diameter]["weight_kg_m"]
                # Estimate average bar length (simplified)
                avg_bar_length = bar_spec.weight / (bar_spec.count * weight_per_bar) if bar_spec.count > 0 else 0
                calculated_weight += bar_spec.weight

        # Add stirrup weight
        for diameter, stirrup_spec in element.stirrups_by_diameter.items():
            calculated_weight += stirrup_spec.weight

        # Compare with reported total weight
        if abs(calculated_weight - element.total_rebar_weight) > element.total_rebar_weight * 0.1:  # 10% tolerance
            checks.append(QualityCheck(
                check_id=f"{element.element_id}_weight_mismatch",
                element_id=element.element_id,
                check_type=QualityIssueType.BAR_DIAMETER,
                description=f"Weight mismatch: calculated {calculated_weight:.1f}kg vs reported {element.total_rebar_weight:.1f}kg",
                status="failed",
                severity=RiskLevel.LOW,
                resolution="Verify material quantity calculations"
            ))

        return checks

    def generate_quality_summary(self, all_checks: List[QualityCheck]) -> Dict[str, Any]:
        """Generate summary of quality validation results"""
        if not all_checks:
            return {"total_checks": 0, "all_passed": True}

        # Count by status
        passed_checks = len([c for c in all_checks if c.status == "passed"])
        failed_checks = len([c for c in all_checks if c.status == "failed"])

        # Count by severity
        severity_counts = {level: 0 for level in RiskLevel}
        for check in all_checks:
            if check.status == "failed":
                severity_counts[check.severity] += 1

        # Count by issue type
        issue_type_counts = {}
        for check in all_checks:
            if check.status == "failed":
                issue_type = check.check_type.value
                issue_type_counts[issue_type] = issue_type_counts.get(issue_type, 0) + 1

        # Critical issues that need immediate attention
        critical_issues = [c for c in all_checks
                         if c.status == "failed" and c.severity == RiskLevel.CRITICAL]

        return {
            "total_checks": len(all_checks),
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "pass_rate": (passed_checks / len(all_checks)) * 100,
            "severity_distribution": {level.value: count for level, count in severity_counts.items()},
            "issue_type_distribution": issue_type_counts,
            "critical_issues": len(critical_issues),
            "critical_issue_details": [
                {"element_id": c.element_id, "description": c.description}
                for c in critical_issues
            ],
            "quality_score": self._calculate_quality_score(all_checks),
            "recommendations": self._generate_quality_recommendations(all_checks)
        }

    def _calculate_quality_score(self, checks: List[QualityCheck]) -> float:
        """Calculate overall quality score (0-100)"""
        if not checks:
            return 100.0

        total_weight = 0
        penalty_weight = 0

        for check in checks:
            weight = 1.0
            if check.severity == RiskLevel.CRITICAL:
                weight = 4.0
            elif check.severity == RiskLevel.HIGH:
                weight = 3.0
            elif check.severity == RiskLevel.MEDIUM:
                weight = 2.0

            total_weight += weight

            if check.status == "failed":
                penalty_weight += weight

        if total_weight == 0:
            return 100.0

        score = max(0, 100 - (penalty_weight / total_weight) * 100)
        return round(score, 1)

    def _generate_quality_recommendations(self, checks: List[QualityCheck]) -> List[str]:
        """Generate prioritized quality improvement recommendations"""
        recommendations = []

        # Group failed checks by type
        failed_by_type = {}
        for check in checks:
            if check.status == "failed":
                issue_type = check.check_type.value
                if issue_type not in failed_by_type:
                    failed_by_type[issue_type] = []
                failed_by_type[issue_type].append(check)

        # Generate recommendations based on most common issues
        for issue_type, failed_checks in failed_by_type.items():
            if len(failed_checks) > 1:
                recommendations.append(
                    f"Address {len(failed_checks)} {issue_type} issues across multiple elements"
                )

        # Add specific recommendations for critical issues
        critical_checks = [c for c in checks if c.status == "failed" and c.severity == RiskLevel.CRITICAL]
        for check in critical_checks:
            if check.resolution:
                recommendations.append(f"CRITICAL: {check.resolution} for element {check.element_id}")

        return recommendations[:10]  # Limit to top 10 recommendations