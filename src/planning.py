"""
planning.py
-----------
Given a high‑level optimisation strategy, output a list of
action‐stage names the agent executor should follow.
"""

from __future__ import annotations
from typing import List


def build_plan(strategy: str) -> List[str]:
    """
    Translate *strategy* → ordered list of step identifiers.

    Supported strategies
    --------------------
    - "minimize_steel"  : keep steel tonnage as low as possible
    - "minimize_cost"   : minimise steel+concrete cost
    - "minimize_manhours"
    - "minimize_co2"
    - "best_ci"         : highest constructibility index
    """
    base = ["load_data"]

    match strategy.lower():
        case "minimize_steel":
            return base + ["evaluate_steel", "rank", "report"]
        case "minimize_manhours":
            return base + ["evaluate_manhours", "rank", "report"]
        case "minimize_cost":
            return base + ["evaluate_cost", "rank", "report"]
        case "minimize_co2":
            return base + ["evaluate_co2", "rank", "report"]
        case "best_ci":
            return base + ["evaluate_ci", "rank_desc", "report"]
        case _:
            # fall back
            return base + ["evaluate_cost", "rank", "report"]
