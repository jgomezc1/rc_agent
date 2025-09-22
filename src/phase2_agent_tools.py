"""
Phase 2 LangChain tools for execution planning and analysis.
Integrates all Phase 2 engines with the LangChain agent framework.
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from langchain.tools import StructuredTool

from risk_radar import RiskRadar
from crew_planner import CrewPlanner
from procurement_system import ProcurementOptimizer
from qa_qc_engine import QualityValidator
from constructibility_engine import ConstructibilityAnalyzer
from phase2_reporting import Phase2Reporter


# Input schemas for Phase 2 tools
class RiskAnalysisInput(BaseModel):
    """Input schema for risk analysis"""
    rs_id: str = Field(description="Reinforcement solution ID to analyze")
    include_mitigation: bool = Field(default=True, description="Include mitigation suggestions")


class CrewPlanningInput(BaseModel):
    """Input schema for crew planning"""
    rs_id: str = Field(description="Reinforcement solution ID to plan")
    target_duration_days: Optional[float] = Field(default=None, description="Target project duration in days")
    crew_size_constraint: Optional[int] = Field(default=None, description="Maximum crew size constraint")


class ProcurementPlanningInput(BaseModel):
    """Input schema for procurement planning"""
    rs_id: str = Field(description="Reinforcement solution ID to plan procurement for")
    delivery_buffer_days: Optional[float] = Field(default=3.0, description="Buffer days for delivery scheduling")
    supplier_preference: Optional[str] = Field(default=None, description="Preferred supplier (primary/secondary/local)")


class QualityValidationInput(BaseModel):
    """Input schema for quality validation"""
    rs_id: str = Field(description="Reinforcement solution ID to validate")
    strict_mode: bool = Field(default=False, description="Enable strict validation mode")


class ConstructibilityAnalysisInput(BaseModel):
    """Input schema for constructibility analysis"""
    rs_id: str = Field(description="Reinforcement solution ID to analyze")
    focus_area: Optional[str] = Field(default=None, description="Focus area (standardization/sequencing/complexity)")


class ExecutionReportInput(BaseModel):
    """Input schema for execution report generation"""
    rs_id: str = Field(description="Reinforcement solution ID to generate report for")
    include_detailed_analysis: bool = Field(default=True, description="Include detailed analysis sections")
    export_summary: bool = Field(default=False, description="Export text summary")


def analyze_execution_risks(rs_id: str, include_mitigation: bool = True) -> str:
    """
    Analyze construction execution risks for a reinforcement solution.

    Identifies potential risks, bottlenecks, and issues that could impact construction execution.
    Provides risk scores, delay estimates, and mitigation suggestions.
    """
    try:
        risk_radar = RiskRadar()
        risks = risk_radar.analyze_solution_risks(rs_id)

        if not risks:
            return f"No elements found for risk analysis in solution {rs_id}"

        # Generate risk summary
        risk_summary = risk_radar.generate_risk_summary(risks)
        critical_path_risks = risk_radar.identify_critical_path_risks(risks)

        # Format response
        response_parts = [
            f"=== Risk Analysis for Solution {rs_id} ===",
            f"Total Elements Analyzed: {risk_summary['total_elements']}",
            f"Average Risk Score: {risk_summary['average_risk_score']}",
            f"Total Delay Potential: {risk_summary['total_delay_potential_days']} days",
            f"Critical Path Risks: {len(critical_path_risks)} elements",
            "",
            "Risk Distribution:",
        ]

        for level, count in risk_summary['risk_distribution'].items():
            percentage = risk_summary['risk_level_percentages'][level]
            response_parts.append(f"  {level}: {count} elements ({percentage}%)")

        # Top 5 highest risk elements
        response_parts.extend([
            "",
            "Top 5 Risk Elements:",
        ])

        for i, risk in enumerate(risks[:5]):
            response_parts.append(
                f"  {i+1}. {risk.element_id} ({risk.level_name}) - "
                f"{risk.risk_level.value} risk, {risk.estimated_delay_days:.1f} day delay potential"
            )
            if include_mitigation and risk.mitigation_suggestions:
                response_parts.append(f"     Mitigation: {risk.mitigation_suggestions[0]}")

        if critical_path_risks:
            response_parts.extend([
                "",
                "Critical Path Risk Elements:",
                ", ".join(critical_path_risks)
            ])

        return "\n".join(response_parts)

    except Exception as e:
        return f"Error analyzing risks for {rs_id}: {str(e)}"


def plan_construction_sequence(rs_id: str, target_duration_days: Optional[float] = None,
                              crew_size_constraint: Optional[int] = None) -> str:
    """
    Generate construction sequence and crew planning for a reinforcement solution.

    Creates optimized task sequences, crew assignments, and construction timeline.
    Considers dependencies, resource constraints, and efficiency optimization.
    """
    try:
        crew_planner = CrewPlanner()
        crew_plan = crew_planner.generate_construction_plan(
            rs_id,
            target_duration=target_duration_days,
            max_crew_size=crew_size_constraint
        )

        if not crew_plan:
            return f"Unable to generate construction plan for solution {rs_id}"

        # Format response
        response_parts = [
            f"=== Construction Plan for Solution {rs_id} ===",
            f"Estimated Duration: {crew_plan.get('total_duration_days', 0):.1f} days",
            f"Peak Crew Size: {crew_plan.get('peak_crew_size', 0)} workers",
            f"Total Labor Hours: {crew_plan.get('total_labor_hours', 0):.0f} hours",
            "",
        ]

        # Task breakdown
        tasks = crew_plan.get('tasks', [])
        if tasks:
            response_parts.extend([
                f"Construction Tasks ({len(tasks)} total):",
            ])

            for i, task in enumerate(tasks[:10]):  # Show first 10 tasks
                response_parts.append(
                    f"  {i+1}. {task.get('task_type', 'Unknown')} - "
                    f"{task.get('duration_days', 0):.1f} days, "
                    f"{task.get('crew_size', 0)} workers"
                )

            if len(tasks) > 10:
                response_parts.append(f"  ... and {len(tasks) - 10} more tasks")

        # Crew requirements
        crew_reqs = crew_plan.get('crew_requirements', {})
        if crew_reqs:
            response_parts.extend([
                "",
                "Crew Requirements:",
            ])
            for role, count in crew_reqs.items():
                response_parts.append(f"  {role}: {count}")

        # Critical path
        critical_path = crew_plan.get('critical_path', [])
        if critical_path:
            response_parts.extend([
                "",
                f"Critical Path ({len(critical_path)} tasks):",
                ", ".join(critical_path[:5]) + ("..." if len(critical_path) > 5 else "")
            ])

        # Scheduling insights
        insights = crew_plan.get('scheduling_insights', [])
        if insights:
            response_parts.extend([
                "",
                "Scheduling Insights:",
            ])
            for insight in insights[:3]:
                response_parts.append(f"  - {insight}")

        return "\n".join(response_parts)

    except Exception as e:
        return f"Error generating construction plan for {rs_id}: {str(e)}"


def optimize_procurement_strategy(rs_id: str, delivery_buffer_days: float = 3.0,
                                 supplier_preference: Optional[str] = None) -> str:
    """
    Optimize procurement strategy and delivery scheduling for a reinforcement solution.

    Creates supplier allocation, delivery schedules, and inventory management plans.
    Considers cost optimization, risk diversification, and just-in-time delivery.
    """
    try:
        procurement_optimizer = ProcurementOptimizer()
        procurement_plan = procurement_optimizer.optimize_procurement(
            rs_id,
            delivery_buffer_days=delivery_buffer_days,
            preferred_supplier_type=supplier_preference
        )

        if not procurement_plan:
            return f"Unable to generate procurement plan for solution {rs_id}"

        # Format response
        response_parts = [
            f"=== Procurement Strategy for Solution {rs_id} ===",
            f"Total Procurement Cost: ${procurement_plan.get('total_cost', 0):,.2f}",
            f"Number of Suppliers: {len(procurement_plan.get('suppliers', []))}",
            f"Total Deliveries: {len(procurement_plan.get('delivery_schedule', []))}",
            "",
        ]

        # Supplier breakdown
        suppliers = procurement_plan.get('suppliers', [])
        if suppliers:
            response_parts.extend([
                "Supplier Allocation:",
            ])
            for supplier in suppliers[:5]:  # Show first 5 suppliers
                response_parts.append(
                    f"  {supplier.get('name', 'Unknown')}: "
                    f"${supplier.get('total_cost', 0):,.2f} "
                    f"({supplier.get('percentage', 0):.1f}% of total)"
                )

        # Delivery schedule summary
        deliveries = procurement_plan.get('delivery_schedule', [])
        if deliveries:
            response_parts.extend([
                "",
                f"Delivery Schedule ({len(deliveries)} deliveries):",
            ])

            # Group by week
            weekly_deliveries = {}
            for delivery in deliveries:
                week = delivery.get('week', 'Unknown')
                if week not in weekly_deliveries:
                    weekly_deliveries[week] = 0
                weekly_deliveries[week] += 1

            for week, count in list(weekly_deliveries.items())[:4]:
                response_parts.append(f"  Week {week}: {count} deliveries")

        # Cost optimization insights
        bulk_savings = procurement_plan.get('bulk_savings', 0)
        if bulk_savings > 0:
            response_parts.append(f"")
            response_parts.append(f"Bulk Purchase Savings: ${bulk_savings:,.2f}")

        # Supply chain insights
        insights = procurement_plan.get('supply_chain_insights', [])
        if insights:
            response_parts.extend([
                "",
                "Supply Chain Insights:",
            ])
            for insight in insights[:3]:
                response_parts.append(f"  - {insight}")

        return "\n".join(response_parts)

    except Exception as e:
        return f"Error optimizing procurement for {rs_id}: {str(e)}"


def validate_construction_quality(rs_id: str, strict_mode: bool = False) -> str:
    """
    Validate construction quality and identify potential issues for a reinforcement solution.

    Performs automated quality checks on design compliance, constructibility, and safety.
    Identifies violations, warnings, and provides corrective recommendations.
    """
    try:
        quality_validator = QualityValidator()
        quality_checks = quality_validator.validate_solution(rs_id, strict_mode=strict_mode)

        if not quality_checks:
            return f"No quality issues found for solution {rs_id}"

        # Categorize checks
        failures = [q for q in quality_checks if q.status.value == 'FAIL']
        warnings = [q for q in quality_checks if q.status.value == 'WARNING']
        passes = [q for q in quality_checks if q.status.value == 'PASS']

        # Format response
        response_parts = [
            f"=== Quality Validation for Solution {rs_id} ===",
            f"Total Checks: {len(quality_checks)}",
            f"Passed: {len(passes)}",
            f"Warnings: {len(warnings)}",
            f"Failed: {len(failures)}",
            f"Pass Rate: {(len(passes) / len(quality_checks) * 100):.1f}%",
            "",
        ]

        # Critical failures
        if failures:
            response_parts.extend([
                f"CRITICAL ISSUES ({len(failures)}):",
            ])
            for failure in failures[:5]:  # Show first 5 failures
                response_parts.append(f"  ❌ {failure.element_id}: {failure.message}")
                if failure.recommended_action:
                    response_parts.append(f"     Action: {failure.recommended_action}")

            if len(failures) > 5:
                response_parts.append(f"  ... and {len(failures) - 5} more critical issues")

        # Warnings
        if warnings:
            response_parts.extend([
                "",
                f"WARNINGS ({len(warnings)}):",
            ])
            for warning in warnings[:3]:  # Show first 3 warnings
                response_parts.append(f"  ⚠️  {warning.element_id}: {warning.message}")
                if warning.recommended_action:
                    response_parts.append(f"     Suggestion: {warning.recommended_action}")

        # Overall assessment
        if len(failures) > 0:
            assessment = "ATTENTION REQUIRED - Critical issues must be resolved before construction"
        elif len(warnings) > len(quality_checks) * 0.3:
            assessment = "REVIEW RECOMMENDED - Multiple warnings require attention"
        elif len(warnings) > 0:
            assessment = "GOOD - Minor warnings, construction can proceed with monitoring"
        else:
            assessment = "EXCELLENT - All quality checks passed"

        response_parts.extend([
            "",
            f"Overall Assessment: {assessment}"
        ])

        return "\n".join(response_parts)

    except Exception as e:
        return f"Error validating quality for {rs_id}: {str(e)}"


def analyze_constructibility_insights(rs_id: str, focus_area: Optional[str] = None) -> str:
    """
    Analyze constructibility and identify optimization opportunities for a reinforcement solution.

    Provides design optimization suggestions, standardization opportunities, and efficiency improvements.
    Includes implementation roadmaps and estimated savings.
    """
    try:
        constructibility_analyzer = ConstructibilityAnalyzer()
        insights = constructibility_analyzer.analyze_constructibility(rs_id, focus_area=focus_area)

        if not insights:
            return f"No constructibility insights generated for solution {rs_id}"

        # Categorize insights
        high_priority = [i for i in insights if i.priority.value == 'HIGH']
        medium_priority = [i for i in insights if i.priority.value == 'MEDIUM']
        low_priority = [i for i in insights if i.priority.value == 'LOW']

        total_savings = sum(i.estimated_savings_hours for i in insights)

        # Format response
        response_parts = [
            f"=== Constructibility Analysis for Solution {rs_id} ===",
            f"Total Insights: {len(insights)}",
            f"High Priority: {len(high_priority)}",
            f"Medium Priority: {len(medium_priority)}",
            f"Potential Labor Savings: {total_savings:.1f} hours",
            "",
        ]

        # High priority insights
        if high_priority:
            response_parts.extend([
                "HIGH PRIORITY OPTIMIZATIONS:",
            ])
            for insight in high_priority[:3]:  # Show first 3
                response_parts.append(f"  🔴 {insight.title}")
                response_parts.append(f"     {insight.description}")
                response_parts.append(f"     Savings: {insight.estimated_savings_hours:.1f} hours")
                if insight.implementation_steps:
                    response_parts.append(f"     Next Step: {insight.implementation_steps[0]}")
                response_parts.append("")

        # Medium priority insights
        if medium_priority:
            response_parts.extend([
                "MEDIUM PRIORITY OPTIMIZATIONS:",
            ])
            for insight in medium_priority[:2]:  # Show first 2
                response_parts.append(f"  🟡 {insight.title}")
                response_parts.append(f"     {insight.description}")
                response_parts.append(f"     Savings: {insight.estimated_savings_hours:.1f} hours")
                response_parts.append("")

        # Quick implementation opportunities
        quick_wins = [i for i in insights if len(i.implementation_steps) <= 2 and i.estimated_savings_hours > 0]
        if quick_wins:
            response_parts.extend([
                "QUICK WIN OPPORTUNITIES:",
            ])
            for win in quick_wins[:3]:
                response_parts.append(f"  ⚡ {win.title} ({win.estimated_savings_hours:.1f}h savings)")

        # Implementation roadmap
        if high_priority:
            response_parts.extend([
                "",
                "IMPLEMENTATION ROADMAP:",
                "1. Address high-priority optimizations first",
                "2. Implement quick wins during planning phase",
                "3. Consider medium-priority items for future phases"
            ])

        return "\n".join(response_parts)

    except Exception as e:
        return f"Error analyzing constructibility for {rs_id}: {str(e)}"


def generate_execution_report(rs_id: str, include_detailed_analysis: bool = True,
                             export_summary: bool = False) -> str:
    """
    Generate comprehensive execution planning report combining all Phase 2 analyses.

    Creates a complete report integrating risk analysis, crew planning, procurement,
    quality validation, and constructibility insights with actionable recommendations.
    """
    try:
        reporter = Phase2Reporter()
        report = reporter.generate_execution_report(rs_id, include_detailed_analysis)

        if export_summary:
            return reporter.export_report_summary(report)

        # Format comprehensive response
        response_parts = [
            f"=== Comprehensive Execution Report for Solution {rs_id} ===",
            f"Generated: {report['metadata']['generated_at'][:19]}",
            "",
            "EXECUTIVE SUMMARY:",
            f"  Elements Analyzed: {report['executive_summary']['project_overview']['total_elements_analyzed']}",
            f"  Project Duration: {report['executive_summary']['project_overview']['estimated_project_duration_days']} days",
            f"  Peak Crew Size: {report['executive_summary']['project_overview']['peak_crew_size']} workers",
            f"  Procurement Value: ${report['executive_summary']['project_overview']['total_procurement_value']:,.2f}",
            "",
            "RISK PROFILE:",
            f"  Critical Risks: {report['executive_summary']['risk_profile']['critical_risk_elements']}",
            f"  High Risks: {report['executive_summary']['risk_profile']['high_risk_elements']}",
            f"  Total Delay Potential: {report['executive_summary']['risk_profile']['total_delay_potential_days']} days",
            "",
            "QUALITY STATUS:",
            f"  Quality Issues: {report['executive_summary']['construction_feasibility']['quality_issues_identified']}",
            f"  Quality Warnings: {report['executive_summary']['construction_feasibility']['quality_warnings']}",
            f"  Complexity Rating: {report['executive_summary']['construction_feasibility']['construction_complexity_rating']}",
            "",
            "OPTIMIZATION OPPORTUNITIES:",
            f"  High Priority Insights: {report['executive_summary']['optimization_opportunities']['high_priority_insights']}",
            f"  Potential Savings: {report['executive_summary']['optimization_opportunities']['potential_labor_savings_hours']} hours",
            "",
            "KEY RECOMMENDATIONS:",
        ]

        # Add recommendations by category
        for category, recommendations in report['recommendations'].items():
            if recommendations:
                response_parts.append(f"  {category.replace('_', ' ').title()}:")
                for rec in recommendations[:2]:  # Limit to 2 per category
                    response_parts.append(f"    - {rec}")

        response_parts.extend([
            "",
            f"OVERALL ASSESSMENT:",
            f"  {report['executive_summary']['overall_assessment']}",
            "",
            "For detailed analysis, set include_detailed_analysis=True",
            "For text summary export, set export_summary=True"
        ])

        return "\n".join(response_parts)

    except Exception as e:
        return f"Error generating execution report for {rs_id}: {str(e)}"


# Create LangChain tools
phase2_tools = [
    StructuredTool(
        name="analyze_execution_risks",
        description="Analyze construction execution risks for a reinforcement solution",
        func=analyze_execution_risks,
        args_schema=RiskAnalysisInput
    ),
    StructuredTool(
        name="plan_construction_sequence",
        description="Generate construction sequence and crew planning for a reinforcement solution",
        func=plan_construction_sequence,
        args_schema=CrewPlanningInput
    ),
    StructuredTool(
        name="optimize_procurement_strategy",
        description="Optimize procurement strategy and delivery scheduling for a reinforcement solution",
        func=optimize_procurement_strategy,
        args_schema=ProcurementPlanningInput
    ),
    StructuredTool(
        name="validate_construction_quality",
        description="Validate construction quality and identify potential issues for a reinforcement solution",
        func=validate_construction_quality,
        args_schema=QualityValidationInput
    ),
    StructuredTool(
        name="analyze_constructibility_insights",
        description="Analyze constructibility and identify optimization opportunities for a reinforcement solution",
        func=analyze_constructibility_insights,
        args_schema=ConstructibilityAnalysisInput
    ),
    StructuredTool(
        name="generate_execution_report",
        description="Generate comprehensive execution planning report combining all Phase 2 analyses",
        func=generate_execution_report,
        args_schema=ExecutionReportInput
    )
]