#!/usr/bin/env python3
"""
Interactive AI Agent for Solution Data (solution.json)
Allows you to ask questions about a specific design solution
"""

import os
import json
from openai import OpenAI
from typing import Optional, Dict, Any

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class SolutionChatAgent:
    """AI agent that chats about a specific design solution."""

    def __init__(self, solution_path: str = "data/solution.json", api_key: Optional[str] = None):
        """Initialize the agent."""
        print("="*80)
        print("SOLUTION ANALYSIS - AI CHAT AGENT")
        print("="*80)

        # Load API key
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY in .env file")

        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o"

        # Load the solution JSON
        print(f"\n[1/2] Loading solution from {solution_path}...")
        self.solution_data = self._load_solution(solution_path)
        print(f"[OK] Loaded solution with {len(self.solution_data['elements'])} elements")

        # Prepare data summary for AI
        print("[2/2] Analyzing solution data...")
        self.data_summary = self._prepare_data_summary()
        print("[OK] Agent ready!\n")

        # Conversation history
        self.conversation_history = []

        print("="*80)
        print("You can now ask any question about this design solution.")
        print("Type 'quit' or 'exit' to end the conversation.")
        print("="*80)

    def _load_solution(self, solution_path: str) -> Dict[str, Any]:
        """Load the solution JSON file."""
        with open(solution_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _prepare_data_summary(self) -> str:
        """Prepare a summary of the solution for the AI."""
        data = self.solution_data

        # Bar sizes (calibres)
        bar_sizes = [bar['name'] for bar in data.get('calibres', [])]

        # Floor levels
        floors = list(data.get('pisos', {}).keys())
        num_floors = len(floors)

        # Elements
        elements = data.get('elements', [])
        num_elements = len(elements)

        # Analyze elements by type and floor
        element_types = {}
        elements_by_floor = {}
        total_bars = 0

        for elem in elements:
            info = elem.get('info', {})
            elem_type = info.get('beamType', 'Unknown')
            elem_name = info.get('nombre', 'Unknown')
            floor = info.get('piso', 'Unknown')

            # Count element types
            element_types[elem_type] = element_types.get(elem_type, 0) + 1

            # Count elements by floor
            elements_by_floor[floor] = elements_by_floor.get(floor, 0) + 1

            # Count bars in despiece
            despiece = elem.get('despiece', [])
            total_bars += len(despiece)

        # Build summary
        summary_parts = [
            "SOLUTION OVERVIEW:",
            f"- Total elements: {num_elements}",
            f"- Total floors: {num_floors}",
            f"- Total bar pieces: {total_bars}",
            f"- Available bar sizes: {', '.join(bar_sizes)}",
            "",
            "ELEMENT TYPES:",
        ]

        for elem_type, count in sorted(element_types.items()):
            summary_parts.append(f"  - {elem_type}: {count} elements")

        summary_parts.extend([
            "",
            "ELEMENTS PER FLOOR:",
        ])

        for floor, count in sorted(elements_by_floor.items(), key=lambda x: x[0]):
            summary_parts.append(f"  - {floor}: {count} elements")

        summary_parts.extend([
            "",
            "DETAILED ELEMENT DATA:",
            f"Each element contains:",
            f"  - 'info': Element identification (type, name, floor, section)",
            f"  - 'despiece': Detailed bar-by-bar breakdown",
            f"  - 'estribos': Stirrup/shear reinforcement zones",
            f"  - 'axes': Structural axes information",
            f"  - 'err_des': Design check results",
            "",
            "BAR SIZE DETAILS:",
        ])

        for bar in data.get('calibres', []):
            summary_parts.append(
                f"  - {bar['name']}: diameter {bar['diametro']}cm, "
                f"weight {bar['pesoLineal']}kg/m"
            )

        return "\n".join(summary_parts)

    def ask(self, question: str) -> str:
        """Ask a question about the solution."""

        # Build system message with data context
        system_message = f"""You are an expert structural engineer and construction advisor specializing in reinforced concrete design.

You have access to a complete design solution for a reinforced concrete building. This solution includes detailed information about every structural element (beams, columns, etc.), their reinforcement bars, and construction details.

{self.data_summary}

AVAILABLE DATA STRUCTURE:
- calibres: Bar sizes and properties
- pisos: Floor levels
- elementos: 86 structural elements with complete details
- Each element has:
  * info: Element type, name, floor, dimensions
  * despiece: Bar-by-bar cutting list (each bar with caliber, length, quantity)
  * estribos: Stirrup zones (spacing, size, configuration)
  * axes: Structural axes
  * err_des: Design validation checks

Your job is to answer questions about this solution clearly and helpfully.

Guidelines:
- Be specific and technical when appropriate
- Reference actual element names, floors, and bar sizes from the data
- If asked about quantities, calculate from the detailed data
- If asked about constructability, consider practical field implications
- If the question requires data I don't have access to, say so clearly
- Provide actionable insights when relevant

Answer in a professional but conversational tone.
"""

        # Add user question to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": question
        })

        # Build messages for API call
        messages = [
            {"role": "system", "content": system_message}
        ] + self.conversation_history

        # Call OpenAI API
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=1500
            )

            answer = response.choices[0].message.content

            # Add assistant response to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": answer
            })

            return answer

        except Exception as e:
            return f"Error: {str(e)}"

    def run_interactive(self):
        """Run interactive chat loop."""
        print("\nSTART CHATTING:")
        print("-" * 80)

        while True:
            # Get user input
            try:
                question = input("\nYou: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n\nGoodbye!")
                break

            if not question:
                continue

            # Check for exit commands
            if question.lower() in ['quit', 'exit', 'bye', 'goodbye']:
                print("\nGoodbye!")
                break

            # Special commands
            if question.lower() == 'help':
                self._show_help()
                continue

            if question.lower() == 'summary':
                print("\n" + self.data_summary)
                continue

            if question.lower() == 'history':
                self._show_history()
                continue

            if question.lower() == 'clear':
                self.conversation_history = []
                print("\n[OK] Conversation history cleared")
                continue

            # Ask the AI
            print("\nAgent: ", end="", flush=True)
            answer = self.ask(question)
            print(answer)
            print("-" * 80)

    def _show_help(self):
        """Show help message."""
        print("\n" + "="*80)
        print("HELP - Available Commands")
        print("="*80)
        print("\nCOMMANDS:")
        print("  help     - Show this help message")
        print("  summary  - Show the solution data summary")
        print("  history  - Show conversation history")
        print("  clear    - Clear conversation history")
        print("  quit     - Exit the chat")
        print("\nEXAMPLE QUESTIONS:")
        print("\nGeneral:")
        print("  - How many beams are in this solution?")
        print("  - What bar sizes are used?")
        print("  - Which floor has the most elements?")
        print("\nElement-Specific:")
        print("  - Tell me about beam V-3")
        print("  - What's the reinforcement for element V-8 on floor 3?")
        print("  - How many bars does column C-5 have?")
        print("\nQuantity Takeoffs:")
        print("  - How many 3/4\" bars are needed total?")
        print("  - What's the total steel weight for floor 10?")
        print("  - List all elements on floor 5")
        print("\nConstruction:")
        print("  - Which elements might be congested?")
        print("  - What's the stirrup spacing in beam V-12?")
        print("  - Are there any elements with complex reinforcement?")
        print("="*80)

    def _show_history(self):
        """Show conversation history."""
        print("\n" + "="*80)
        print("CONVERSATION HISTORY")
        print("="*80)

        if not self.conversation_history:
            print("\nNo conversation history yet.")
        else:
            for i, msg in enumerate(self.conversation_history, 1):
                role = "You" if msg["role"] == "user" else "Agent"
                content = msg["content"][:150]  # Show first 150 chars
                if len(msg["content"]) > 150:
                    content += "..."
                print(f"\n{i}. {role}: {content}")

        print("="*80)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Interactive Solution Chat Agent")
    parser.add_argument(
        "--solution",
        type=str,
        default="data/solution.json",
        help="Path to solution JSON file (default: data/solution.json)"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="OpenAI API key (optional, reads from .env if not provided)"
    )

    args = parser.parse_args()

    # Create and run agent
    try:
        agent = SolutionChatAgent(solution_path=args.solution, api_key=args.api_key)
        agent.run_interactive()
    except Exception as e:
        print(f"\n[!] Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
