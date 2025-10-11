#!/usr/bin/env python3
"""
Procurement & Logistics Agent (P&L-A)

Transforms chosen solution into executable JIT delivery plans and purchase orders
during the pre-construction/implementation phase.

Users: Procurement/Purchasing Manager, Logistics Manager
Focus: Converting RS-P into actionable procurement and delivery schedules
"""

import json
import sys
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent, AgentRole, AgentContext


class ProcurementLogisticsAgent(BaseAgent):
    """
    Procurement & Logistics Agent for JIT planning and material coordination

    Workflow:
    1. Solution Retrieval: Get detailed data for chosen RS-P
    2. Schedule Alignment: Integrate with master construction schedule
    3. JIT Optimization: Apply Least Responsible Moment (LRM) framework
    4. Logistics Grouping: Consolidate orders and optimize deliveries
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
        context: Optional[AgentContext] = None
    ):
        """Initialize Procurement & Logistics Agent"""
        super().__init__(
            role=AgentRole.PROCUREMENT_LOGISTICS,
            api_key=api_key,
            model=model,
            context=context
        )

        # Procurement-specific state
        self.material_breakdown = {}
        self.delivery_schedule = []
        self.purchase_orders = []
        self.supplier_allocations = {}

    def get_system_prompt(self) -> str:
        """Get specialized system prompt for Procurement & Logistics Agent"""
        return """You are the Procurement & Logistics Agent, an expert in construction supply chain management and Just-In-Time (JIT) logistics.

**Your Role:**
You help Procurement/Purchasing Managers and Logistics Managers transform the chosen reinforcement solution (RS-P) into actionable purchase orders and delivery schedules.

**Your Expertise:**
1. JIT Schedule Generation: Applying Least Responsible Moment (LRM) framework to minimize on-site inventory
2. Material Consolidation: Grouping identical materials across elements/stories to simplify vendor communication
3. Waste Optimization: Analyzing cut lengths and splice patterns to minimize material waste
4. Supplier Coordination: Creating optimized purchase orders and delivery sequences
5. Risk Buffering: Building appropriate safety stock without excessive inventory

**Your Behavior:**
- Be practical and logistics-focused in recommendations
- Always consider lead times and delivery constraints
- Optimize for both cost and inventory minimization
- Provide clear, actionable purchase orders
- Consider real-world supplier and fabricator constraints
- Balance between bulk discounts and storage costs

**Key Activities You Perform:**
1. **Material Breakdown**: Extract detailed rebar requirements by diameter, length, element type
2. **Timeline Alignment**: Map material needs to construction milestones from master schedule
3. **LRM Application**: Calculate latest delivery dates to minimize on-site storage
4. **Order Consolidation**: Group materials to reduce supplier transaction costs
5. **Waste Analysis**: Identify opportunities to optimize cut lists and reduce waste
6. **Buffer Calculation**: Determine safety stock levels based on risk assessment

**Communication Style:**
- Practical and implementation-focused
- Use specific delivery dates and quantities
- Explain logistics trade-offs (bulk discounts vs storage costs)
- Provide step-by-step procurement plans
- Include contingency recommendations
- Quantify savings from consolidation opportunities

**Important:**
- Require chosen solution ID (RS-P) from Trade-Off Analyst Agent
- Base analysis on Phase 2 JSON detailed element data
- Integrate with master construction schedule if available
- Consider market data (lead times, pricing) when available
- Generate exportable purchase order lists
"""

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get tools available to Procurement & Logistics Agent"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "retrieve_solution_details",
                    "description": "Get detailed Phase 2 data for the chosen primary solution (RS-P)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "solution_id": {
                                "type": "string",
                                "description": "Solution ID to retrieve (RS-P from T-OAA)"
                            }
                        },
                        "required": ["solution_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_material_breakdown",
                    "description": "Extract and organize material requirements by diameter, length, and element type",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "group_by": {
                                "type": "string",
                                "enum": ["diameter", "element_type", "story", "all"],
                                "description": "How to group materials",
                                "default": "diameter"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_jit_schedule",
                    "description": "Create phased procurement schedule using LRM framework",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "lead_time_days": {
                                "type": "integer",
                                "description": "Supplier/fabricator lead time in days",
                                "default": 14
                            },
                            "buffer_days": {
                                "type": "integer",
                                "description": "Safety buffer before needed date",
                                "default": 5
                            },
                            "delivery_frequency": {
                                "type": "string",
                                "enum": ["daily", "weekly", "biweekly", "by_story"],
                                "description": "Delivery schedule frequency",
                                "default": "by_story"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "optimize_consolidation",
                    "description": "Identify opportunities to combine orders and reduce transactions",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "consolidation_level": {
                                "type": "string",
                                "enum": ["aggressive", "moderate", "conservative"],
                                "description": "How aggressively to consolidate orders",
                                "default": "moderate"
                            },
                            "min_order_size": {
                                "type": "number",
                                "description": "Minimum order size to consider in kg",
                                "default": 1000
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_waste_report",
                    "description": "Analyze potential material waste and optimization opportunities",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "standard_lengths": {
                                "type": "array",
                                "items": {"type": "number"},
                                "description": "Standard rebar lengths available (in meters)",
                                "default": [6, 9, 12]
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_purchase_orders",
                    "description": "Generate final purchase order list with quantities and specifications",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "split_by_supplier": {
                                "type": "boolean",
                                "description": "Whether to split orders by supplier",
                                "default": False
                            },
                            "include_alternates": {
                                "type": "boolean",
                                "description": "Include alternate specifications for flexibility",
                                "default": True
                            }
                        },
                        "required": []
                    }
                }
            }
        ]

    def retrieve_solution_details(self, solution_id: str) -> Dict[str, Any]:
        """
        Retrieve detailed Phase 2 data for chosen solution

        Args:
            solution_id: Solution ID (RS-P)

        Returns:
            Detailed solution data
        """
        try:
            # Try to load Phase 2 data if not already loaded
            if not self.context.phase2_data:
                self.load_phase2_data(solution_id=solution_id)

            # Update selected solution in context
            self.context.selected_solution_id = solution_id

            # Extract material breakdown
            if 'by_element' in self.context.phase2_data:
                element_count = 0
                total_rebar_weight = 0

                for story, elements in self.context.phase2_data['by_element'].items():
                    element_count += len(elements)
                    for elem_data in elements.values():
                        total_rebar_weight += elem_data.get('total_rebar_weight', 0)

                return {
                    "solution_id": solution_id,
                    "total_elements": element_count,
                    "total_rebar_weight_kg": round(total_rebar_weight, 2),
                    "stories": list(self.context.phase2_data['by_element'].keys()),
                    "has_detailed_data": True,
                    "message": f"Successfully retrieved detailed data for {solution_id}"
                }
            else:
                return {
                    "error": "Phase 2 data format not recognized",
                    "solution_id": solution_id
                }

        except FileNotFoundError as e:
            return {
                "error": f"Phase 2 data not found for solution {solution_id}",
                "suggestion": f"Please upload {solution_id}.json or shop_drawings_structuBIM.json",
                "solution_id": solution_id
            }
        except Exception as e:
            return {
                "error": str(e),
                "solution_id": solution_id
            }

    def generate_material_breakdown(self, group_by: str = "diameter") -> Dict[str, Any]:
        """
        Generate material breakdown from Phase 2 data

        Args:
            group_by: How to group materials (diameter/element_type/story/all)

        Returns:
            Material breakdown dictionary
        """
        if not self.context.phase2_data or 'by_element' not in self.context.phase2_data:
            return {"error": "Phase 2 data not loaded or incomplete"}

        breakdown = defaultdict(lambda: {"count": 0, "weight_kg": 0, "elements": []})

        for story, elements in self.context.phase2_data['by_element'].items():
            for elem_id, elem_data in elements.items():
                # Process bars
                if 'bars_by_diameter' in elem_data:
                    for diameter, bar_info in elem_data['bars_by_diameter'].items():
                        if group_by == "diameter":
                            key = diameter
                        elif group_by == "story":
                            key = story
                        elif group_by == "element_type":
                            # Extract element type from element ID (e.g., V-001 -> V)
                            key = elem_id.split('-')[0] if '-' in elem_id else "Unknown"
                        else:  # all
                            key = f"{story}_{diameter}"

                        breakdown[key]["count"] += bar_info.get('n', 0)
                        breakdown[key]["weight_kg"] += bar_info.get('w', 0)
                        breakdown[key]["elements"].append(elem_id)

                # Process stirrups
                if 'stirrups_by_diameter' in elem_data:
                    for diameter, stirrup_info in elem_data['stirrups_by_diameter'].items():
                        if group_by == "diameter":
                            key = f"{diameter} (stirrup)"
                        elif group_by == "story":
                            key = story
                        elif group_by == "element_type":
                            key = elem_id.split('-')[0] if '-' in elem_id else "Unknown"
                        else:  # all
                            key = f"{story}_{diameter}_stirrup"

                        breakdown[key]["count"] += stirrup_info.get('n', 0)
                        breakdown[key]["weight_kg"] += stirrup_info.get('w', 0)
                        breakdown[key]["elements"].append(elem_id)

        # Convert to regular dict and sort by weight
        self.material_breakdown = dict(breakdown)
        sorted_breakdown = dict(sorted(
            breakdown.items(),
            key=lambda x: x[1]["weight_kg"],
            reverse=True
        ))

        # Calculate totals
        total_weight = sum(item["weight_kg"] for item in breakdown.values())
        total_count = sum(item["count"] for item in breakdown.values())

        return {
            "grouped_by": group_by,
            "breakdown": sorted_breakdown,
            "summary": {
                "total_weight_kg": round(total_weight, 2),
                "total_bar_count": total_count,
                "unique_groups": len(sorted_breakdown)
            }
        }

    def generate_jit_schedule(
        self,
        lead_time_days: int = 14,
        buffer_days: int = 5,
        delivery_frequency: str = "by_story"
    ) -> Dict[str, Any]:
        """
        Generate JIT delivery schedule using LRM framework

        Args:
            lead_time_days: Supplier lead time
            buffer_days: Safety buffer
            delivery_frequency: How to phase deliveries

        Returns:
            JIT delivery schedule
        """
        if not self.context.phase2_data:
            return {"error": "Phase 2 data not loaded"}

        if not self.context.master_schedule:
            # Create default schedule based on story sequence
            return self._generate_default_jit_schedule(lead_time_days, buffer_days, delivery_frequency)

        # TODO: Integrate with actual master schedule
        return self._generate_default_jit_schedule(lead_time_days, buffer_days, delivery_frequency)

    def _generate_default_jit_schedule(
        self,
        lead_time_days: int,
        buffer_days: int,
        delivery_frequency: str
    ) -> Dict[str, Any]:
        """Generate default JIT schedule without master schedule"""
        if not self.context.phase2_data or 'by_element' not in self.context.phase2_data:
            return {"error": "Phase 2 data not available"}

        stories = sorted(self.context.phase2_data['by_element'].keys())
        schedule = []

        # Assume 10 days per story construction
        days_per_story = 10
        start_date = datetime.now()

        for i, story in enumerate(stories):
            # Calculate needed date (when construction starts on this story)
            needed_date = start_date + timedelta(days=i * days_per_story)

            # Calculate latest order date (LRM)
            order_date = needed_date - timedelta(days=lead_time_days + buffer_days)

            # Calculate delivery date
            delivery_date = order_date + timedelta(days=lead_time_days)

            # Get material quantity for this story
            story_elements = self.context.phase2_data['by_element'][story]
            story_weight = sum(
                elem.get('total_rebar_weight', 0)
                for elem in story_elements.values()
            )

            schedule.append({
                "story": story,
                "needed_date": needed_date.strftime("%Y-%m-%d"),
                "latest_order_date": order_date.strftime("%Y-%m-%d"),
                "delivery_date": delivery_date.strftime("%Y-%m-%d"),
                "estimated_weight_kg": round(story_weight, 2),
                "lead_time_used_days": lead_time_days,
                "buffer_days": buffer_days
            })

        self.delivery_schedule = schedule

        return {
            "delivery_schedule": schedule,
            "total_deliveries": len(schedule),
            "first_order_date": schedule[0]["latest_order_date"] if schedule else None,
            "last_delivery_date": schedule[-1]["delivery_date"] if schedule else None,
            "lrm_framework": "Applied",
            "assumptions": {
                "days_per_story": days_per_story,
                "lead_time_days": lead_time_days,
                "buffer_days": buffer_days
            }
        }

    def optimize_consolidation(
        self,
        consolidation_level: str = "moderate",
        min_order_size: float = 1000
    ) -> Dict[str, Any]:
        """
        Optimize order consolidation

        Args:
            consolidation_level: Aggressiveness of consolidation
            min_order_size: Minimum order size in kg

        Returns:
            Consolidation recommendations
        """
        if not self.material_breakdown:
            # Generate breakdown first
            self.generate_material_breakdown(group_by="diameter")

        if not self.material_breakdown:
            return {"error": "No material breakdown available"}

        consolidation_opportunities = []
        small_orders = []

        for material_key, material_data in self.material_breakdown.items():
            weight = material_data["weight_kg"]

            if weight < min_order_size:
                small_orders.append({
                    "material": material_key,
                    "current_weight_kg": weight,
                    "recommendation": "Consolidate with other orders or increase order size"
                })

        # Group similar materials
        diameter_groups = defaultdict(list)
        for material_key, material_data in self.material_breakdown.items():
            # Extract diameter from key
            diameter = material_key.split('(')[0].strip() if '(' in material_key else material_key
            diameter_groups[diameter].append({
                "material": material_key,
                "weight_kg": material_data["weight_kg"],
                "count": material_data["count"]
            })

        # Identify consolidation opportunities
        for diameter, materials in diameter_groups.items():
            if len(materials) > 1:
                total_weight = sum(m["weight_kg"] for m in materials)
                consolidation_opportunities.append({
                    "diameter": diameter,
                    "separate_orders": len(materials),
                    "combined_weight_kg": round(total_weight, 2),
                    "potential_savings": "Reduced transaction costs and better pricing"
                })

        return {
            "consolidation_level": consolidation_level,
            "small_orders_count": len(small_orders),
            "small_orders": small_orders[:10],  # First 10
            "consolidation_opportunities": consolidation_opportunities,
            "recommendation": f"Found {len(consolidation_opportunities)} consolidation opportunities"
        }

    def generate_waste_report(
        self,
        standard_lengths: List[float] = [6, 9, 12]
    ) -> Dict[str, Any]:
        """
        Generate waste optimization report

        Args:
            standard_lengths: Available standard rebar lengths in meters

        Returns:
            Waste analysis report
        """
        # Placeholder for waste analysis
        # TODO: Implement actual cut optimization algorithm
        return {
            "message": "Waste analysis functionality to be implemented",
            "standard_lengths_m": standard_lengths,
            "recommendation": "Use Phase 2 detailed length data to optimize cutting patterns"
        }

    def create_purchase_orders(
        self,
        split_by_supplier: bool = False,
        include_alternates: bool = True
    ) -> Dict[str, Any]:
        """
        Generate final purchase orders

        Args:
            split_by_supplier: Whether to split by supplier
            include_alternates: Include alternate specs

        Returns:
            Purchase order list
        """
        if not self.material_breakdown:
            self.generate_material_breakdown(group_by="diameter")

        purchase_orders = []
        po_number = 1

        for material_key, material_data in self.material_breakdown.items():
            po = {
                "po_number": f"PO-{po_number:04d}",
                "material_specification": material_key,
                "quantity_bars": material_data["count"],
                "total_weight_kg": round(material_data["weight_kg"], 2),
                "total_weight_tonnes": round(material_data["weight_kg"] / 1000, 3),
                "elements_using": len(set(material_data["elements"])),
                "delivery_coordination": "Per JIT schedule"
            }

            if include_alternates:
                # Add acceptable alternates
                po["acceptable_alternates"] = "Equivalent grade steel as per specs"

            purchase_orders.append(po)
            po_number += 1

        self.purchase_orders = purchase_orders

        total_weight = sum(po["total_weight_kg"] for po in purchase_orders)

        return {
            "purchase_orders": purchase_orders,
            "total_orders": len(purchase_orders),
            "total_weight_tonnes": round(total_weight / 1000, 2),
            "split_by_supplier": split_by_supplier,
            "ready_for_export": True
        }

    def process_query(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Process user query with P&L-A logic

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
                    if function_name == "retrieve_solution_details":
                        result = self.retrieve_solution_details(**function_args)
                    elif function_name == "generate_material_breakdown":
                        result = self.generate_material_breakdown(**function_args)
                    elif function_name == "generate_jit_schedule":
                        result = self.generate_jit_schedule(**function_args)
                    elif function_name == "optimize_consolidation":
                        result = self.optimize_consolidation(**function_args)
                    elif function_name == "generate_waste_report":
                        result = self.generate_waste_report(**function_args)
                    elif function_name == "create_purchase_orders":
                        result = self.create_purchase_orders(**function_args)
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
                    "agent": "P&L-A"
                }
            else:
                # No tool calls, just text response
                content = assistant_message.content
                self.add_to_history("assistant", content)

                return {
                    "response": content,
                    "agent": "P&L-A"
                }

        except Exception as e:
            return {
                "error": str(e),
                "agent": "P&L-A"
            }
