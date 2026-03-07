"""Token usage logging callback for LangChain agents.

Tracks input/output tokens per LLM call and accumulates session totals.
Supports per-agent breakdown when a single instance is shared across agents.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


# Default pricing: Sonnet ($3 / $15 per million tokens)
DEFAULT_INPUT_COST_PER_MTOK = 3.0
DEFAULT_OUTPUT_COST_PER_MTOK = 15.0

# Haiku pricing ($0.25 / $1.25 per million tokens)
HAIKU_INPUT_COST_PER_MTOK = 0.25
HAIKU_OUTPUT_COST_PER_MTOK = 1.25

# Model display name mapping
MODEL_DISPLAY_NAMES = {
    "claude-sonnet-4-6": "Sonnet 4.6",
    "claude-haiku-4-5-20251001": "Haiku 4.5",
}


def model_display_name(model_id: str) -> str:
    """Convert a model ID to a short display name."""
    return MODEL_DISPLAY_NAMES.get(model_id, model_id)


def cost_rates_for_model(model_id: str):
    """Return (input_cost_per_mtok, output_cost_per_mtok) for a model."""
    if "haiku" in model_id.lower():
        return HAIKU_INPUT_COST_PER_MTOK, HAIKU_OUTPUT_COST_PER_MTOK
    return DEFAULT_INPUT_COST_PER_MTOK, DEFAULT_OUTPUT_COST_PER_MTOK


class AgentStats:
    """Per-agent token accumulation."""
    __slots__ = (
        "call_count", "input_tokens", "output_tokens",
        "cache_read_tokens", "cache_creation_tokens", "cost", "model",
    )

    def __init__(self, model: str = ""):
        self.call_count = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_read_tokens = 0
        self.cache_creation_tokens = 0
        self.cost = 0.0
        self.model = model


class TokenCounterCallback(BaseCallbackHandler):
    """Callback handler that logs token usage and estimates cost per LLM call.

    Can be used in two modes:
    1. Per-agent (original): pass agent_name at construction time.
    2. Shared session: create once, call set_current_agent() before each
       agent invocation. Per-agent stats are accumulated in `agent_stats`.
    """

    def __init__(
        self,
        agent_name: str = "unknown",
        input_cost_per_mtok: float = DEFAULT_INPUT_COST_PER_MTOK,
        output_cost_per_mtok: float = DEFAULT_OUTPUT_COST_PER_MTOK,
    ):
        super().__init__()
        self.agent_name = agent_name
        self.input_cost_per_mtok = input_cost_per_mtok
        self.output_cost_per_mtok = output_cost_per_mtok

        # Session-level totals
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.call_count = 0
        self.cache_read_tokens = 0
        self.cache_creation_tokens = 0

        # Per-agent breakdown
        self.agent_stats: Dict[str, AgentStats] = {}

    def set_current_agent(self, agent_name: str, model: str = ""):
        """Set the current agent name for per-agent tracking."""
        self.agent_name = agent_name
        if agent_name not in self.agent_stats:
            self.agent_stats[agent_name] = AgentStats(model=model)
        elif model and not self.agent_stats[agent_name].model:
            self.agent_stats[agent_name].model = model

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Extract token usage from LLM response."""
        input_tokens = 0
        output_tokens = 0
        cache_read = 0
        cache_creation = 0

        # Try usage_metadata from generations (langchain-anthropic style)
        if response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    msg = getattr(gen, "message", None)
                    if msg:
                        usage = getattr(msg, "usage_metadata", None)
                        if usage:
                            input_tokens += usage.get("input_tokens", 0)
                            output_tokens += usage.get("output_tokens", 0)
                            input_details = usage.get("input_token_details", {})
                            cache_read += input_details.get("cache_read", 0)
                            cache_creation += input_details.get("cache_creation", 0)

        # Fallback: try llm_output.usage
        if input_tokens == 0 and response.llm_output:
            usage = response.llm_output.get("usage", {})
            input_tokens = usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0)
            output_tokens = usage.get("output_tokens", 0) or usage.get("completion_tokens", 0)
            cache_read = usage.get("cache_read_input_tokens", 0)
            cache_creation = usage.get("cache_creation_input_tokens", 0)

        if input_tokens == 0 and output_tokens == 0:
            return

        # Determine cost rates from agent model if available
        stats = self.agent_stats.get(self.agent_name)
        if stats and stats.model:
            in_rate, out_rate = cost_rates_for_model(stats.model)
        else:
            in_rate = self.input_cost_per_mtok
            out_rate = self.output_cost_per_mtok

        # Compute cost (cache reads are 90% cheaper for Anthropic)
        billable_input = input_tokens - cache_read
        input_cost = (billable_input * in_rate / 1_000_000
                      + cache_read * in_rate * 0.1 / 1_000_000)
        output_cost = output_tokens * out_rate / 1_000_000
        call_cost = input_cost + output_cost

        # Update session totals
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += call_cost
        self.call_count += 1
        self.cache_read_tokens += cache_read
        self.cache_creation_tokens += cache_creation

        # Update per-agent stats
        if self.agent_name not in self.agent_stats:
            self.agent_stats[self.agent_name] = AgentStats()
        stats = self.agent_stats[self.agent_name]
        stats.call_count += 1
        stats.input_tokens += input_tokens
        stats.output_tokens += output_tokens
        stats.cache_read_tokens += cache_read
        stats.cache_creation_tokens += cache_creation
        stats.cost += call_cost

        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        cache_info = f" (cache_read={cache_read})" if cache_read else ""
        print(
            f"  [{timestamp}] {self.agent_name} | "
            f"in={input_tokens:,} out={output_tokens:,}{cache_info} | "
            f"${call_cost:.4f}"
        )

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Print session summary when the top-level chain ends."""
        # Only print for the outermost chain (run_id matches parent)
        if kwargs.get("parent_run_id") is not None:
            return
        if self.call_count == 0:
            return
        print(
            f"\n  Token summary [{self.agent_name}]: "
            f"{self.call_count} LLM calls | "
            f"in={self.total_input_tokens:,} out={self.total_output_tokens:,} | "
            f"cache_read={self.cache_read_tokens:,} | "
            f"est. cost=${self.total_cost:.4f}"
        )

    def format_receipt(self) -> str:
        """Format a session cost receipt for CLI display."""
        # Determine the cache savings rate (use Sonnet rate as default)
        # Cache saves 90% of input cost per token
        uncached_rate = DEFAULT_INPUT_COST_PER_MTOK
        cache_savings = self.cache_read_tokens * uncached_rate * 0.9 / 1_000_000

        lines = []
        lines.append("╔══════════════════════════════════════════════════╗")
        lines.append("║              SESSION COST RECEIPT                ║")
        lines.append("╠══════════════════════════════════════════════════╣")
        lines.append("║  Agent          Model     Calls   Input  Output ║")
        lines.append("║  ───────────────────────────────────────────── ║")

        if self.agent_stats:
            for name, s in self.agent_stats.items():
                if s.call_count == 0:
                    continue
                display = model_display_name(s.model) if s.model else "-"
                lines.append(
                    f"║  {name:<14s} {display:<9s} {s.call_count:>3d}"
                    f"  {s.input_tokens:>7,d} {s.output_tokens:>6,d} ║"
                )
        else:
            lines.append("║  (no agents called)                             ║")

        lines.append("║  ───────────────────────────────────────────── ║")
        lines.append(
            f"║  TOTAL                    {self.call_count:>3d}"
            f"  {self.total_input_tokens:>7,d} {self.total_output_tokens:>6,d} ║"
        )
        lines.append(f"║  Cache hits       {self.cache_read_tokens:>8,d} tokens             ║")
        lines.append(f"║  Saved by cache      ~${cache_savings:<8.4f}              ║")
        lines.append(f"║  Estimated cost      ~${self.total_cost:<8.4f}              ║")
        lines.append("╚══════════════════════════════════════════════════╝")

        return "\n".join(lines)
