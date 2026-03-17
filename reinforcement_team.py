#!/usr/bin/env python3
"""
Reinforcement Team — unified CLI for Config Agent + Grouping Optimizer.

A lightweight LLM router classifies each user message and transparently
delegates to the appropriate sub-agent while sharing full conversation history.

Usage:
    python reinforcement_team.py                      # Interactive mode
    python reinforcement_team.py -p mokara            # With active project
    python reinforcement_team.py -q "Describe the mokara config"  # Single query
"""

import argparse
import itertools
import os
import sys
import threading
import time

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from utils.token_logger import TokenCounterCallback

load_dotenv()

# ---------------------------------------------------------------------------
# UI helpers (reused from cli.py)
# ---------------------------------------------------------------------------

MAX_HISTORY_PAIRS = 5

GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

BANNER = f"""
{GREEN}╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ██████╗ ███████╗██╗███╗   ██╗███████╗ ██████╗ ██████╗       ║
║   ██╔══██╗██╔════╝██║████╗  ██║██╔════╝██╔═══██╗██╔══██╗      ║
║   ██████╔╝█████╗  ██║██╔██╗ ██║█████╗  ██║   ██║██████╔╝      ║
║   ██╔══██╗██╔══╝  ██║██║╚██╗██║██╔══╝  ██║   ██║██╔══██╗      ║
║   ██║  ██║███████╗██║██║ ╚████║██║     ╚██████╔╝██║  ██║      ║
║   ╚═╝  ╚═╝╚══════╝╚═╝╚═╝  ╚═══╝╚═╝      ╚═════╝ ╚═╝  ╚═╝      ║
║                                                               ║
║          Reinforcement Team                                   ║
║          Config + Grouping Optimizer                          ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝{RESET}
"""


class Spinner:
    """Animated spinner to show processing activity."""

    def __init__(self, message="Processing", delay=0.1):
        self.message = message
        self.delay = delay
        self.running = False
        self.thread = None
        self.spinner_chars = itertools.cycle(
            ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        )

    def _spin(self):
        while self.running:
            char = next(self.spinner_chars)
            sys.stdout.write(f"\r{YELLOW}{char} {self.message}...{RESET}")
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
        sys.stdout.write("\r" + " " * (len(self.message) + 20) + "\r")
        sys.stdout.flush()
        return False


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

ROUTER_SYSTEM_PROMPT = """\
You are a silent intent classifier. Your ONLY job is to output a single word:
either "config" or "grouping".

Rules:
- "config" — the user wants to inspect, describe, create, compare, or modify a \
ProDet project.config file, or discuss design parameters, archetype profiles, \
parameter clusters, or rebar detailing settings.
- "grouping" — the user wants to optimize floor groupings, estimate steel impact \
of grouping floors, apply a grouping, compare grouped vs ungrouped results, or \
load baseline steel data.
- If the message is ambiguous or conversational (e.g. greetings, clarifications, \
follow-ups), look at the conversation history to determine which agent was last \
active and output that agent's name. If there is no history, default to "config".
- Output ONLY the single word. No punctuation, no explanation."""


class Router:
    """LLM-based intent classifier that routes to config or grouping agent."""

    def __init__(self, token_callback: TokenCounterCallback = None):
        model = os.environ.get("CLAUDE_MODEL_ROUTER", "claude-haiku-4-5-20251001")
        self.llm = ChatAnthropic(
            model=model,
            temperature=0.0,
            max_tokens=10,
        )
        self.system_message = SystemMessage(content=ROUTER_SYSTEM_PROMPT)
        self._token_callback = token_callback

    def classify(self, user_input: str, chat_history: list) -> str:
        """Return 'config' or 'grouping'."""
        messages = [self.system_message]

        # Include recent history so the router can detect follow-ups
        for msg in chat_history[-6:]:
            messages.append(msg)

        messages.append(HumanMessage(content=user_input))

        callbacks = []
        if self._token_callback:
            self._token_callback.set_current_agent("router", model=self.llm.model)
            callbacks.append(self._token_callback)

        result = self.llm.invoke(messages, config={"callbacks": callbacks})
        classification = result.content.strip().lower()

        if classification not in ("config", "grouping"):
            # Fallback: check for keywords
            lower = user_input.lower()
            if any(kw in lower for kw in ("group", "baseline", "steel", "estimate", "optimize floor")):
                return "grouping"
            return "config"

        return classification


# ---------------------------------------------------------------------------
# Team orchestrator
# ---------------------------------------------------------------------------

class ReinforcementTeam:
    """Orchestrates Config Agent and Grouping Optimizer behind a single chat."""

    def __init__(self, token_callback: TokenCounterCallback = None):
        self._token_callback = token_callback

        # Lazy-loaded sub-agents
        self._config_agent = None
        self._grouping_agent = None

        self.router = Router(token_callback=token_callback)

    @property
    def config_agent(self):
        if self._config_agent is None:
            from config_agent import ConfigAgent
            self._config_agent = ConfigAgent()
        return self._config_agent

    @property
    def grouping_agent(self):
        if self._grouping_agent is None:
            from grouping_optimizer import GroupingOptimizerAgent
            self._grouping_agent = GroupingOptimizerAgent()
        return self._grouping_agent

    def run(self, user_input: str, chat_history: list) -> str:
        """Route the message to the appropriate agent and return the response."""
        target = self.router.classify(user_input, chat_history)

        if target == "grouping":
            agent = self.grouping_agent
        else:
            agent = self.config_agent

        return agent.run(
            user_input,
            chat_history=chat_history,
            token_callback=self._token_callback,
        )


# ---------------------------------------------------------------------------
# Interactive loop
# ---------------------------------------------------------------------------

def _build_message(user_input: str, active_project: str = None) -> str:
    if active_project:
        return f"[Active project: {active_project} — use projects/{active_project}/ for all file paths]\n{user_input}"
    return user_input


def run_interactive(team: ReinforcementTeam, active_project: str = None):
    """Main interactive chat loop."""
    print(f"\n{GREEN}━━━ Reinforcement Team ━━━{RESET}")
    if active_project:
        print(f"  Active project: {YELLOW}{active_project}{RESET}")
    print(f"\nType 'exit' to quit.")
    print(f"Use '/project <name>' to set active project, '/project' to show current.\n")
    print("Example queries:")
    print("  - Describe the mokara config")
    print("  - Create a balanced config variant for mokara")
    print("  - Optimize floor groupings for mokara from PISO 5 to PISO 15")
    print("  - Compare grouped vs ungrouped steel totals")
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
            print("\nGoodbye!")
            return active_project

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "q"):
            return active_project

        # Handle /project command
        if user_input.startswith("/project"):
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
                response = team.run(message, chat_history=chat_history)
            print(f"{GREEN}Agent:{RESET} {response}")
            print()

            chat_history.append(HumanMessage(content=message))
            chat_history.append(AIMessage(content=response))

            if len(chat_history) > MAX_HISTORY_PAIRS * 2:
                chat_history[:] = chat_history[-(MAX_HISTORY_PAIRS * 2):]

        except Exception as e:
            print(f"{YELLOW}Error:{RESET} {e}\n")

    return active_project


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print(BANNER)

    parser = argparse.ArgumentParser(
        description="Reinforcement Team — Config + Grouping Optimizer",
    )
    parser.add_argument(
        "-p", "--project", type=str, default=None,
        help="Set active project (data in projects/<project>/)",
    )
    parser.add_argument(
        "-q", "--query", nargs=argparse.REMAINDER,
        help="Single-query mode: run one query and exit",
    )
    args = parser.parse_args()

    token_cb = TokenCounterCallback(agent_name="reinforcement-team")
    team = ReinforcementTeam(token_callback=token_cb)

    # Single-query mode
    if args.query is not None:
        query = " ".join(args.query)
        if not query.strip():
            print("Error: --query requires a query string.")
            return 1
        message = _build_message(query, args.project)
        print(f"Query: {query}")
        if args.project:
            print(f"Project: {args.project}")
        print("-" * 60)
        with Spinner("Thinking"):
            result = team.run(message, chat_history=[])
        print(result)
        if token_cb.call_count > 0:
            print(f"\n{token_cb.format_receipt()}")
        return 0

    # Interactive mode
    run_interactive(team, active_project=args.project)

    if token_cb.call_count > 0:
        print(f"\n{token_cb.format_receipt()}")
    print("Goodbye!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
