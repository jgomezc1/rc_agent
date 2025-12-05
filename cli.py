#!/usr/bin/env python3
"""
Command-line interface for ProDet Agent system.

Usage:
    python cli.py                           # Interactive mode with agent selection
    python cli.py --grouping "query"        # Grouping optimizer single query
    python cli.py --procurement "query"     # Procurement agent single query
    python cli.py --scheduling "query"      # Scheduling agent single query
"""

import sys
from langchain_core.messages import HumanMessage, AIMessage

# ANSI color codes
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

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
            'Optimize data/summary.xlsx from PISO 5 to PISO 15 with k=2,3,4',
            'What levels are available in data/summary.xlsx?'
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


def run_interactive(agent, agent_info):
    """Run interactive chat session with an agent."""
    print(f"\n{GREEN}━━━ {agent_info['name']} ━━━{RESET}")
    print(f"\nType 'back' to return to agent selection, 'exit' to quit.\n")
    print("Example queries:")
    for example in agent_info['examples']:
        print(f"  - {example}")
    print()

    chat_history = []

    while True:
        try:
            user_input = input(f"{CYAN}You:{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nReturning to menu...")
            return 'menu'

        if not user_input:
            continue

        if user_input.lower() == 'back':
            return 'menu'

        if user_input.lower() in ['exit', 'quit', 'q']:
            return 'exit'

        print()
        try:
            response = agent.run(user_input, chat_history=chat_history)
            print(f"{GREEN}Agent:{RESET} {response}")
            print()

            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(AIMessage(content=response))

        except Exception as e:
            print(f"{YELLOW}Error:{RESET} {e}\n")

    return 'menu'


def main():
    print(MAIN_BANNER)

    # Handle command-line arguments for single query mode
    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg == '--grouping' and len(sys.argv) > 2:
            from grouping_optimizer import GroupingOptimizerAgent
            query = " ".join(sys.argv[2:])
            print("Initializing Grouping Optimizer...")
            agent = GroupingOptimizerAgent()
            print(f"\nQuery: {query}\n")
            print("-" * 60)
            print(agent.run(query))
            return 0

        elif arg == '--procurement' and len(sys.argv) > 2:
            from procurement_agent import ProcurementAgent
            query = " ".join(sys.argv[2:])
            print("Initializing Procurement Agent...")
            agent = ProcurementAgent()
            print(f"\nQuery: {query}\n")
            print("-" * 60)
            print(agent.run(query))
            return 0

        elif arg == '--scheduling' and len(sys.argv) > 2:
            from scheduling_agent import SchedulingAgent
            query = " ".join(sys.argv[2:])
            print("Initializing Scheduling Agent...")
            agent = SchedulingAgent()
            print(f"\nQuery: {query}\n")
            print("-" * 60)
            print(agent.run(query))
            return 0

        elif arg in ['--help', '-h']:
            print("Usage:")
            print("  python cli.py                           # Interactive mode")
            print("  python cli.py --grouping \"query\"        # Grouping optimizer")
            print("  python cli.py --procurement \"query\"     # Procurement agent")
            print("  python cli.py --scheduling \"query\"      # Scheduling agent")
            return 0

        else:
            # Backwards compatibility: treat as grouping optimizer query
            from grouping_optimizer import GroupingOptimizerAgent
            query = " ".join(sys.argv[1:])
            print("Initializing Grouping Optimizer...")
            agent = GroupingOptimizerAgent()
            print(f"\nQuery: {query}\n")
            print("-" * 60)
            print(agent.run(query))
            return 0

    # Interactive mode with agent selection
    while True:
        print_agent_menu()

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
        print(f"\nInitializing {AGENTS[choice]['name']} (connecting to OpenAI)...")
        try:
            agent, agent_info = load_agent(choice)
            print("Agent ready.")
        except Exception as e:
            print(f"{YELLOW}Error initializing agent:{RESET} {e}")
            print("Make sure OPENAI_API_KEY is set in your .env file.")
            continue

        # Run interactive session
        result = run_interactive(agent, agent_info)

        if result == 'exit':
            print("Goodbye!")
            return 0
        # If 'menu', loop continues to show menu again

    return 0


if __name__ == "__main__":
    sys.exit(main())
