#!/usr/bin/env python3
"""
ProDet Agent Team — unified CLI for all ProDet agents.

A lightweight LLM router classifies each user message and transparently
delegates to the appropriate sub-agent while sharing full conversation history.

Agents:
  - Config Agent: inspect, describe, create, modify project.config files
  - Grouping Optimizer: optimize floor groupings to minimize steel
  - Procurement Agent: review reinforcement files, generate bar lists & PDF reports
  - Scheduling Agent: plan rebar installation schedules
  - ProDet Runner: run ProDet, manage configs, process data pipeline

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
║          ProDet Agent                                         ║
║          Construction Intelligence Platform                   ║
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

VALID_AGENTS = ("grouping", "procurement", "scheduling", "prodet", "config")

AGENT_LABELS = {
    "grouping": "Grouping Optimizer",
    "procurement": "Procurement Agent",
    "scheduling": "Scheduling Agent",
    "prodet": "ProDet Runner",
    "config": "Config Agent",
}

ROUTER_SYSTEM_PROMPT = """\
You are a silent intent classifier. Your ONLY job is to output a single word: \
one of "grouping", "procurement", "scheduling", "prodet", or "config".

Rules:
- "grouping" — the user wants to optimize floor groupings, estimate steel impact \
of grouping floors, apply a grouping, compare grouped vs ungrouped results, or \
load baseline steel data.
- "procurement" — the user wants to review reinforcement solution files, generate \
bar lists, analyze bars by diameter or shape, compare reinforcement between \
variants, or generate PDF procurement reports.
- "scheduling" — the user wants to plan rebar installation schedules, compute \
floor durations, analyze crew allocations, or find scheduling bottlenecks.
- "prodet" — the user wants to run ProDet, list or inspect projects, run the \
data pipeline, run parametric studies, generate planos/memorias, compose \
solutions from variants, or copy ProDet output.
- "config" — the user wants to inspect, describe, create, compare, or modify a \
ProDet project.config file, or discuss design parameters, archetype profiles, \
parameter clusters, or rebar detailing settings.
- If the message is ambiguous or conversational (e.g. greetings, clarifications, \
follow-ups), look at the conversation history to determine which agent was last \
active and output that agent's name. If there is no history, default to "config".
- Output ONLY the single word. No punctuation, no explanation."""


class Router:
    """LLM-based intent classifier that routes to one of the five agents."""

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
        """Return one of: 'grouping', 'procurement', 'scheduling', 'prodet', 'config'."""
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

        if classification in VALID_AGENTS:
            return classification

        # Fallback: keyword matching
        lower = user_input.lower()
        if any(kw in lower for kw in ("group", "baseline", "optimize floor")):
            return "grouping"
        if any(kw in lower for kw in ("bar list", "procurement", "pdf report", "diameter", "reinforcement file")):
            return "procurement"
        if any(kw in lower for kw in ("schedule", "duration", "crew", "bottleneck", "workday")):
            return "scheduling"
        if any(kw in lower for kw in ("run prodet", "parametric", "pipeline", "planos", "memorias", "compose solution")):
            return "prodet"
        return "config"


# ---------------------------------------------------------------------------
# Team orchestrator
# ---------------------------------------------------------------------------

class ProDetAgentTeam:
    """Orchestrates all five ProDet agents behind a single chat with LLM routing."""

    def __init__(self, token_callback: TokenCounterCallback = None):
        self._token_callback = token_callback
        self._agents = {}  # lazy-loaded by key
        self.router = Router(token_callback=token_callback)

    def _get_agent(self, key: str):
        """Lazy-load and cache the requested agent."""
        if key not in self._agents:
            if key == "grouping":
                from grouping_optimizer import GroupingOptimizerAgent
                self._agents[key] = GroupingOptimizerAgent()
            elif key == "procurement":
                from procurement_agent import ProcurementAgent
                self._agents[key] = ProcurementAgent()
            elif key == "scheduling":
                from scheduling_agent import SchedulingAgent
                self._agents[key] = SchedulingAgent()
            elif key == "prodet":
                from prodet_agent import ProDetAgent
                self._agents[key] = ProDetAgent()
            else:  # config
                from config_agent import ConfigAgent
                self._agents[key] = ConfigAgent()
        return self._agents[key]

    def run(self, user_input: str, chat_history: list, forced_agent: str = None) -> tuple[str, str]:
        """Route the message to the appropriate agent.

        Args:
            forced_agent: If provided and valid, skip the LLM router and send
                          the message directly to that agent. Pass None to
                          use the router (default behavior).

        Returns (response_text, agent_key).
        """
        if forced_agent and forced_agent in VALID_AGENTS:
            target = forced_agent
        else:
            target = self.router.classify(user_input, chat_history)
        agent = self._get_agent(target)

        response = agent.run(
            user_input,
            chat_history=chat_history,
            token_callback=self._token_callback,
        )
        return response, target


# ---------------------------------------------------------------------------
# Interactive loop
# ---------------------------------------------------------------------------

def _build_message(user_input: str, active_project: str = None) -> str:
    if active_project:
        return f"[Active project: {active_project} — use projects/{active_project}/ for all file paths]\n{user_input}"
    return user_input


def run_interactive(team: ProDetAgentTeam, active_project: str = None):
    """Main interactive chat loop."""
    print(f"\n{GREEN}━━━ ProDet Agent ━━━{RESET}")
    if active_project:
        print(f"  Active project: {YELLOW}{active_project}{RESET}")
    print(f"\nType 'exit' to quit.")
    print(f"Use '/project <name>' to set active project, '/project' to show current.\n")
    print("Example queries:")
    print("  - Describe the mokara config")
    print("  - Optimize floor groupings from PISO 5 to PISO 15")
    print("  - Review the reinforcement solution file")
    print("  - What is the duration for each floor?")
    print("  - Run ProDet for mokara and process the output")
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
                response, routed_to = team.run(message, chat_history=chat_history)
            label = AGENT_LABELS.get(routed_to, routed_to)
            print(f"{GREEN}{label}:{RESET} {response}")
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
        description="ProDet Agent — Construction Intelligence Platform",
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

    token_cb = TokenCounterCallback(agent_name="prodet-agent")
    team = ProDetAgentTeam(token_callback=token_cb)

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
            result, routed_to = team.run(message, chat_history=[])
        label = AGENT_LABELS.get(routed_to, routed_to)
        print(f"[{label}]\n{result}")
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
