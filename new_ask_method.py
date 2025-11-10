    def ask(self, user_prompt: str) -> str:
        """Process user request with OpenAI function calling and tool execution."""

        # Build system message
        system_message = f"""You are the ProDet+StructuBIM Logistics Agent.

You create high-leverage logistics intelligence and operations plans for reinforced concrete construction.

NON-NEGOTIABLE CONSTRAINTS:
- NO design changes - bars are pre-cut and bent, never modify geometry
- Contiguous construction - build from lower floors upward
- All optimization is logistics/sequence/space only

{self.logistics_summary}

YOUR CAPABILITIES:
1. Dynamic yard planning (2D layouts, slotting, space-time optimization)
2. Inventory forecasting (rolling demand, stockout risk, saturation curves)
3. Congestion-aware installation sequencing (rank hard installs, micro-playbooks)
4. Micro-training & task cards (element-specific, <2min read)
5. Exception handling (missing bundles, crane down, resequencing)
6. Stakeholder communications (supplier, site lead, PM briefs)
7. What-if logistics scenarios (weather, delays, crane changes)
8. Cross-project learning (capture outcomes, suggest templates)

TOOLS AVAILABLE:
You have access to the following tools via function calling:
- analyze_congestion: Identify most congested elements in a floor range
- generate_yard_layout: Create yard layout diagram PDF
- generate_crane_safety: Create crane safety guidelines PDF
- generate_unloading_schedule: Create truck unloading schedule Excel
- generate_zone_allocation: Create zone allocation map PDF with floor filtering

Use these tools whenever they would help answer the user's request.

RESPONSE GUIDELINES:
- Be operational, concise, visual
- Quantify everything: handling touches, hook utilization, stockout risk, etc.
- Be decisive - recommend one option with clear reasoning
- Use tools proactively when they add value
- If data is missing, state assumptions explicitly

Answer the user's request with actionable logistics intelligence.
"""

        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": user_prompt
        })

        # Build messages
        messages = [
            {"role": "system", "content": system_message}
        ] + self.conversation_history

        # Track tool results
        tool_results = []

        try:
            # Initial API call with function calling
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=2000
            )

            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

            # If AI wants to use tools
            if tool_calls:
                # Add AI's message to conversation
                messages.append(response_message)

                # Execute each tool call
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    print(f"\n[TOOL CALL] {function_name} with args: {function_args}")

                    # Execute the appropriate function
                    if function_name == "analyze_congestion":
                        result = self.analyze_congestion(
                            floor_start=function_args.get('floor_start'),
                            floor_end=function_args.get('floor_end'),
                            top_n=function_args.get('top_n', 10)
                        )
                        function_response = json.dumps(result)

                    elif function_name == "generate_yard_layout":
                        filepath = self.generate_yard_layout(
                            filename=function_args.get('filename')
                        )
                        function_response = json.dumps({
                            "status": "success",
                            "filepath": str(filepath),
                            "message": "Yard layout PDF generated successfully"
                        })
                        tool_results.append(f"Yard Layout: {filepath}")

                    elif function_name == "generate_crane_safety":
                        filepath = self.generate_crane_safety(
                            filename=function_args.get('filename')
                        )
                        function_response = json.dumps({
                            "status": "success",
                            "filepath": str(filepath),
                            "message": "Crane safety guidelines PDF generated successfully"
                        })
                        tool_results.append(f"Crane Safety Guidelines: {filepath}")

                    elif function_name == "generate_unloading_schedule":
                        trucks, bundles = self._create_sample_unloading_data()
                        filepath = self.generate_unloading_schedule(
                            trucks=trucks,
                            bundles=bundles,
                            filename=function_args.get('filename')
                        )
                        function_response = json.dumps({
                            "status": "success",
                            "filepath": str(filepath),
                            "message": "Unloading schedule Excel generated successfully"
                        })
                        tool_results.append(f"Unloading Schedule: {filepath}")

                    elif function_name == "generate_zone_allocation":
                        zones = self._create_default_zones()
                        floor_range = None
                        if function_args.get('floor_start') and function_args.get('floor_end'):
                            floor_range = (function_args['floor_start'], function_args['floor_end'])

                        allocations = self._create_sample_allocations(
                            top_n=function_args.get('top_n', 20),
                            floor_range=floor_range
                        )
                        filepath = self.generate_zone_allocation(
                            zones=zones,
                            allocations=allocations,
                            filename=function_args.get('filename')
                        )
                        function_response = json.dumps({
                            "status": "success",
                            "filepath": str(filepath),
                            "message": "Zone allocation PDF generated successfully",
                            "elements_allocated": len(allocations)
                        })
                        tool_results.append(f"Zone Allocation Map: {filepath}")

                    else:
                        function_response = json.dumps({
                            "status": "error",
                            "message": f"Unknown function: {function_name}"
                        })

                    # Add function response to messages
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": function_response
                    })

                # Get final response from AI after tool execution
                final_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=2000
                )

                answer = final_response.choices[0].message.content

            else:
                # No tool calls, just use the response
                answer = response_message.content

            # Add AI's final answer to history
            self.conversation_history.append({
                "role": "assistant",
                "content": answer
            })

            # Append generated files info to answer
            if tool_results:
                answer += "\n\n" + "="*60 + "\n"
                answer += "GENERATED FILES (ready to open):\n"
                answer += "="*60 + "\n"
                for result in tool_results:
                    answer += f"[OK] {result}\n"
                answer += "="*60 + "\n"
                answer += "All files saved in the logistics_outputs/ folder.\n"
                answer += "You can open them directly from there.\n"

            return answer

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return error_msg
