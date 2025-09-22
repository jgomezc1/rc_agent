"""
Enhanced reporting system for Phase 2 execution planning.
Generates comprehensive reports combining all Phase 2 analysis engines.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from phase2_models import (
    ElementRisk, CrewRequirement, ProcurementItem, QualityCheck,
    ConstructibilityInsight, RiskLevel, QualityStatus, InsightPriority
)
from risk_radar import RiskRadar
from crew_planner import CrewPlanner
from procurement_system import ProcurementOptimizer
from qa_qc_engine import QualityValidator
from constructibility_engine import ConstructibilityAnalyzer


class Phase2Reporter:
    """Comprehensive reporting system for Phase 2 execution planning"""

    def __init__(self):
        self.risk_radar = RiskRadar()
        self.crew_planner = CrewPlanner()
        self.procurement_optimizer = ProcurementOptimizer()
        self.quality_validator = QualityValidator()
        self.constructibility_analyzer = ConstructibilityAnalyzer()

    def generate_execution_report(self, rs_id: str, include_detailed_analysis: bool = True) -> Dict[str, Any]:
        """Generate comprehensive execution planning report"""

        # Perform all analyses
        risks = self.risk_radar.analyze_solution_risks(rs_id)
        crew_plan = self.crew_planner.generate_construction_plan(rs_id)
        procurement_plan = self.procurement_optimizer.optimize_procurement(rs_id)
        quality_checks = self.quality_validator.validate_solution(rs_id)
        constructibility_insights = self.constructibility_analyzer.analyze_constructibility(rs_id)

        # Generate main report structure
        report = {
            "metadata": self._generate_metadata(rs_id),
            "executive_summary": self._generate_executive_summary(
                risks, crew_plan, procurement_plan, quality_checks, constructibility_insights
            ),
            "risk_analysis": self._format_risk_analysis(risks),
            "construction_planning": self._format_construction_planning(crew_plan),
            "procurement_strategy": self._format_procurement_strategy(procurement_plan),
            "quality_validation": self._format_quality_validation(quality_checks),
            "constructibility_insights": self._format_constructibility_insights(constructibility_insights),
            "recommendations": self._generate_recommendations(
                risks, crew_plan, procurement_plan, quality_checks, constructibility_insights
            )
        }

        if include_detailed_analysis:
            report["detailed_analysis"] = self._generate_detailed_analysis(
                risks, crew_plan, procurement_plan, quality_checks, constructibility_insights
            )

        return report

    def _generate_metadata(self, rs_id: str) -> Dict[str, Any]:
        """Generate report metadata"""
        return {
            "rs_id": rs_id,
            "report_type": "Phase 2 Execution Planning",
            "generated_at": datetime.now().isoformat(),
            "report_version": "2.0",
            "analysis_engines": [
                "Risk Radar",
                "Crew Planner",
                "Procurement Optimizer",
                "Quality Validator",
                "Constructibility Analyzer"
            ]
        }

    def _generate_executive_summary(self, risks: List[ElementRisk], crew_plan: Dict,
                                   procurement_plan: Dict, quality_checks: List[QualityCheck],
                                   insights: List[ConstructibilityInsight]) -> Dict[str, Any]:
        """Generate executive summary of all analyses"""

        # Risk summary
        total_elements = len(risks)
        critical_risks = len([r for r in risks if r.risk_level == RiskLevel.CRITICAL])
        high_risks = len([r for r in risks if r.risk_level == RiskLevel.HIGH])
        total_delay_potential = sum(r.estimated_delay_days for r in risks)

        # Construction summary
        total_tasks = len(crew_plan.get("tasks", []))
        estimated_duration = crew_plan.get("total_duration_days", 0)
        total_crew_size = crew_plan.get("peak_crew_size", 0)

        # Procurement summary
        total_suppliers = len(procurement_plan.get("suppliers", []))
        total_deliveries = len(procurement_plan.get("delivery_schedule", []))
        total_procurement_value = procurement_plan.get("total_cost", 0)

        # Quality summary
        quality_issues = len([q for q in quality_checks if q.status == QualityStatus.FAIL])
        quality_warnings = len([q for q in quality_checks if q.status == QualityStatus.WARNING])

        # Constructibility summary
        high_priority_insights = len([i for i in insights if i.priority == InsightPriority.HIGH])
        total_savings_potential = sum(i.estimated_savings_hours for i in insights)

        return {
            "project_overview": {
                "total_elements_analyzed": total_elements,
                "estimated_project_duration_days": round(estimated_duration, 1),
                "peak_crew_size": total_crew_size,
                "total_procurement_value": round(total_procurement_value, 2)
            },
            "risk_profile": {
                "critical_risk_elements": critical_risks,
                "high_risk_elements": high_risks,
                "total_delay_potential_days": round(total_delay_potential, 1),
                "risk_distribution": f"{critical_risks + high_risks}/{total_elements} high-risk elements"
            },
            "construction_feasibility": {
                "total_construction_tasks": total_tasks,
                "quality_issues_identified": quality_issues,
                "quality_warnings": quality_warnings,
                "construction_complexity_rating": self._calculate_complexity_rating(risks)
            },
            "optimization_opportunities": {
                "high_priority_insights": high_priority_insights,
                "potential_labor_savings_hours": round(total_savings_potential, 1),
                "procurement_suppliers": total_suppliers,
                "delivery_coordination_events": total_deliveries
            },
            "overall_assessment": self._generate_overall_assessment(
                critical_risks, quality_issues, high_priority_insights, estimated_duration
            )
        }

    def _format_risk_analysis(self, risks: List[ElementRisk]) -> Dict[str, Any]:
        """Format risk analysis results"""
        if not risks:
            return {"status": "No elements analyzed"}

        risk_summary = self.risk_radar.generate_risk_summary(risks)
        critical_path_risks = self.risk_radar.identify_critical_path_risks(risks)

        # Top 10 highest risk elements
        top_risks = risks[:10]  # Already sorted by risk score

        return {
            "summary": risk_summary,
            "critical_path_elements": critical_path_risks,
            "top_risk_elements": [
                {
                    "element_id": risk.element_id,
                    "level": risk.level_name,
                    "risk_level": risk.risk_level.value,
                    "risk_score": round(risk.risk_score, 3),
                    "delay_potential_days": round(risk.estimated_delay_days, 1),
                    "issue_probability": round(risk.probability_of_issues, 3),
                    "primary_risk_factors": risk.risk_factors[:3]
                }
                for risk in top_risks
            ],
            "mitigation_priorities": self._prioritize_risk_mitigation(risks)
        }

    def _format_construction_planning(self, crew_plan: Dict) -> Dict[str, Any]:
        """Format construction planning results"""
        if not crew_plan:
            return {"status": "No construction plan available"}

        return {
            "timeline": {
                "total_duration_days": crew_plan.get("total_duration_days", 0),
                "estimated_start_date": crew_plan.get("estimated_start_date", "TBD"),
                "estimated_completion_date": crew_plan.get("estimated_completion_date", "TBD")
            },
            "resource_requirements": {
                "peak_crew_size": crew_plan.get("peak_crew_size", 0),
                "total_labor_hours": crew_plan.get("total_labor_hours", 0),
                "crew_composition": crew_plan.get("crew_requirements", {})
            },
            "task_breakdown": {
                "total_tasks": len(crew_plan.get("tasks", [])),
                "parallel_task_opportunities": crew_plan.get("parallel_opportunities", 0),
                "critical_path_tasks": len(crew_plan.get("critical_path", []))
            },
            "scheduling_insights": crew_plan.get("scheduling_insights", [])
        }

    def _format_procurement_strategy(self, procurement_plan: Dict) -> Dict[str, Any]:
        """Format procurement strategy results"""
        if not procurement_plan:
            return {"status": "No procurement plan available"}

        return {
            "supplier_strategy": {
                "total_suppliers": len(procurement_plan.get("suppliers", [])),
                "supplier_mix": procurement_plan.get("supplier_mix", {}),
                "risk_diversification": procurement_plan.get("risk_diversification", "Not assessed")
            },
            "delivery_coordination": {
                "total_deliveries": len(procurement_plan.get("delivery_schedule", [])),
                "just_in_time_opportunities": procurement_plan.get("jit_opportunities", 0),
                "storage_requirements": procurement_plan.get("storage_needs", {})
            },
            "cost_optimization": {
                "total_procurement_cost": procurement_plan.get("total_cost", 0),
                "bulk_purchase_savings": procurement_plan.get("bulk_savings", 0),
                "supplier_negotiation_opportunities": procurement_plan.get("negotiation_opportunities", [])
            },
            "supply_chain_insights": procurement_plan.get("supply_chain_insights", [])
        }

    def _format_quality_validation(self, quality_checks: List[QualityCheck]) -> Dict[str, Any]:
        """Format quality validation results"""
        if not quality_checks:
            return {"status": "No quality checks performed"}

        total_checks = len(quality_checks)
        passed = len([q for q in quality_checks if q.status == QualityStatus.PASS])
        warnings = len([q for q in quality_checks if q.status == QualityStatus.WARNING])
        failed = len([q for q in quality_checks if q.status == QualityStatus.FAIL])

        return {
            "validation_summary": {
                "total_checks": total_checks,
                "passed": passed,
                "warnings": warnings,
                "failed": failed,
                "pass_rate": round((passed / total_checks) * 100, 1) if total_checks > 0 else 0
            },
            "critical_issues": [
                {
                    "element_id": check.element_id,
                    "check_type": check.check_type,
                    "issue": check.message,
                    "recommended_action": check.recommended_action
                }
                for check in quality_checks if check.status == QualityStatus.FAIL
            ],
            "quality_improvements": [
                {
                    "element_id": check.element_id,
                    "check_type": check.check_type,
                    "warning": check.message,
                    "suggestion": check.recommended_action
                }
                for check in quality_checks if check.status == QualityStatus.WARNING
            ]
        }

    def _format_constructibility_insights(self, insights: List[ConstructibilityInsight]) -> Dict[str, Any]:
        """Format constructibility insights results"""
        if not insights:
            return {"status": "No constructibility insights generated"}

        high_priority = [i for i in insights if i.priority == InsightPriority.HIGH]
        medium_priority = [i for i in insights if i.priority == InsightPriority.MEDIUM]

        total_savings = sum(i.estimated_savings_hours for i in insights)

        return {
            "optimization_summary": {
                "total_insights": len(insights),
                "high_priority_insights": len(high_priority),
                "medium_priority_insights": len(medium_priority),
                "total_savings_potential_hours": round(total_savings, 1)
            },
            "priority_optimizations": [
                {
                    "insight_type": insight.insight_type,
                    "title": insight.title,
                    "description": insight.description,
                    "savings_hours": insight.estimated_savings_hours,
                    "implementation_steps": insight.implementation_steps[:3]  # Top 3 steps
                }
                for insight in high_priority
            ],
            "quick_wins": [
                insight.title for insight in insights
                if insight.estimated_savings_hours > 0 and len(insight.implementation_steps) <= 3
            ],
            "design_recommendations": [
                insight.description for insight in insights
                if "design" in insight.insight_type.lower()
            ]
        }

    def _generate_recommendations(self, risks: List[ElementRisk], crew_plan: Dict,
                                 procurement_plan: Dict, quality_checks: List[QualityCheck],
                                 insights: List[ConstructibilityInsight]) -> Dict[str, List[str]]:
        """Generate actionable recommendations based on all analyses"""

        recommendations = {
            "immediate_actions": [],
            "planning_priorities": [],
            "risk_mitigation": [],
            "optimization_opportunities": []
        }

        # Immediate actions from quality issues
        critical_quality_issues = [q for q in quality_checks if q.status == QualityStatus.FAIL]
        if critical_quality_issues:
            recommendations["immediate_actions"].append(
                f"Address {len(critical_quality_issues)} critical quality issues before construction"
            )

        # High-risk element actions
        critical_risks = [r for r in risks if r.risk_level == RiskLevel.CRITICAL]
        if critical_risks:
            recommendations["immediate_actions"].append(
                f"Conduct detailed pre-construction planning for {len(critical_risks)} critical-risk elements"
            )

        # Planning priorities from construction complexity
        if crew_plan.get("total_duration_days", 0) > 30:
            recommendations["planning_priorities"].append("Consider project phasing due to extended duration")

        if crew_plan.get("peak_crew_size", 0) > 15:
            recommendations["planning_priorities"].append("Plan for enhanced site logistics and crew coordination")

        # Risk mitigation from delay potential
        total_delay_potential = sum(r.estimated_delay_days for r in risks)
        if total_delay_potential > 10:
            recommendations["risk_mitigation"].append(
                f"Build {round(total_delay_potential * 0.2, 1)} days buffer into schedule for risk mitigation"
            )

        # Optimization opportunities from insights
        high_priority_insights = [i for i in insights if i.priority == InsightPriority.HIGH]
        if high_priority_insights:
            recommendations["optimization_opportunities"].extend([
                f"Implement {insight.title}" for insight in high_priority_insights[:3]
            ])

        # Procurement recommendations
        if len(procurement_plan.get("suppliers", [])) < 3:
            recommendations["planning_priorities"].append("Consider additional suppliers for risk diversification")

        return recommendations

    def _generate_detailed_analysis(self, risks: List[ElementRisk], crew_plan: Dict,
                                   procurement_plan: Dict, quality_checks: List[QualityCheck],
                                   insights: List[ConstructibilityInsight]) -> Dict[str, Any]:
        """Generate detailed analysis section"""

        return {
            "risk_details": {
                "element_breakdown": [
                    {
                        "element_id": risk.element_id,
                        "level_name": risk.level_name,
                        "risk_assessment": {
                            "risk_level": risk.risk_level.value,
                            "risk_score": risk.risk_score,
                            "delay_estimate": risk.estimated_delay_days,
                            "issue_probability": risk.probability_of_issues
                        },
                        "risk_factors": risk.risk_factors,
                        "mitigation_suggestions": risk.mitigation_suggestions
                    }
                    for risk in risks
                ]
            },
            "construction_details": crew_plan,
            "procurement_details": procurement_plan,
            "quality_details": [
                {
                    "element_id": check.element_id,
                    "check_type": check.check_type,
                    "status": check.status.value,
                    "message": check.message,
                    "recommended_action": check.recommended_action,
                    "severity": getattr(check, 'severity', 'Medium')
                }
                for check in quality_checks
            ],
            "constructibility_details": [
                {
                    "insight_type": insight.insight_type,
                    "priority": insight.priority.value,
                    "title": insight.title,
                    "description": insight.description,
                    "implementation_steps": insight.implementation_steps,
                    "estimated_savings": insight.estimated_savings_hours,
                    "affected_elements": getattr(insight, 'affected_elements', [])
                }
                for insight in insights
            ]
        }

    def _calculate_complexity_rating(self, risks: List[ElementRisk]) -> str:
        """Calculate overall project complexity rating"""
        if not risks:
            return "Not assessed"

        avg_risk_score = sum(r.risk_score for r in risks) / len(risks)
        critical_count = len([r for r in risks if r.risk_level == RiskLevel.CRITICAL])

        if avg_risk_score > 0.7 or critical_count > len(risks) * 0.2:
            return "Very High"
        elif avg_risk_score > 0.5 or critical_count > len(risks) * 0.1:
            return "High"
        elif avg_risk_score > 0.3:
            return "Medium"
        else:
            return "Low"

    def _generate_overall_assessment(self, critical_risks: int, quality_issues: int,
                                    high_priority_insights: int, duration: float) -> str:
        """Generate overall project assessment"""

        if critical_risks > 5 or quality_issues > 3:
            return "High complexity project requiring extensive planning and risk mitigation"
        elif critical_risks > 2 or quality_issues > 1 or duration > 45:
            return "Moderate complexity project with manageable risks and good optimization potential"
        elif high_priority_insights > 3:
            return "Standard complexity project with excellent optimization opportunities"
        else:
            return "Low complexity project suitable for standard construction practices"

    def _prioritize_risk_mitigation(self, risks: List[ElementRisk]) -> List[str]:
        """Prioritize risk mitigation actions"""
        priorities = []

        # Critical risks first
        critical_risks = [r for r in risks if r.risk_level == RiskLevel.CRITICAL]
        if critical_risks:
            priorities.append(f"Address {len(critical_risks)} critical risk elements immediately")

        # High delay potential
        high_delay_risks = [r for r in risks if r.estimated_delay_days > 3]
        if high_delay_risks:
            priorities.append(f"Mitigate {len(high_delay_risks)} elements with high delay potential")

        # High probability issues
        high_prob_risks = [r for r in risks if r.probability_of_issues > 0.7]
        if high_prob_risks:
            priorities.append(f"Plan contingencies for {len(high_prob_risks)} high-probability issue elements")

        return priorities

    def export_report_summary(self, report: Dict[str, Any]) -> str:
        """Export a concise text summary of the report"""

        summary_lines = [
            f"=== Phase 2 Execution Planning Report ===",
            f"Project: {report['metadata']['rs_id']}",
            f"Generated: {report['metadata']['generated_at'][:10]}",
            "",
            "== Executive Summary ==",
            f"Elements Analyzed: {report['executive_summary']['project_overview']['total_elements_analyzed']}",
            f"Project Duration: {report['executive_summary']['project_overview']['estimated_project_duration_days']} days",
            f"Risk Profile: {report['executive_summary']['risk_profile']['risk_distribution']}",
            f"Quality Issues: {report['executive_summary']['construction_feasibility']['quality_issues_identified']}",
            f"Optimization Opportunities: {report['executive_summary']['optimization_opportunities']['high_priority_insights']}",
            "",
            "== Key Recommendations ==",
        ]

        for category, recommendations in report['recommendations'].items():
            if recommendations:
                summary_lines.append(f"{category.replace('_', ' ').title()}:")
                for rec in recommendations:
                    summary_lines.append(f"  - {rec}")
                summary_lines.append("")

        summary_lines.append(f"Overall Assessment: {report['executive_summary']['overall_assessment']}")

        return "\n".join(summary_lines)