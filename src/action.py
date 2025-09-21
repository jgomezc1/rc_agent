"""
action.py
---------
Scoring / ranking helpers used by the agent's Action stage.
"""

from __future__ import annotations
import json
from typing import List, Dict, Any


# ------------------------------------------------------------------ #
#  RANKERS
# ------------------------------------------------------------------ #
def evaluate_steel(options: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(options, key=lambda x: x["steel_tonnage"])


def evaluate_manhours(options: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(options, key=lambda x: x["manhours"])


def evaluate_cost(options: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(options, key=lambda x: x["steel_cost"] + x["concrete_cost"])


def evaluate_co2(options: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(options, key=lambda x: x["co2_tonnes"])


def evaluate_ci(options: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Highest CI first
    return sorted(options, key=lambda x: x["constructibility_index"], reverse=True)


# ------------------------------------------------------------------ #
#  REPORTER
# ------------------------------------------------------------------ #
def print_report(best: Dict[str, Any]) -> str:
    best = {k.lower(): v for k, v in best.items()}   # normalise keys

    lines = [
        f"RS:            {best.get('id', best.get('rs_id'))}",
        f"Steel tonnage:  {best['steel_tonnage']:.1f} t",
        f"Man-hours:      {best['manhours']}",
        f"Material cost:  ${(best['steel_cost'] + best['concrete_cost']):,.0f}",
        f"Duration:       {best['duration_days']} days",
        f"CO2 trapped:    {best.get('co2_tonnes', best.get('co2'))} t",
        f"Constructibility index: "
        f"{best.get('constructibility_index', best.get('ci')):.2f}",
        f"Bar geometries: {best['bar_geometries']}",
    ]
    return "\n".join(lines)
# ------------------------------------------------------------------ #
#  Tool‑friendly wrapper (single‑argument 'input')
# ------------------------------------------------------------------ #
def print_report_tool(input: str) -> str:
    """
    Expect *input* to be a JSON record representing ONE RS.
    """
    best = json.loads(input)
    return print_report(best)