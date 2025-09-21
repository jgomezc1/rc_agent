"""
reflection.py
-------------
Quick post‑action sanity checks.
"""

from __future__ import annotations
from typing import Dict, Any


def needs_replan(best_option: Dict[str, Any]) -> bool:
    """
    Return *True* if the selected option violates hard constraints
    that should cause the agent to revisit the plan.
    """
    if best_option["steel_tonnage"] > 120:   # t
        return True
    if best_option["manhours"] > 700:
        return True
    if best_option["co2_tonnes"] > 600:
        return True
    return False
