"""
reasoning.py
------------
Very thin wrapper that decides *which* planning strategy to adopt
based on the natural‑language user prompt.
"""

from __future__ import annotations
import re


def choose_strategy(user_prompt: str) -> str:
    prompt = user_prompt.lower()

    if re.search(r"\b(co2|carbon)\b", prompt):
        return "minimize_co2"
    if "man-hour" in prompt or "manhour" in prompt:
        return "minimize_manhours"
    if "cheapest" in prompt or "cost" in prompt or "$" in prompt:
        return "minimize_cost"
    if "steel" in prompt:
        return "minimize_steel"
    if "constructibility" in prompt or "ci" in prompt:
        return "best_ci"

    # default
    return "minimize_cost"

