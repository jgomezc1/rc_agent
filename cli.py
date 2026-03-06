#!/usr/bin/env python3
"""
Command-line interface for ProDet Agent system.

Usage:
    python cli.py                           # Interactive mode with agent selection
    python cli.py --grouping "query"        # Grouping optimizer single query
    python cli.py --procurement "query"     # Procurement agent single query
    python cli.py --scheduling "query"      # Scheduling agent single query
    python cli.py --prodet "query"          # ProDet runner single query
    python cli.py --config "query"          # Config agent single query
    python cli.py --workflow config-impact mokara "simplify for speed"
"""

import argparse
import sys
import threading
import time
import itertools
from langchain_core.messages import HumanMessage, AIMessage

# Chat history sliding window — keep last N human+AI message pairs
MAX_HISTORY_PAIRS = 5

# ANSI color codes
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


class Spinner:
    """Animated spinner to show processing activity."""

    def __init__(self, message="Processing", delay=0.1):
        self.message = message
        self.delay = delay
        self.running = False
        self.thread = None
        self.spinner_chars = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])

    def _spin(self):
        while self.running:
            char = next(self.spinner_chars)
            sys.stdout.write(f'\r{YELLOW}{char} {self.message}...{RESET}')
            sys.stdout.flush()
            time.sleep(self.delay)

    def __enter__(self):
        self.running = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.running = False
        if self.thread:
            self.thread.join()
        # Clear the spinner line
        sys.stdout.write('\r' + ' ' * (len(self.message) + 20) + '\r')
        sys.stdout.flush()
        return False


MAIN_BANNER = f"""
{GREEN}╔═══════════════════════════════════════════════════════════════╗
║                                                                 ║
║   ██████╗ ██████╗  ██████╗ ██████╗ ███████╗████████╗            ║
║   ██╔══██╗██╔══██╗██╔═══██╗██╔══██╗██╔════╝╚══██╔══╝            ║
║   ██████╔╝██████╔╝██║   ██║██║  ██║█████╗     ██║               ║
║   ██╔═══╝ ██╔══██╗██║   ██║██║  ██║██╔══╝     ██║               ║
║   ██║     ██║  ██║╚██████╔╝██████╔╝███████╗   ██║               ║
║   ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝   ╚═╝               ║
║                                                                 ║
║                 🏗️  A G E N T  🏗️                               ║
║                                                                 ║
║           Construction Intelligence Platform                    ║
║                                                                 ║
╚═══════════════════════════════════════════════════════════════╝{RESET}
"""

AGENTS = {
    '1': {
        'name': 'Floor Grouping Optimizer',
        'description': 'Optimize floor groupings to minimize steel consumption',
        'module': 'grouping_optimizer',
        'class': 'GroupingOptimizerAgent',
        'examples': [
            'Optimize projects/summary.xlsx from PISO 5 to PISO 15 with k=2,3,4',
            'What levels are available in projects/summary.xlsx?'
        ]
    },
    '2': {
        'name': 'Procurement Agent',
        'description': 'Review reinforcement files and plan material procurement',
        'module': 'procurement_agent',
        'class': 'ProcurementAgent',
        'examples': [
            'Review the reinforcement solution file',
            'Give me a procurement report for PISO 5',
            'Generate a PDF report for floors PISO 5 through PISO 11',
            'What floors are available?'
        ]
    },
    '3': {
        'name': 'Scheduling Agent',
        'description': 'Plan rebar installation schedules and analyze floor durations',
        'module': 'scheduling_agent',
        'class': 'SchedulingAgent',
        'examples': [
            'What is the duration for each floor?',
            'Which floor is the bottleneck?',
            'What if I use 3 crews for beams instead of 2?',
            'How long would it take with 10-hour workdays?'
        ]
    },
    '4': {
        'name': 'ProDet Runner',
        'description': 'Run ProDet, manage configs, and process the data pipeline',
        'module': 'prodet_agent',
        'class': 'ProDetAgent',
        'examples': [
            'What projects are available?',
            'Inspect the mokara project',
            'Run ProDet for mokara and process the output',
            'Run a parametric study on mokara with cutting lengths 0.10m, 0.50m, 1.0m for vigas'
        ]
    },
    '5': {
        'name': 'Config Agent',
        'description': 'Describe and create ProDet project.config files using natural language',
        'module': 'config_agent',
        'class': 'ConfigAgent',
        'examples': [
            'Describe the configuration for the mokara project',
            'Create a new config with DES demand and 280 kg/cm2 concrete for beams',
            'Change the max rebar size to 1" for vigas',
            'What are the current detailing parameters for nervios?'
        ]
    }
}


def print_agent_menu():
    """Display agent selection menu."""
    print(f"\n{CYAN}Available Agents:{RESET}\n")
    for key, agent_info in AGENTS.items():
        print(f"  {GREEN}[{key}]{RESET} {agent_info['name']}")
        print(f"      {agent_info['description']}\n")
    print(f"  {GREEN}[q]{RESET} Quit\n")


def load_agent(agent_key: str):
    """Dynamically load the selected agent."""
    agent_info = AGENTS[agent_key]
    module = __import__(agent_info['module'])
    agent_class = getattr(module, agent_info['class'])
    return agent_class(), agent_info


def _build_message(user_input: str, active_project: str = None) -> str:
    """Prepend project context prefix to user message if a project is active."""
    if active_project:
        return f"[Active project: {active_project} — use projects/{active_project}/ for all file paths]\n{user_input}"
    return user_input


def run_interactive(agent, agent_info, active_project: str = None):
    """Run interactive chat session with an agent.

    Returns a tuple (action, active_project) where action is 'menu' or 'exit'.
    """
    print(f"\n{GREEN}━━━ {agent_info['name']} ━━━{RESET}")
    if active_project:
        print(f"  Active project: {YELLOW}{active_project}{RESET}")
    print(f"\nType 'back' to return to agent selection, 'exit' to quit.")
    print(f"Use '/project <name>' to set active project, '/project' to show current.\n")
    print("Example queries:")
    for example in agent_info['examples']:
        print(f"  - {example}")
    print()

    chat_history = []

    while True:
        try:
            if active_project:
                prompt_label = f"{CYAN}You [{active_project}]:{RESET} "
            else:
                prompt_label = f"{CYAN}You:{RESET} "
            user_input = input(prompt_label).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nReturning to menu...")
            return 'menu', active_project

        if not user_input:
            continue

        if user_input.lower() == 'back':
            return 'menu', active_project

        if user_input.lower() in ['exit', 'quit', 'q']:
            return 'exit', active_project

        # Handle /project command
        if user_input.startswith('/project'):
            parts = user_input.split(None, 1)
            if len(parts) > 1:
                active_project = parts[1].strip()
                print(f"{GREEN}Active project set to: {active_project}{RESET}")
                print(f"  Data path: projects/{active_project}/\n")
            else:
                if active_project:
                    print(f"Active project: {YELLOW}{active_project}{RESET} (projects/{active_project}/)\n")
                else:
                    print(f"No active project. Use '/project <name>' to set one.\n")
            continue

        print()
        try:
            message = _build_message(user_input, active_project)
            with Spinner("Thinking"):
                response = agent.run(message, chat_history=chat_history)
            print(f"{GREEN}Agent:{RESET} {response}")
            print()

            chat_history.append(HumanMessage(content=message))
            chat_history.append(AIMessage(content=response))

            # Sliding window: keep only the last N pairs to cap token cost
            if len(chat_history) > MAX_HISTORY_PAIRS * 2:
                chat_history[:] = chat_history[-(MAX_HISTORY_PAIRS * 2):]

        except Exception as e:
            print(f"{YELLOW}Error:{RESET} {e}\n")

    return 'menu', active_project


def _parse_args():
    """Parse CLI arguments. Returns (agent_flag, query, project) or None for interactive."""
    parser = argparse.ArgumentParser(
        description="ProDet Agent CLI — Construction Intelligence Platform",
        add_help=True,
    )
    parser.add_argument("--grouping", nargs=argparse.REMAINDER, help="Grouping optimizer query")
    parser.add_argument("--procurement", nargs=argparse.REMAINDER, help="Procurement agent query")
    parser.add_argument("--scheduling", nargs=argparse.REMAINDER, help="Scheduling agent query")
    parser.add_argument("--prodet", nargs=argparse.REMAINDER, help="ProDet runner query")
    parser.add_argument("--config", nargs=argparse.REMAINDER, help="Config agent query")
    parser.add_argument("--workflow", nargs=argparse.REMAINDER,
                        help="Run a workflow (e.g., config-impact mokara 'simplify for speed')")
    parser.add_argument("-p", "--project", type=str, default=None,
                        help="Set active project (data stored in projects/<project>/)")
    return parser


def _run_config_impact_workflow(project: str, intent: str) -> int:
    """Run the Config Impact Analysis workflow with interrupt/resume."""
    from workflows.config_impact import build_config_impact_workflow
    from langgraph.types import Command

    print(f"\n{GREEN}━━━ Config Impact Analysis Workflow ━━━{RESET}")
    print(f"  Project: {YELLOW}{project}{RESET}")
    print(f"  Intent:  {intent}\n")

    workflow = build_config_impact_workflow()
    thread_config = {"configurable": {"thread_id": "cli-config-impact-1"}}

    # Phase 1: run until interrupt (load_baseline + propose_changes)
    print(f"{CYAN}Phase 1:{RESET} Analyzing baseline and proposing changes...")
    with Spinner("Analyzing config"):
        result = workflow.invoke(
            {"project_name": project, "user_intent": intent, "messages": []},
            config=thread_config,
        )

    # Check for errors
    if result.get("error"):
        print(f"\n{YELLOW}Error:{RESET} {result['error']}")
        return 1

    # Display proposed changes (from the interrupted state)
    state = workflow.get_state(thread_config)
    vals = state.values

    print(f"\n{GREEN}Proposed Changes:{RESET}")
    print(f"  Target archetype: {BOLD}{vals.get('archetype_target', '?')}{RESET}")
    print(f"  Rationale: {vals.get('rationale', '?')}")
    print(f"  Expected impact: {vals.get('expected_impact', '?')}")
    print(f"\n  Config modifications:")
    for path, value in vals.get("proposed_changes", {}).items():
        print(f"    {path} = {value}")
    print(f"\n  Variant project: {project}_{vals.get('variant_suffix', '?')}")

    # Ask for confirmation
    print()
    try:
        confirm = input(f"{CYAN}Proceed with these changes? [y/N]:{RESET} ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nAborted.")
        return 0

    if confirm not in ("y", "yes"):
        print("Workflow cancelled.")
        # Resume with False to route to END
        workflow.invoke(Command(resume=False), config=thread_config)
        return 0

    # Phase 2: resume with confirmation → create variant → run ProDet → compare → narrate
    print(f"\n{CYAN}Phase 2:{RESET} Creating variant and running ProDet...")
    print("  (This may take several minutes per ProDet run)\n")

    result = workflow.invoke(Command(resume=True), config=thread_config)

    # Check for errors
    if result.get("error"):
        print(f"\n{YELLOW}Error:{RESET} {result['error']}")
        return 1

    # Display the narrative
    narrative = result.get("narrative", "")
    if narrative:
        print(f"\n{GREEN}{'=' * 60}{RESET}")
        print(f"{GREEN}  Config Impact Analysis — Trade-off Report{RESET}")
        print(f"{GREEN}{'=' * 60}{RESET}\n")
        print(narrative)
        print(f"\n{GREEN}{'=' * 60}{RESET}")
    else:
        print(f"\n{YELLOW}No narrative generated.{RESET}")
        # Print whatever messages we have
        for msg in result.get("messages", []):
            print(f"  {msg}")

    structubim_paths = result.get("structubim_output")
    if structubim_paths:
        print(f"\n{CYAN}StructuBim Output:{RESET}")
        for sb_path in structubim_paths:
            print(f"  File: {sb_path}")
        print(f"  Upload to structu-bim.com to visualize 3D reinforcement comparison")

    return 0


def main():
    print(MAIN_BANNER)

    parser = _parse_args()
    args = parser.parse_args()

    active_project = args.project

    # Workflow mode — run workflow first, then fall through to interactive menu
    if args.workflow is not None:
        wf_args = args.workflow
        if len(wf_args) < 2:
            print(f"{YELLOW}Usage:{RESET} --workflow <workflow-name> <project> <intent...>")
            print(f"  Example: --workflow config-impact mokara \"simplify for speed\"")
            return 1
        workflow_name = wf_args[0]
        project = wf_args[1]
        intent = " ".join(wf_args[2:]) if len(wf_args) > 2 else ""

        if workflow_name == "config-impact":
            if not intent:
                print(f"{YELLOW}Error:{RESET} config-impact workflow requires an intent string.")
                print(f"  Example: --workflow config-impact mokara \"simplify for faster construction\"")
                return 1
            result = _run_config_impact_workflow(project, intent)
            if result != 0:
                return result
            # Set active project to the one used in the workflow
            active_project = project
            # Fall through to interactive menu
        else:
            print(f"{YELLOW}Unknown workflow:{RESET} {workflow_name}")
            print(f"  Available workflows: config-impact")
            return 1

    # Single-query mode: detect which agent flag was used
    agent_modes = [
        ("grouping", args.grouping, "Grouping Optimizer", "Analyzing floor groupings",
         lambda: __import__("grouping_optimizer").GroupingOptimizerAgent()),
        ("procurement", args.procurement, "Procurement Agent", "Reviewing reinforcement data",
         lambda: __import__("procurement_agent").ProcurementAgent()),
        ("scheduling", args.scheduling, "Scheduling Agent", "Computing schedule",
         lambda: __import__("scheduling_agent").SchedulingAgent()),
        ("prodet", args.prodet, "ProDet Runner", "Running ProDet workflow",
         lambda: __import__("prodet_agent").ProDetAgent()),
        ("config", args.config, "Config Agent", "Analyzing configuration",
         lambda: __import__("config_agent").ConfigAgent()),
    ]

    for flag_name, flag_value, label, spinner_msg, factory in agent_modes:
        if flag_value is not None:
            query = " ".join(flag_value)
            if not query.strip():
                print(f"Error: --{flag_name} requires a query string.")
                return 1
            print(f"Initializing {label}...")
            agent = factory()
            message = _build_message(query, active_project)
            print(f"\nQuery: {query}")
            if active_project:
                print(f"Project: {active_project}")
            print()
            print("-" * 60)
            with Spinner(spinner_msg):
                result = agent.run(message)
            print(result)
            return 0

    # Interactive mode with agent selection
    while True:
        print_agent_menu()
        if active_project:
            print(f"  Active project: {YELLOW}{active_project}{RESET}")
            print(f"  Use '/project <name>' to change, '/project' to show current.\n")

        try:
            choice = input(f"{CYAN}Select agent [1-{len(AGENTS)}]:{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            return 0

        if choice.lower() in ['q', 'quit', 'exit']:
            print("Goodbye!")
            return 0

        if choice not in AGENTS:
            print(f"{YELLOW}Invalid selection. Please choose 1-{len(AGENTS)} or 'q' to quit.{RESET}")
            continue

        # Load selected agent
        print(f"\nInitializing {AGENTS[choice]['name']}...")
        try:
            agent, agent_info = load_agent(choice)
            print("Agent ready.")
        except Exception as e:
            print(f"{YELLOW}Error initializing agent:{RESET} {e}")
            print("Make sure ANTHROPIC_API_KEY is set in your .env file.")
            continue

        # Run interactive session
        action, active_project = run_interactive(agent, agent_info, active_project)

        if action == 'exit':
            print("Goodbye!")
            return 0
        # If 'menu', loop continues to show menu again

    return 0


if __name__ == "__main__":
    sys.exit(main())
