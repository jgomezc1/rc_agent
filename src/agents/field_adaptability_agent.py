#!/usr/bin/env python3
"""
Field Adaptability Agent (F-AA)

Provides real-time problem-solving and maintains construction momentum during
the construction/adaptation phase.

Users: Site Superintendent, Foreman, QC Inspector
Focus: Real-time risk mitigation and solution switching for site execution
"""

import json
import sys
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent, AgentRole, AgentContext


@dataclass
class SiteEvent:
    """Represents a site event or crisis"""
    event_type: str  # 'material_shortage', 'quality_issue', 'schedule_delay'
    affected_element: Optional[str] = None
    affected_story: Optional[str] = None
    description: str = ""
    severity: str = "medium"  # low, medium, high, critical


class FieldAdaptabilityAgent(BaseAgent):
    """
    Field Adaptability Agent for real-time crisis response and adaptation

    Workflow:
    1. Proactive Risk Scan: Review constructability index and flag high-risk elements
    2. Constraint/Crisis Trigger: Detect site events requiring intervention
    3. Alternate Solution Query: Find substitute solutions from Phase 1 data
    4. Net Impact Analysis: Calculate cost/schedule impact of switching
    5. Adaptive Recommendation: Provide actionable directives including mixed-solution options
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
        context: Optional[AgentContext] = None
    ):
        """Initialize Field Adaptability Agent"""
        super().__init__(
            role=AgentRole.FIELD_ADAPTABILITY,
            api_key=api_key,
            model=model,
            context=context
        )

        # Field-specific state
        self.risk_alerts = []
        self.active_crises = []
        self.alternate_solutions = []
        self.mixed_solution_plan = None

    def get_system_prompt(self) -> str:
        """Get specialized system prompt for Field Adaptability Agent"""
        return """You are the Field Adaptability Agent, an expert in construction site problem-solving and crisis management.

**Your Role:**
You help Site Superintendents, Foremen, and QC Inspectors maintain construction momentum when issues arise in the field. You provide real-time solutions to keep the project moving.

**Your Expertise:**
1. Proactive Risk Assessment: Identifying high-risk elements before work begins
2. Crisis Response: Quickly finding alternative solutions when problems occur
3. Mixed-Solution Planning: Recommending floor-by-floor solution switches when needed
4. Impact Analysis: Calculating net cost/schedule impact of changes in real-time
5. Resource Optimization: Finding solutions that work with available materials/crews

**Your Behavior:**
- Be fast and decisive - construction delays are expensive
- Always provide actionable alternatives, never just identify problems
- Quantify impact: Always include cost and time implications
- Consider what's actually available on site or nearby
- Balance between ideal solutions and practical reality
- Prioritize maintaining schedule momentum

**Crisis Types You Handle:**
1. **Material Shortage**: Required rebar diameter unavailable or delayed
2. **Quality Issues**: QC failures requiring rework or design changes
3. **Schedule Pressure**: Need to accelerate specific floors or elements
4. **Crew Constraints**: Labor shortages or skill limitations
5. **Design Conflicts**: Field conditions don't match design

**Your Most Powerful Capability:**
**Mixed-Solution Recommendation** - You can recommend using different solutions for different floors:
- Example: "Use Solution A for Floors 1-5 as planned, switch Floor 6 to Solution B due to material shortage"
- Calculate net project impact across all affected floors
- This is disruptive but keeps project moving

**Key Data You Use:**
- Phase 2 JSON: Constructability Index for proactive risk flagging
- Phase 1 JSON: All available solutions for finding alternates
- Current site conditions: What's actually happening on site
- Chosen RS-P: The baseline plan to deviate from

**Communication Style:**
- Urgent and action-oriented
- Lead with the recommendation, then explain reasoning
- Always include specific numbers: "costs extra $5,000 but saves 3 days"
- Provide step-by-step action plans
- Acknowledge risks of changes
- Clear about which approach you recommend and why

**Example Response Structure:**
1. **Immediate Action**: "Switch Floor 6 to Solution RS-12"
2. **Impact**: "Adds $5,000 cost, saves 3 days fabrication time"
3. **Rationale**: "RS-12 uses 3/4" bar which is available on site now"
4. **Next Steps**: "Order additional 3/4" bar quantities per attached breakdown"
5. **Risks**: "Different splice pattern - brief crew on new procedure"

**Important:**
- Speed is critical - provide recommendations quickly
- Base alternates on Phase 1 data (all solutions)
- Calculate impact using both Phase 1 and Phase 2 data
- Be realistic about site constraints
- Document why changes are necessary for future reference
"""

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get tools available to Field Adaptability Agent"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "scan_proactive_risks",
                    "description": "Scan Phase 2 data for high-risk elements based on constructability index",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "threshold": {
                                "type": "number",
                                "description": "Constructability index threshold (higher = more complex/risky)",
                                "default": 3.0
                            },
                            "story": {
                                "type": "string",
                                "description": "Specific story to scan (optional, scans all if not provided)"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "report_site_event",
                    "description": "Report a site event or crisis requiring intervention",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_type": {
                                "type": "string",
                                "enum": ["material_shortage", "quality_issue", "schedule_delay", "crew_constraint", "design_conflict"],
                                "description": "Type of site event"
                            },
                            "description": {
                                "type": "string",
                                "description": "Detailed description of the issue"
                            },
                            "affected_element": {
                                "type": "string",
                                "description": "Specific element ID affected (e.g., 'V-1585')"
                            },
                            "affected_story": {
                                "type": "string",
                                "description": "Story affected (e.g., 'Level_1')"
                            },
                            "severity": {
                                "type": "string",
                                "enum": ["low", "medium", "high", "critical"],
                                "description": "Severity of the issue",
                                "default": "medium"
                            }
                        },
                        "required": ["event_type", "description"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_alternate_solutions",
                    "description": "Query Phase 1 data to find alternate solutions that solve the constraint",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "constraint": {
                                "type": "string",
                                "description": "The constraint to solve (e.g., 'avoid_7_8_bar', 'faster_than_current', 'cheaper_than_current')"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of alternates to return",
                                "default": 5
                            }
                        },
                        "required": ["constraint"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "calculate_net_impact",
                    "description": "Calculate the net project impact of switching to an alternate solution",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "alternate_solution_id": {
                                "type": "string",
                                "description": "The alternate solution to evaluate (RS-A)"
                            },
                            "scope": {
                                "type": "string",
                                "enum": ["single_element", "single_story", "multiple_stories", "entire_project"],
                                "description": "Scope of the switch",
                                "default": "single_story"
                            },
                            "affected_stories": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of stories affected (for multiple_stories scope)"
                            }
                        },
                        "required": ["alternate_solution_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "recommend_mixed_solution",
                    "description": "Recommend using different solutions for different floors (most disruptive option)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "baseline_solution": {
                                "type": "string",
                                "description": "The current/baseline solution (RS-P)"
                            },
                            "alternate_solution": {
                                "type": "string",
                                "description": "The alternate solution to use for affected floors (RS-A)"
                            },
                            "switch_floors": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of floors/stories to switch to alternate"
                            }
                        },
                        "required": ["baseline_solution", "alternate_solution", "switch_floors"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_action_directive",
                    "description": "Generate detailed action plan for implementing the recommended solution",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "recommendation_type": {
                                "type": "string",
                                "enum": ["continue_as_planned", "switch_all", "switch_partial", "mixed_solution"],
                                "description": "Type of recommendation"
                            }
                        },
                        "required": ["recommendation_type"]
                    }
                }
            }
        ]

    def scan_proactive_risks(
        self,
        threshold: float = 3.0,
        story: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Scan for high-risk elements proactively

        Args:
            threshold: Constructability index threshold
            story: Specific story to scan (optional)

        Returns:
            Dictionary with risk alerts
        """
        if not self.context.phase2_data or 'by_element' not in self.context.phase2_data:
            return {"error": "Phase 2 data not loaded or incomplete"}

        risk_elements = []

        # Determine which stories to scan
        stories_to_scan = [story] if story else self.context.phase2_data['by_element'].keys()

        for story_id in stories_to_scan:
            if story_id not in self.context.phase2_data['by_element']:
                continue

            elements = self.context.phase2_data['by_element'][story_id]

            for elem_id, elem_data in elements.items():
                # Check constructability index (if available)
                const_index = elem_data.get('complexity_score', 0)

                if const_index >= threshold:
                    risk_elements.append({
                        "element_id": elem_id,
                        "story": story_id,
                        "complexity_score": const_index,
                        "total_rebar_weight_kg": elem_data.get('total_rebar_weight', 0),
                        "labor_hours_modifier": elem_data.get('labor_hours_modifier', 1.0),
                        "risk_level": "high" if const_index >= 4.0 else "medium"
                    })

        # Sort by complexity score (highest first)
        risk_elements.sort(key=lambda x: x["complexity_score"], reverse=True)

        self.risk_alerts = risk_elements

        return {
            "risk_elements_found": len(risk_elements),
            "threshold_used": threshold,
            "high_risk_count": len([r for r in risk_elements if r["risk_level"] == "high"]),
            "risk_alerts": risk_elements[:20],  # Top 20 risks
            "recommendation": "Review these elements before starting work - consider simplified backup plans"
        }

    def report_site_event(
        self,
        event_type: str,
        description: str,
        affected_element: Optional[str] = None,
        affected_story: Optional[str] = None,
        severity: str = "medium"
    ) -> Dict[str, Any]:
        """
        Report a site event/crisis

        Args:
            event_type: Type of event
            description: Event description
            affected_element: Affected element ID
            affected_story: Affected story
            severity: Event severity

        Returns:
            Event acknowledgment with next steps
        """
        event = SiteEvent(
            event_type=event_type,
            affected_element=affected_element,
            affected_story=affected_story,
            description=description,
            severity=severity
        )

        self.active_crises.append(event)

        # Generate initial response
        response = {
            "event_logged": True,
            "event_type": event_type,
            "severity": severity,
            "affected_element": affected_element,
            "affected_story": affected_story,
            "description": description,
            "recommended_next_steps": []
        }

        # Provide context-specific recommendations
        if event_type == "material_shortage":
            response["recommended_next_steps"] = [
                "Use find_alternate_solutions to identify solutions using available materials",
                "Calculate net impact of switching to alternate",
                "Consider mixed-solution if only one floor is affected"
            ]
        elif event_type == "quality_issue":
            response["recommended_next_steps"] = [
                "Review constructability index for this element",
                "Find simpler alternate solutions",
                "Calculate rework cost vs switch cost"
            ]
        elif event_type == "schedule_delay":
            response["recommended_next_steps"] = [
                "Find faster alternate solutions from Phase 1 data",
                "Calculate time savings vs cost increase",
                "Consider parallel work strategies"
            ]

        return response

    def find_alternate_solutions(
        self,
        constraint: str,
        max_results: int = 5
    ) -> Dict[str, Any]:
        """
        Find alternate solutions that meet the constraint

        Args:
            constraint: Constraint to solve
            max_results: Max number of results

        Returns:
            List of alternate solutions
        """
        if not self.context.phase1_data:
            return {"error": "Phase 1 data not loaded - cannot find alternates"}

        current_solution_id = self.context.selected_solution_id
        if not current_solution_id:
            return {"error": "No current solution selected (RS-P not set)"}

        # Get current solution metrics
        if current_solution_id not in self.context.phase1_data:
            return {"error": f"Current solution {current_solution_id} not found in Phase 1 data"}

        current_metrics = self.context.phase1_data[current_solution_id]
        current_total_cost = current_metrics.get('steel_cost', 0) + current_metrics.get('concrete_cost', 0)

        alternates = []

        # Parse constraint and filter solutions
        for sol_id, metrics in self.context.phase1_data.items():
            if sol_id == current_solution_id:
                continue  # Skip current solution

            total_cost = metrics.get('steel_cost', 0) + metrics.get('concrete_cost', 0)

            # Apply constraint filters
            matches = False

            if "avoid" in constraint.lower():
                # Example: "avoid_7_8_bar"
                if "7_8" in constraint or "7/8" in constraint:
                    # Check if solution uses different bar range
                    if "7a8" not in sol_id and "7_8" not in sol_id:
                        matches = True
            elif "faster" in constraint.lower():
                if metrics.get('duration_days', 999) < current_metrics.get('duration_days', 999):
                    matches = True
            elif "cheaper" in constraint.lower():
                if total_cost < current_total_cost:
                    matches = True
            elif "simpler" in constraint.lower() or "easier" in constraint.lower():
                if metrics.get('constructibility_index', 999) < current_metrics.get('constructibility_index', 999):
                    matches = True
            elif "lower_co2" in constraint.lower() or "greener" in constraint.lower():
                if metrics.get('co2_tonnes', 999) < current_metrics.get('co2_tonnes', 999):
                    matches = True
            else:
                # Generic match - return all
                matches = True

            if matches:
                alternates.append({
                    "solution_id": sol_id,
                    "total_cost": total_cost,
                    "cost_diff": total_cost - current_total_cost,
                    "cost_diff_pct": ((total_cost - current_total_cost) / current_total_cost * 100) if current_total_cost > 0 else 0,
                    "duration_days": metrics.get('duration_days'),
                    "duration_diff": metrics.get('duration_days', 0) - current_metrics.get('duration_days', 0),
                    "co2_tonnes": metrics.get('co2_tonnes'),
                    "constructibility_index": metrics.get('constructibility_index')
                })

        # Sort by cost increase (prefer minimal cost increase)
        alternates.sort(key=lambda x: x["cost_diff"])

        self.alternate_solutions = alternates[:max_results]

        return {
            "current_solution": current_solution_id,
            "constraint_applied": constraint,
            "alternates_found": len(alternates),
            "top_alternates": self.alternate_solutions,
            "message": f"Found {len(self.alternate_solutions)} alternate solutions matching constraint"
        }

    def calculate_net_impact(
        self,
        alternate_solution_id: str,
        scope: str = "single_story",
        affected_stories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Calculate net impact of switching to alternate solution

        Args:
            alternate_solution_id: Alternate solution ID
            scope: Scope of switch
            affected_stories: Stories affected (for multi-story scope)

        Returns:
            Impact analysis
        """
        if not self.context.phase1_data:
            return {"error": "Phase 1 data not loaded"}

        current_solution_id = self.context.selected_solution_id
        if not current_solution_id:
            return {"error": "No current solution selected"}

        # Get metrics for both solutions
        current = self.context.phase1_data.get(current_solution_id, {})
        alternate = self.context.phase1_data.get(alternate_solution_id, {})

        if not alternate:
            return {"error": f"Alternate solution {alternate_solution_id} not found"}

        # Calculate total costs
        current_total_cost = current.get('steel_cost', 0) + current.get('concrete_cost', 0)
        alternate_total_cost = alternate.get('steel_cost', 0) + alternate.get('concrete_cost', 0)

        # Estimate impact based on scope
        scope_multiplier = {
            "single_element": 0.05,  # ~5% of project
            "single_story": 0.1,     # ~10% of project
            "multiple_stories": 0.3,  # ~30% of project
            "entire_project": 1.0     # 100% of project
        }.get(scope, 0.1)

        # If specific stories provided, calculate more accurate multiplier
        if affected_stories and self.context.phase2_data and 'by_element' in self.context.phase2_data:
            total_stories = len(self.context.phase2_data['by_element'])
            scope_multiplier = len(affected_stories) / total_stories if total_stories > 0 else 0.1

        # Calculate net impact
        net_cost_impact = (alternate_total_cost - current_total_cost) * scope_multiplier
        net_duration_impact = (alternate.get('duration_days', 0) - current.get('duration_days', 0)) * scope_multiplier
        net_co2_impact = (alternate.get('co2_tonnes', 0) - current.get('co2_tonnes', 0)) * scope_multiplier

        return {
            "current_solution": current_solution_id,
            "alternate_solution": alternate_solution_id,
            "scope": scope,
            "scope_multiplier": scope_multiplier,
            "affected_stories": affected_stories,
            "net_impact": {
                "cost_change_usd": round(net_cost_impact, 2),
                "duration_change_days": round(net_duration_impact, 1),
                "co2_change_tonnes": round(net_co2_impact, 2)
            },
            "full_solution_comparison": {
                "current_total_cost": current_total_cost,
                "alternate_total_cost": alternate_total_cost,
                "current_duration": current.get('duration_days'),
                "alternate_duration": alternate.get('duration_days')
            },
            "recommendation": "Consider this switch" if abs(net_cost_impact) < 10000 else "Significant cost impact - evaluate carefully"
        }

    def recommend_mixed_solution(
        self,
        baseline_solution: str,
        alternate_solution: str,
        switch_floors: List[str]
    ) -> Dict[str, Any]:
        """
        Recommend mixed-solution approach (most disruptive)

        Args:
            baseline_solution: Current solution (RS-P)
            alternate_solution: Solution for affected floors (RS-A)
            switch_floors: Floors to switch

        Returns:
            Mixed-solution recommendation
        """
        if not self.context.phase1_data:
            return {"error": "Phase 1 data not loaded"}

        # Calculate impact for switched floors
        impact = self.calculate_net_impact(
            alternate_solution_id=alternate_solution,
            scope="multiple_stories",
            affected_stories=switch_floors
        )

        # Create mixed solution plan
        mixed_plan = {
            "strategy": "Mixed-Solution",
            "baseline_solution": baseline_solution,
            "baseline_floors": "All floors except specified",
            "alternate_solution": alternate_solution,
            "switched_floors": switch_floors,
            "net_impact": impact.get("net_impact", {}),
            "warning": "This is a disruptive change - requires clear communication to all teams",
            "action_items": [
                f"Update procurement to order materials for {alternate_solution} for floors: {', '.join(switch_floors)}",
                "Brief construction crew on different installation procedures for switched floors",
                "Update QC checklists for affected floors",
                "Revise delivery schedule to accommodate mixed materials",
                "Document change order and reasons for project records"
            ]
        }

        self.mixed_solution_plan = mixed_plan

        return mixed_plan

    def generate_action_directive(
        self,
        recommendation_type: str
    ) -> Dict[str, Any]:
        """
        Generate detailed action plan

        Args:
            recommendation_type: Type of recommendation

        Returns:
            Action directive
        """
        if recommendation_type == "mixed_solution" and self.mixed_solution_plan:
            return {
                "directive": "IMPLEMENT MIXED-SOLUTION",
                "plan": self.mixed_solution_plan,
                "priority": "HIGH",
                "timeline": "Implement before next affected floor begins"
            }
        elif recommendation_type == "switch_all" and self.alternate_solutions:
            return {
                "directive": "SWITCH ENTIRE PROJECT",
                "new_solution": self.alternate_solutions[0]["solution_id"] if self.alternate_solutions else "Not specified",
                "priority": "CRITICAL",
                "timeline": "Requires project-wide coordination"
            }
        else:
            return {
                "directive": "CONTINUE AS PLANNED",
                "message": "No changes recommended at this time"
            }

    def process_query(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Process user query with F-AA logic

        Args:
            query: User question or command
            **kwargs: Additional parameters

        Returns:
            Agent response dictionary
        """
        # Add user query to history
        self.add_to_history("user", query)

        # Prepare messages for LLM
        messages = [
            {"role": "system", "content": self.get_system_prompt()}
        ] + self.conversation_history

        # Call LLM with tools
        try:
            response = self.call_llm(
                messages=messages,
                tools=self.get_tools(),
                temperature=0.7,
                max_tokens=2000
            )

            # Process response
            assistant_message = response.choices[0].message

            # Check if tool calls were made
            if assistant_message.tool_calls:
                # Execute tool calls
                tool_results = []
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    # Execute the appropriate function
                    if function_name == "scan_proactive_risks":
                        result = self.scan_proactive_risks(**function_args)
                    elif function_name == "report_site_event":
                        result = self.report_site_event(**function_args)
                    elif function_name == "find_alternate_solutions":
                        result = self.find_alternate_solutions(**function_args)
                    elif function_name == "calculate_net_impact":
                        result = self.calculate_net_impact(**function_args)
                    elif function_name == "recommend_mixed_solution":
                        result = self.recommend_mixed_solution(**function_args)
                    elif function_name == "generate_action_directive":
                        result = self.generate_action_directive(**function_args)
                    else:
                        result = {"error": f"Unknown function: {function_name}"}

                    tool_results.append({
                        "function": function_name,
                        "result": result
                    })

                # Add tool results to history and get final response
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": assistant_message.tool_calls
                })

                for i, tool_call in enumerate(assistant_message.tool_calls):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_results[i]["result"])
                    })

                # Get final response
                final_response = self.call_llm(messages=messages)
                final_content = final_response.choices[0].message.content

                self.add_to_history("assistant", final_content)

                return {
                    "response": final_content,
                    "tool_calls": tool_results,
                    "agent": "F-AA"
                }
            else:
                # No tool calls, just text response
                content = assistant_message.content
                self.add_to_history("assistant", content)

                return {
                    "response": content,
                    "agent": "F-AA"
                }

        except Exception as e:
            return {
                "error": str(e),
                "agent": "F-AA"
            }
