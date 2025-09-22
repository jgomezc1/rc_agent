"""
Workflow management tools for two-step Phase 1 → Phase 2 process.
Helps users transition from solution selection to execution planning.
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from langchain.tools import StructuredTool

from core_services import DataRouter


# Input schemas for workflow tools
class CheckDataAvailabilityInput(BaseModel):
    """Input schema for checking data availability"""
    rs_id: str = Field(description="Reinforcement solution ID to check")


class ListSolutionsInput(BaseModel):
    """Input schema for listing available solutions"""
    show_details: bool = Field(default=False, description="Show detailed information about each solution")


class PreparePhase2Input(BaseModel):
    """Input schema for Phase 2 preparation guidance"""
    rs_id: str = Field(description="Selected reinforcement solution ID from Phase 1")


def check_phase2_data_availability(rs_id: str) -> str:
    """
    Check if Phase 2 BIM data is available for a specific solution.

    Helps users understand what data is needed to proceed with execution planning
    after Phase 1 solution selection.
    """
    try:
        data_router = DataRouter()
        availability = data_router.check_phase_b_availability(rs_id)

        response_parts = [
            f"=== Phase 2 Data Availability for {rs_id} ===",
            "",
            f"Solution ID: {rs_id}",
            f"Status: {'[READY]' if availability['data_available'] else '[NEEDS DATA]'}",
            "",
            "Data Sources Checked:",
        ]

        # Solution-specific file status
        solution_file = availability["solution_specific_file"]
        status_icon = "[OK]" if solution_file["exists"] else "[MISSING]"
        response_parts.append(f"  {status_icon} Individual file: {solution_file['filename']}")

        # Unified file status
        unified_file = availability["unified_file"]
        status_icon = "[OK]" if unified_file["exists"] else "[MISSING]"
        response_parts.append(f"  {status_icon} Unified file: {unified_file['filename']}")

        response_parts.extend([
            "",
            "Recommendation:",
            f"  {availability['recommended_action']}",
            ""
        ])

        if not availability['data_available']:
            response_parts.extend([
                "Next Steps:",
                f"1. Obtain detailed BIM data for solution {rs_id}",
                f"2. Save it as 'data/{rs_id}.json'",
                f"3. Run Phase 2 analysis tools (risk analysis, crew planning, etc.)",
                "",
                "File Format Expected:",
                "- JSON file with detailed element-level BIM data",
                "- Should contain 'by_element' structure with construction levels",
                "- Include rebar specifications, complexity scores, and geometric data"
            ])
        else:
            response_parts.extend([
                "Ready for Phase 2 Analysis:",
                "- analyze_execution_risks",
                "- plan_construction_sequence",
                "- optimize_procurement_strategy",
                "- validate_construction_quality",
                "- analyze_constructibility_insights",
                "- generate_execution_report"
            ])

        return "\n".join(response_parts)

    except Exception as e:
        return f"Error checking data availability for {rs_id}: {str(e)}"


def list_available_solutions(show_details: bool = False) -> str:
    """
    List all solutions available in Phase 1 and Phase 2 data.

    Shows what solutions can be analyzed and which ones are ready for execution planning.
    """
    try:
        data_router = DataRouter()
        solutions = data_router.list_available_solutions()

        response_parts = [
            "=== Available Solutions Overview ===",
            ""
        ]

        # Phase A solutions
        phase_a_count = len(solutions["phase_a_solutions"])
        response_parts.extend([
            f"Phase 1 Solutions ({phase_a_count} available):",
            "  Source: shop_drawings.json",
            "  Use for: Solution selection, optimization, ranking",
        ])

        if phase_a_count > 0:
            if show_details:
                for sol in solutions["phase_a_solutions"]:
                    response_parts.append(f"    - {sol}")
            else:
                # Show first few and count
                shown = solutions["phase_a_solutions"][:5]
                response_parts.append(f"    - {', '.join(shown)}")
                if phase_a_count > 5:
                    response_parts.append(f"    - ... and {phase_a_count - 5} more")
        else:
            response_parts.append("    - No solutions found in shop_drawings.json")

        response_parts.append("")

        # Phase B solutions (unified file)
        phase_b_count = len(solutions["phase_b_solutions"])
        response_parts.extend([
            f"Phase 2 Solutions - Unified File ({phase_b_count} available):",
            "  Source: shop_drawings_structuBIM.json",
            "  Use for: Execution planning, risk analysis, crew planning",
        ])

        if phase_b_count > 0:
            if show_details:
                for sol in solutions["phase_b_solutions"]:
                    response_parts.append(f"    - {sol}")
            else:
                shown = solutions["phase_b_solutions"][:5]
                response_parts.append(f"    - {', '.join(shown)}")
                if phase_b_count > 5:
                    response_parts.append(f"    - ... and {phase_b_count - 5} more")
        else:
            response_parts.append("    - No unified BIM file found")

        response_parts.append("")

        # Individual solution files
        individual_count = len(solutions["individual_solution_files"])
        response_parts.extend([
            f"Phase 2 Solutions - Individual Files ({individual_count} available):",
            "  Source: Individual [solution_id].json files",
            "  Use for: Targeted execution planning after Phase 1 selection",
        ])

        if individual_count > 0:
            if show_details:
                for sol in solutions["individual_solution_files"]:
                    response_parts.append(f"    - {sol} (from {sol}.json)")
            else:
                shown = solutions["individual_solution_files"][:5]
                response_parts.append(f"    - {', '.join(shown)}")
                if individual_count > 5:
                    response_parts.append(f"    - ... and {individual_count - 5} more")
        else:
            response_parts.append("    - No individual solution files found")

        response_parts.extend([
            "",
            "Workflow Recommendations:",
            f"1. Use Phase 1 tools with any of the {phase_a_count} available solutions",
            "2. Select optimal solution from Phase 1 analysis",
            "3. Check Phase 2 data availability for selected solution",
            "4. Upload individual BIM file if needed (recommended approach)",
            "5. Run Phase 2 execution planning tools"
        ])

        return "\n".join(response_parts)

    except Exception as e:
        return f"Error listing solutions: {str(e)}"


def prepare_phase2_transition(rs_id: str) -> str:
    """
    Provide guidance for transitioning from Phase 1 to Phase 2 analysis.

    Explains next steps after selecting an optimal solution in Phase 1.
    """
    try:
        data_router = DataRouter()

        # Check if solution exists in Phase A
        try:
            phase_a_data = data_router.load_phase_a_data()
            if rs_id not in phase_a_data:
                return f"Solution {rs_id} not found in Phase 1 data. Available solutions: {', '.join(list(phase_a_data.keys())[:5])}"

            selected_solution = phase_a_data[rs_id]
        except Exception as e:
            return f"Error accessing Phase 1 data: {e}"

        # Check Phase 2 data availability
        availability = data_router.check_phase_b_availability(rs_id)

        response_parts = [
            f"=== Phase 1 to Phase 2 Transition Guide ===",
            f"Selected Solution: {rs_id}",
            "",
            "Phase 1 Solution Summary:",
            f"  Steel Tonnage: {selected_solution.steel_tonnage} tonnes",
            f"  Concrete Volume: {selected_solution.concrete_volume} m³",
            f"  Total Cost: ${selected_solution.steel_cost + selected_solution.concrete_cost:,.0f}",
            f"  Duration: {selected_solution.duration_days} days",
            f"  Constructibility: {selected_solution.constructibility_index:.1f}",
            "",
            "Phase 2 Data Status:",
            f"  {availability['recommended_action']}",
            ""
        ]

        if availability['data_available']:
            response_parts.extend([
                "[READY] Ready for Phase 2 Analysis!",
                "",
                "Available Phase 2 Tools:",
                f"  analyze_execution_risks('{rs_id}') - Identify construction risks",
                f"  plan_construction_sequence('{rs_id}') - Generate crew and task plans",
                f"  optimize_procurement_strategy('{rs_id}') - Plan material procurement",
                f"  validate_construction_quality('{rs_id}') - Check design compliance",
                f"  analyze_constructibility_insights('{rs_id}') - Find optimization opportunities",
                f"  generate_execution_report('{rs_id}') - Comprehensive execution plan",
                "",
                "Recommended Workflow:",
                "1. Start with execution risk analysis",
                "2. Generate construction sequence and crew plan",
                "3. Validate quality and check for issues",
                "4. Generate comprehensive execution report",
            ])
        else:
            response_parts.extend([
                "[REQUIRED] Phase 2 Data Required",
                "",
                "To proceed with execution planning, you need detailed BIM data:",
                "",
                "Required File:",
                f"  data/{rs_id}.json",
                "",
                "File Contents Should Include:",
                "- Detailed element-level data (beams, columns, slabs)",
                "- Rebar specifications by diameter and type",
                "- Complexity scores and labor modifiers",
                "- Geometric properties (areas, volumes, weights)",
                "- Construction level organization",
                "",
                "File Structure Example:",
                '{',
                '  "by_element": {',
                '    "Level_1": {',
                '      "Element_ID": {',
                '        "bars_by_diameter": {...},',
                '        "complexity_score": 2.5,',
                '        "surface_area": 15.6,',
                '        "vol_concreto": 3.9,',
                '        // ... other element data',
                '      }',
                '    }',
                '  }',
                '}',
                "",
                "Once uploaded, you can run all Phase 2 analysis tools!"
            ])

        return "\n".join(response_parts)

    except Exception as e:
        return f"Error preparing Phase 2 transition for {rs_id}: {str(e)}"


# Create LangChain tools
workflow_tools = [
    StructuredTool(
        name="check_phase2_data_availability",
        description="Check if Phase 2 BIM data is available for a specific solution selected in Phase 1",
        func=check_phase2_data_availability,
        args_schema=CheckDataAvailabilityInput
    ),
    StructuredTool(
        name="list_available_solutions",
        description="List all solutions available in Phase 1 and Phase 2 data files",
        func=list_available_solutions,
        args_schema=ListSolutionsInput
    ),
    StructuredTool(
        name="prepare_phase2_transition",
        description="Get guidance for transitioning from Phase 1 solution selection to Phase 2 execution planning",
        func=prepare_phase2_transition,
        args_schema=PreparePhase2Input
    )
]