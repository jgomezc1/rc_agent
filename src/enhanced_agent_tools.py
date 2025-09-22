"""
Enhanced agent tools for RC Agent Phase 1 implementation.
Provides LangChain-compatible tools with the new selection and analysis capabilities.
"""

import json
import os
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from langchain.tools import StructuredTool

from core_services import DataRouter, ConstraintManager, DataValidator
from selection_engine import SelectionEngine, SensitivityAnalyzer
from data_models import OptimizationSpec, OptimizationObjective


# Initialize core services
data_router = DataRouter()
selection_engine = SelectionEngine()
constraint_manager = ConstraintManager()


# ---- Input Schemas ----

class SelectSolutionInput(BaseModel):
    """Input for solution selection tool"""
    objective: str = Field(description="Primary objective: 'cost', 'co2', 'duration', 'manhours', or 'constructibility'")
    constraints: List[str] = Field(default=[], description="List of constraints like 'cost <= 450000', 'duration < 70'")
    weights: Optional[str] = Field(default=None, description="JSON string of weights like '{\"cost\": 0.4, \"co2\": 0.3}'")


class ParetoAnalysisInput(BaseModel):
    """Input for Pareto analysis tool"""
    objectives: List[str] = Field(description="List of objectives to analyze: 'cost', 'co2', 'duration', 'manhours', 'constructibility'")
    constraints: List[str] = Field(default=[], description="List of constraints")


class SensitivityAnalysisInput(BaseModel):
    """Input for sensitivity analysis tool"""
    objective: str = Field(description="Primary objective for analysis")
    parameter: str = Field(description="Parameter to test: 'cost', 'co2', 'duration', 'manhours', 'steel_cost'")
    shock_percentage: float = Field(default=0.1, description="Percentage change to test (0.1 = 10%)")
    constraints: List[str] = Field(default=[], description="List of constraints")


class DataValidationInput(BaseModel):
    """Input for data validation tool"""
    data_source: str = Field(default="both", description="Data source to validate: 'phase_a', 'phase_b', or 'both'")


class GenerateReportInput(BaseModel):
    """Input for report generation tool"""
    rs_id: str = Field(description="RS ID to generate detailed report for")
    include_bim: bool = Field(default=False, description="Include BIM-level details if available")


class WhatIfAnalysisInput(BaseModel):
    """Input for what-if analysis tool"""
    parameter_changes: str = Field(description="JSON string of parameter changes like '{\"steel_cost\": 1.1, \"co2\": 0.9}'")
    objective: str = Field(description="Primary objective for analysis")


# ---- Tool Functions ----

def _select_solution(objective: str, constraints: List[str] = None, weights: str = None) -> str:
    """Select optimal solution based on objectives and constraints"""
    try:
        # Load Phase A data
        try:
            scenarios = data_router.load_phase_a_data()
        except FileNotFoundError as e:
            return f"Error: Data file not found. Please ensure 'shop_drawings.json' exists in the data directory.\nDetailed error: {e}"

        selection_engine.load_scenarios(scenarios)

        # Parse weights if provided
        weight_dict = None
        if weights:
            try:
                weight_dict = json.loads(weights)
            except json.JSONDecodeError:
                return f"Error: Invalid weights JSON format: {weights}"

        # Create optimization spec
        spec = constraint_manager.create_optimization_spec(
            primary_objective=objective,
            constraints=constraints or [],
            weights=weight_dict
        )

        # Perform selection
        result = selection_engine.select_solution(spec)

        # Format response
        response = f"""
## Solution Selection Result

**Recommended Solution**: {result.recommended_solution}

**Ranking Summary**:
"""
        for i, score in enumerate(result.all_scores[:5]):  # Top 5
            status = "✓ Feasible" if score.is_feasible else "✗ Infeasible"
            response += f"{i+1}. {score.rs_id} (Score: {score.total_score:.3f}) - {status}\n"

        if result.pareto_optimal:
            response += f"\n**Pareto Optimal Solutions**: {', '.join(result.pareto_optimal)}\n"

        if result.alternatives:
            response += f"\n**Alternative Recommendations**: {', '.join(result.alternatives)}\n"

        response += f"\n**Constraints Applied**: {result.constraints_summary}\n"

        # Add rationale
        response += f"\n{result.rationale}"

        return response

    except Exception as e:
        return f"Error in solution selection: {str(e)}"


def _analyze_pareto_frontier(objectives: List[str], constraints: List[str] = None) -> str:
    """Analyze Pareto frontier across multiple objectives"""
    try:
        # Load data
        scenarios = data_router.load_phase_a_data()
        selection_engine.load_scenarios(scenarios)

        # Analyze for each objective
        results = {}
        pareto_sets = {}

        for obj in objectives:
            spec = constraint_manager.create_optimization_spec(
                primary_objective=obj,
                constraints=constraints or []
            )
            result = selection_engine.select_solution(spec)
            results[obj] = result
            pareto_sets[obj] = set(result.pareto_optimal)

        # Find overall Pareto optimal (intersection)
        if pareto_sets:
            overall_pareto = set.intersection(*pareto_sets.values()) if len(pareto_sets) > 1 else pareto_sets[objectives[0]]
        else:
            overall_pareto = set()

        # Format response
        response = f"""
## Pareto Frontier Analysis

**Objectives Analyzed**: {', '.join(objectives)}

**Individual Pareto Optimal Sets**:
"""
        for obj, pareto_set in pareto_sets.items():
            response += f"- {obj}: {', '.join(sorted(pareto_set))}\n"

        response += f"\n**Overall Pareto Optimal Solutions**: {', '.join(sorted(overall_pareto)) if overall_pareto else 'None'}\n"

        # Performance comparison table
        response += "\n**Performance Comparison**:\n"
        response += "| RS_ID | Cost | CO2 | Duration | Manhours | Constructibility |\n"
        response += "|-------|------|-----|----------|----------|------------------|\n"

        for rs_id in sorted(overall_pareto):
            scenario = scenarios[rs_id]
            response += f"| {rs_id} | ${scenario.total_cost:,.0f} | {scenario.co2_tonnes} | {scenario.duration_days} | {scenario.manhours} | {scenario.constructibility_index:.2f} |\n"

        return response

    except Exception as e:
        return f"Error in Pareto analysis: {str(e)}"


def _perform_sensitivity_analysis(objective: str, parameter: str, shock_percentage: float = 0.1, constraints: List[str] = None) -> str:
    """Perform sensitivity analysis on parameter changes"""
    try:
        # Load data
        scenarios = data_router.load_phase_a_data()
        selection_engine.load_scenarios(scenarios)

        # Create spec
        spec = constraint_manager.create_optimization_spec(
            primary_objective=objective,
            constraints=constraints or []
        )

        # Perform sensitivity analysis
        analyzer = SensitivityAnalyzer(selection_engine)
        result = analyzer.analyze_parameter_sensitivity(spec, parameter, shock_percentage)

        # Format response
        response = f"""
## Sensitivity Analysis Results

**Parameter Tested**: {parameter}
**Shock Applied**: {shock_percentage*100:+.1f}%
**Base Value**: {result.base_value:,.2f}

**Impact Assessment**:
- **Impact Score**: {result.impact_score:.3f} (0 = no change, 1 = maximum change)
- **Sensitivity Level**: {'High' if result.impact_score > 0.3 else 'Medium' if result.impact_score > 0.1 else 'Low'}

**Ranking Changes**:
"""

        for rs_id, change in result.ranking_changes.items():
            if change != 0:
                direction = "↑" if change < 0 else "↓"
                response += f"- {rs_id}: {direction} {abs(change)} positions\n"

        if not any(result.ranking_changes.values()):
            response += "- No ranking changes detected\n"

        response += f"\n**Original Top 3**: {', '.join(result.original_ranking[:3])}\n"
        response += f"**New Top 3**: {', '.join(result.new_ranking[:3])}\n"

        # Recommendation
        if result.impact_score > 0.3:
            response += f"\n⚠️ **High sensitivity detected**: {parameter} changes significantly affect solution ranking. Monitor this parameter closely."
        else:
            response += f"\n✓ **Low sensitivity**: Solution ranking is robust to {parameter} changes."

        return response

    except Exception as e:
        return f"Error in sensitivity analysis: {str(e)}"


def _validate_data(data_source: str = "both") -> str:
    """Validate data integrity and consistency"""
    try:
        reports = []

        if data_source in ["phase_a", "both"]:
            scenarios = data_router.load_phase_a_data()
            report = DataValidator.validate_phase_a_data(scenarios)
            reports.append(("Phase A", report))

        if data_source in ["phase_b", "both"]:
            try:
                # Try to load BIM data for first available RS
                scenarios = data_router.load_phase_a_data()
                if scenarios:
                    first_rs = list(scenarios.keys())[0]
                    bim_data = data_router.load_phase_b_data(first_rs)
                    report = DataValidator.validate_phase_b_data(bim_data)
                    reports.append(("Phase B", report))
            except Exception as e:
                reports.append(("Phase B", f"Error loading BIM data: {str(e)}"))

        # Format response
        response = "## Data Validation Report\n\n"

        for phase_name, report in reports:
            if isinstance(report, str):
                response += f"**{phase_name} Data**: {report}\n\n"
                continue

            response += f"**{phase_name} Data Validation**:\n"
            response += f"- **Status**: {'✓ Valid' if report.is_valid else '✗ Invalid'}\n"

            if report.errors:
                response += "- **Errors**:\n"
                for error in report.errors:
                    response += f"  - {error}\n"

            if report.warnings:
                response += "- **Warnings**:\n"
                for warning in report.warnings:
                    response += f"  - {warning}\n"

            if report.data_summary:
                response += "- **Summary**:\n"
                for key, value in report.data_summary.items():
                    response += f"  - {key}: {value}\n"

            response += "\n"

        return response

    except Exception as e:
        return f"Error in data validation: {str(e)}"


def _generate_detailed_report(rs_id: str, include_bim: bool = False) -> str:
    """Generate detailed report for a specific solution"""
    try:
        # Load Phase A data
        scenarios = data_router.load_phase_a_data()

        if rs_id not in scenarios:
            return f"Error: RS ID '{rs_id}' not found in available solutions: {list(scenarios.keys())}"

        scenario = scenarios[rs_id]

        # Generate basic report
        response = f"""
## Detailed Report: {rs_id}

### Performance Metrics
- **Total Cost**: ${scenario.total_cost:,.0f}
  - Steel Cost: ${scenario.steel_cost:,.0f}
  - Concrete Cost: ${scenario.concrete_cost:,.0f}
- **Duration**: {scenario.duration_days} days
- **Labor**: {scenario.manhours:,} manhours
- **Environmental**: {scenario.co2_tonnes} tonnes CO₂
- **Materials**:
  - Steel: {scenario.steel_tonnage:.1f} tonnes
  - Concrete: {scenario.concrete_volume:,.0f} m³
- **Constructibility Index**: {scenario.constructibility_index:.2f}/5.0
- **Bar Geometries**: {scenario.bar_geometries}

### Cost Analysis
- **Cost per tonne steel**: ${scenario.steel_cost/scenario.steel_tonnage:,.0f}/tonne
- **Cost per m³ concrete**: ${scenario.concrete_cost/scenario.concrete_volume:,.0f}/m³
- **Cost per manhour**: ${scenario.total_cost/scenario.manhours:,.0f}/hour

### Efficiency Metrics
- **Manhours per tonne steel**: {scenario.manhours/scenario.steel_tonnage:.1f} hours/tonne
- **CO₂ per tonne steel**: {scenario.co2_tonnes/scenario.steel_tonnage:.1f} tonnes CO₂/tonne steel
- **Schedule efficiency**: {scenario.steel_tonnage/scenario.duration_days:.1f} tonnes/day
"""

        # Add BIM details if requested
        if include_bim:
            try:
                bim_data = data_router.load_phase_b_data(rs_id)
                response += "\n### BIM-Level Details\n"

                if "by_element" in bim_data:
                    total_elements = 0
                    complex_elements = 0
                    total_rebar = 0

                    for level_name, level_data in bim_data["by_element"].items():
                        response += f"\n#### {level_name}\n"
                        for element_id, element_data in level_data.items():
                            total_elements += 1
                            total_rebar += element_data.get("total_rebar_weight", 0)

                            if element_data.get("complexity_score", 0) > 3.0:
                                complex_elements += 1
                                response += f"- **{element_id}** (High Complexity: {element_data.get('complexity_score', 0):.2f})\n"
                            else:
                                response += f"- {element_id} (Complexity: {element_data.get('complexity_score', 0):.2f})\n"

                    response += f"\n**BIM Summary**:\n"
                    response += f"- Total Elements: {total_elements}\n"
                    response += f"- High Complexity Elements: {complex_elements}\n"
                    response += f"- Total Rebar Weight: {total_rebar:,.1f} kg\n"
                    response += f"- Complexity Ratio: {complex_elements/total_elements*100:.1f}%\n"

            except Exception as e:
                response += f"\n### BIM Data\n❌ BIM data not available: {str(e)}\n"

        return response

    except Exception as e:
        return f"Error generating report: {str(e)}"


def _what_if_analysis(parameter_changes: str, objective: str) -> str:
    """Perform what-if analysis with multiple parameter changes"""
    try:
        # Parse parameter changes
        try:
            changes = json.loads(parameter_changes)
        except json.JSONDecodeError:
            return f"Error: Invalid parameter changes JSON format: {parameter_changes}"

        # Load data
        scenarios = data_router.load_phase_a_data()
        selection_engine.load_scenarios(scenarios)

        # Get original ranking
        spec = constraint_manager.create_optimization_spec(primary_objective=objective)
        original_result = selection_engine.select_solution(spec)
        original_top = original_result.recommended_solution

        # Perform sensitivity analysis for each parameter
        analyzer = SensitivityAnalyzer(selection_engine)
        results = {}

        for param, multiplier in changes.items():
            shock = multiplier - 1.0  # Convert multiplier to shock percentage
            try:
                result = analyzer.analyze_parameter_sensitivity(spec, param, shock)
                results[param] = result
            except Exception as e:
                results[param] = f"Error: {str(e)}"

        # Format response
        response = f"""
## What-If Analysis Results

**Scenario**: {parameter_changes}
**Primary Objective**: {objective}
**Original Best Solution**: {original_top}

### Parameter Impact Summary:
"""

        for param, result in results.items():
            if isinstance(result, str):
                response += f"- **{param}**: {result}\n"
                continue

            new_top = result.new_ranking[0] if result.new_ranking else "None"
            impact_level = "High" if result.impact_score > 0.3 else "Medium" if result.impact_score > 0.1 else "Low"

            response += f"- **{param}** ({changes[param]:.1%}): {impact_level} impact (Score: {result.impact_score:.3f})\n"

            if new_top != original_top:
                response += f"  - 🔄 **New best solution**: {new_top}\n"

        # Overall assessment
        total_impact = sum(r.impact_score for r in results.values() if hasattr(r, 'impact_score'))
        response += f"\n### Overall Assessment:\n"
        response += f"- **Combined Impact Score**: {total_impact:.3f}\n"

        if total_impact > 1.0:
            response += "- 🚨 **High cumulative impact**: These changes significantly affect solution ranking\n"
        elif total_impact > 0.5:
            response += "- ⚠️ **Moderate impact**: Some ranking changes expected\n"
        else:
            response += "- ✅ **Low impact**: Solution ranking remains relatively stable\n"

        return response

    except Exception as e:
        return f"Error in what-if analysis: {str(e)}"


# ---- Structured Tools ----

select_solution = StructuredTool.from_function(
    func=_select_solution,
    name="select_solution",
    description="Select optimal reinforcement solution based on objectives and constraints. Supports multi-objective optimization with Pareto analysis.",
    args_schema=SelectSolutionInput
)

analyze_pareto_frontier = StructuredTool.from_function(
    func=_analyze_pareto_frontier,
    name="analyze_pareto_frontier",
    description="Analyze Pareto-optimal solutions across multiple objectives to find best trade-offs.",
    args_schema=ParetoAnalysisInput
)

perform_sensitivity_analysis = StructuredTool.from_function(
    func=_perform_sensitivity_analysis,
    name="perform_sensitivity_analysis",
    description="Analyze how sensitive solution rankings are to changes in specific parameters.",
    args_schema=SensitivityAnalysisInput
)

validate_data = StructuredTool.from_function(
    func=_validate_data,
    name="validate_data",
    description="Validate data integrity and consistency for Phase A and/or Phase B data sources.",
    args_schema=DataValidationInput
)

generate_detailed_report = StructuredTool.from_function(
    func=_generate_detailed_report,
    name="generate_detailed_report",
    description="Generate comprehensive report for a specific solution including BIM details if available.",
    args_schema=GenerateReportInput
)

what_if_analysis = StructuredTool.from_function(
    func=_what_if_analysis,
    name="what_if_analysis",
    description="Perform what-if analysis with multiple parameter changes to assess cumulative impact.",
    args_schema=WhatIfAnalysisInput
)

# Export all Phase 1 tools
enhanced_tools = [
    select_solution,
    analyze_pareto_frontier,
    perform_sensitivity_analysis,
    validate_data,
    generate_detailed_report,
    what_if_analysis
]