#!/usr/bin/env python3
"""
Multi-Agent CLI Interface for StructuBIM RC Agent

Provides unified interface for interacting with all three specialized agents:
- Trade-Off Analyst Agent (T-OAA)
- Procurement & Logistics Agent (P&L-A)
- Field Adaptability Agent (F-AA)
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from agents.orchestrator import AgentOrchestrator, ProjectPhase
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
import argparse


console = Console()


def print_welcome():
    """Print welcome message"""
    welcome_text = """
# StructuBIM Multi-Agent System

Welcome to the RC Agent Multi-Agent System. Three specialized agents are available:

## 🔍 Trade-Off Analyst Agent (T-OAA)
**Users:** Project Managers, Estimators, Design Leads
**Focus:** Solution selection and optimization
**Phase:** Pre-Construction (Optimization)

## 📦 Procurement & Logistics Agent (P&L-A)
**Users:** Procurement/Purchasing Manager, Logistics Manager
**Focus:** JIT planning and material coordination
**Phase:** Pre-Construction (Implementation)

## 🚧 Field Adaptability Agent (F-AA)
**Users:** Site Superintendent, Foreman, QC Inspector
**Focus:** Real-time crisis response and adaptation
**Phase:** Construction (Adaptation)

---

**Commands:**
- `status` - Show project status
- `switch <phase>` - Switch to different phase (optimization/implementation/adaptation)
- `select <solution_id>` - Select solution and move to implementation
- `crisis` - Report a site crisis
- `help` - Show this help message
- `exit` - Exit the system
    """
    console.print(Markdown(welcome_text))


def print_agent_response(response: dict):
    """
    Pretty print agent response

    Args:
        response: Agent response dictionary
    """
    if "error" in response:
        console.print(f"[bold red]Error:[/bold red] {response['error']}")
        return

    agent_name = response.get("agent", "System")

    # Print main response
    if "response" in response:
        console.print(Panel(
            response["response"],
            title=f"[bold cyan]{agent_name}[/bold cyan]",
            border_style="cyan"
        ))

    # Print tool calls if any
    if "tool_calls" in response:
        console.print("\n[bold yellow]Tool Executions:[/bold yellow]")
        for tool_call in response["tool_calls"]:
            console.print(f"  📋 {tool_call['function']}")


def print_status(orchestrator: AgentOrchestrator):
    """
    Print project status

    Args:
        orchestrator: Agent orchestrator instance
    """
    status = orchestrator.get_project_status()

    table = Table(title="Project Status", show_header=True)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Project ID", status["project_id"])
    table.add_row("Current Phase", status["current_phase"])
    table.add_row("Active Agent", status["active_agent"] or "None")
    table.add_row("Selected Solution", status["selected_solution"] or "None")
    table.add_row("Phase Transitions", str(status["phase_transitions"]))

    console.print(table)

    if status["agents_status"]:
        console.print("\n[bold]Agent Status:[/bold]")
        for agent_name, agent_info in status["agents_status"].items():
            console.print(f"  {agent_name}: {agent_info['tools_count']} tools, "
                         f"Phase1: {'✓' if agent_info['has_phase1_data'] else '✗'}, "
                         f"Phase2: {'✓' if agent_info['has_phase2_data'] else '✗'}")


def interactive_mode(api_key: str, project_id: str = "default"):
    """
    Run interactive mode

    Args:
        api_key: OpenAI API key
        project_id: Project identifier
    """
    print_welcome()

    # Initialize orchestrator
    console.print("\n[bold green]Initializing multi-agent system...[/bold green]")
    orchestrator = AgentOrchestrator(
        project_id=project_id,
        api_key=api_key,
        model="gpt-4"
    )

    # Verify data is loaded
    if orchestrator.toaa.context.phase1_data:
        num_solutions = len(orchestrator.toaa.context.phase1_data)
        console.print(f"[bold green]✓ Phase 1 data loaded: {num_solutions} solutions available[/bold green]")
    else:
        console.print("[bold yellow]⚠ Warning: Phase 1 data not loaded[/bold yellow]")
        console.print("[yellow]Agent will have limited functionality.[/yellow]")

    console.print("[bold green]✓ System ready![/bold green]\n")
    print_status(orchestrator)

    # Main interaction loop
    while True:
        try:
            # Get user input
            console.print(f"\n[bold cyan][{orchestrator.current_phase.value.upper()}][/bold cyan] ", end="")
            user_input = input("You: ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.lower() in ['exit', 'quit', 'q']:
                console.print("[bold yellow]Exiting multi-agent system. Goodbye![/bold yellow]")
                break

            elif user_input.lower() == 'status':
                print_status(orchestrator)
                continue

            elif user_input.lower() == 'help':
                print_welcome()
                continue

            elif user_input.lower().startswith('switch '):
                phase_name = user_input[7:].strip()
                try:
                    phase = ProjectPhase(phase_name.lower())
                    result = orchestrator.transition_to_phase(phase)
                    console.print(f"[bold green]✓ Switched to {phase.value} phase[/bold green]")
                    console.print(f"  Active agent: {result['active_agent']}")
                except ValueError:
                    console.print(f"[bold red]Invalid phase: {phase_name}[/bold red]")
                    console.print("Valid phases: optimization, implementation, adaptation")
                continue

            elif user_input.lower().startswith('select '):
                solution_id = user_input[7:].strip()
                result = orchestrator.select_solution(solution_id)
                if "error" in result:
                    console.print(f"[bold red]Error:[/bold red] {result['error']}")
                else:
                    console.print(f"[bold green]✓ Solution {solution_id} selected[/bold green]")
                    console.print(f"  Transitioned to {orchestrator.current_phase.value} phase")
                    console.print("\n[bold]Next Steps:[/bold]")
                    for step in result.get("next_steps", []):
                        console.print(f"  • {step}")
                continue

            elif user_input.lower() == 'crisis':
                console.print("\n[bold red]Report Site Crisis[/bold red]")
                event_type = input("Event type (material_shortage/quality_issue/schedule_delay/crew_constraint/design_conflict): ")
                description = input("Description: ")
                affected_story = input("Affected story (optional): ") or None
                affected_element = input("Affected element (optional): ") or None
                severity = input("Severity (low/medium/high/critical) [medium]: ") or "medium"

                result = orchestrator.report_crisis(
                    event_type=event_type,
                    description=description,
                    affected_story=affected_story,
                    affected_element=affected_element,
                    severity=severity
                )

                console.print(f"\n[bold green]✓ Crisis logged[/bold green]")
                console.print(f"Switched to Field Adaptability Agent (F-AA)")
                console.print("\n[bold]Recommended Next Steps:[/bold]")
                for step in result.get("response", {}).get("recommended_next_steps", []):
                    console.print(f"  • {step}")
                continue

            # Regular query to active agent
            console.print("[dim]Processing...[/dim]")
            response = orchestrator.query(user_input)
            print_agent_response(response)

        except KeyboardInterrupt:
            console.print("\n[bold yellow]Interrupted. Type 'exit' to quit.[/bold yellow]")
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="StructuBIM Multi-Agent System CLI"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--project-id",
        type=str,
        default="default",
        help="Project identifier"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="OpenAI API key (optional, will use env var if not provided)"
    )
    parser.add_argument(
        "--phase",
        type=str,
        choices=["optimization", "implementation", "adaptation"],
        default="optimization",
        help="Starting phase"
    )

    args = parser.parse_args()

    # Get API key
    api_key = args.api_key or os.getenv('OPENAI_API_KEY')
    if not api_key:
        console.print("[bold red]Error:[/bold red] OpenAI API key not provided.")
        console.print("Set OPENAI_API_KEY environment variable or use --api-key flag.")
        sys.exit(1)

    # Run interactive mode
    if args.interactive or len(sys.argv) == 1:
        interactive_mode(api_key, args.project_id)
    else:
        # Single command mode
        orchestrator = AgentOrchestrator(
            project_id=args.project_id,
            api_key=api_key
        )

        # Set phase
        phase = ProjectPhase(args.phase)
        orchestrator.transition_to_phase(phase)

        # Show status
        print_status(orchestrator)


if __name__ == "__main__":
    main()
