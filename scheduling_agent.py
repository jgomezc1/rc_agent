#!/usr/bin/env python3
"""
Scheduling Agent - LCEL-based agent for rebar scheduling and floor cycle planning.

This module provides LangChain tools and an agent for working with RC rebar
scheduling JSONs (work_packages.json and floor_schedule.json).

Usage:
    from scheduling_agent import SchedulingAgent

    agent = SchedulingAgent()
    response = agent.run("What is the duration for each floor?")
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Load environment variables from .env file
load_dotenv()
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from floor_schedule import (
    DEFAULT_HOURS_PER_DAY,
    DEFAULT_CREWS_PER_WORK_TYPE,
    build_floor_schedule,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# Defaults
# =============================================================================

DEFAULT_WORK_PACKAGES_PATH = "data/work_packages.json"
DEFAULT_FLOOR_SCHEDULE_PATH = "data/floor_schedule.json"


# =============================================================================
# LangChain Tools
# =============================================================================

@tool
def compute_floor_schedule_tool(
    work_packages_path: str = DEFAULT_WORK_PACKAGES_PATH,
    hours_per_day: float = DEFAULT_HOURS_PER_DAY,
    rebar_beams_crews: int = 2,
    rebar_columns_crews: int = 1,
    rebar_walls_crews: int = 1,
    rebar_slabs_crews: int = 2,
    rebar_unknown_crews: int = 1,
) -> Dict[str, Any]:
    """
    Compute a fresh floor-level schedule from work_packages.json.

    This tool reads work package data and computes floor-by-floor durations
    based on crew allocations and working hours per day.

    Args:
        work_packages_path: Path to work_packages.json file.
                           Default: "data/work_packages.json"
        hours_per_day: Working hours per day. Default: 8.0
        rebar_beams_crews: Number of crews for beam rebar work. Default: 2
        rebar_columns_crews: Number of crews for column rebar work. Default: 1
        rebar_walls_crews: Number of crews for wall rebar work. Default: 1
        rebar_slabs_crews: Number of crews for slab rebar work. Default: 2
        rebar_unknown_crews: Number of crews for unknown rebar work. Default: 1

    Returns:
        Dictionary containing the complete floor schedule with durations,
        or {"error": "..."} if something fails.
    """
    try:
        # Validate file existence
        if not os.path.exists(work_packages_path):
            return {"error": f"File not found: {work_packages_path}"}

        # Load work packages JSON
        with open(work_packages_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Build crews_per_work_type from parameters
        crews_per_work_type = DEFAULT_CREWS_PER_WORK_TYPE.copy()
        crews_per_work_type["rebar_beams"] = max(1, int(rebar_beams_crews or 1))
        crews_per_work_type["rebar_columns"] = max(1, int(rebar_columns_crews or 1))
        crews_per_work_type["rebar_walls"] = max(1, int(rebar_walls_crews or 1))
        crews_per_work_type["rebar_slabs"] = max(1, int(rebar_slabs_crews or 1))
        crews_per_work_type["rebar_unknown"] = max(1, int(rebar_unknown_crews or 1))

        # Sanitize hours_per_day
        if hours_per_day is None or hours_per_day <= 0:
            hours_per_day = DEFAULT_HOURS_PER_DAY

        # Compute floor schedule
        schedule = build_floor_schedule(data, crews_per_work_type, hours_per_day)

        return schedule

    except Exception as e:
        logger.error(f"Error computing floor schedule: {e}")
        return {"error": str(e)}


@tool
def load_floor_schedule_tool(
    floor_schedule_path: str = DEFAULT_FLOOR_SCHEDULE_PATH,
) -> Dict[str, Any]:
    """
    Load an existing floor_schedule.json file and return a summarized view.

    Useful when you already have a schedule computed and want to inspect it
    without recomputing.

    Args:
        floor_schedule_path: Path to floor_schedule.json file.
                            Default: "data/floor_schedule.json"

    Returns:
        Dictionary containing the schedule data plus a summary with:
        - total_floors: number of floors
        - floor_durations: list of {floor_id, floor_duration_days}
        - max_floor_duration_days: the slowest (bottleneck) floor duration
        Or {"error": "..."} if something fails.
    """
    try:
        # Check file existence
        if not os.path.exists(floor_schedule_path):
            return {"error": f"File not found: {floor_schedule_path}"}

        # Load schedule JSON
        with open(floor_schedule_path, "r", encoding="utf-8") as f:
            schedule = json.load(f)

        # Derive summary
        floors = schedule.get("floors", [])
        floor_summaries = []
        max_duration = 0.0

        for f in floors:
            floor_id = f.get("floor_id")
            duration = f.get("floor_duration_days", 0.0)
            floor_summaries.append({
                "floor_id": floor_id,
                "floor_duration_days": duration
            })
            if duration > max_duration:
                max_duration = duration

        return {
            "file_path": floor_schedule_path,
            "project_id": schedule.get("project_id"),
            "hours_per_day": schedule.get("hours_per_day"),
            "crews_per_work_type": schedule.get("crews_per_work_type"),
            "floors": schedule.get("floors", []),
            "summary": {
                "total_floors": len(floor_summaries),
                "floor_durations": floor_summaries,
                "max_floor_duration_days": max_duration,
            },
        }

    except Exception as e:
        logger.error(f"Error loading floor schedule: {e}")
        return {"error": str(e)}


# =============================================================================
# Scheduling Agent
# =============================================================================

class SchedulingAgent:
    """
    LCEL-based agent for rebar scheduling and floor cycle planning.

    Helps analyze rebar workloads (in tonf & crew-hours), evaluate floor-level
    durations, and explore what-if scenarios with different crew allocations.
    """

    SYSTEM_PROMPT = """You are an expert construction planner specializing in reinforced concrete rebar scheduling.

Your task is to help users understand and optimize floor-by-floor rebar installation schedules for RC building projects.

== WHAT YOU DO ==

You work with **work packages** and **floor schedules** generated from ProDet reinforcement data:

1. **Analyze workloads**: Understand crew_hours_total per floor and work type
2. **Compute durations**: Calculate duration_days given crew allocations and hours/day
3. **Identify bottlenecks**: Find the critical (slowest) floor that controls the cycle
4. **What-if analysis**: Explore scenarios like "What if I add one more beam crew?"

== AVAILABLE TOOLS ==

1. **compute_floor_schedule_tool**
   - Computes a fresh schedule from work_packages.json
   - Parameters: work_packages_path, hours_per_day, and crew counts per work type
   - Use this for what-if scenarios with different crew allocations

2. **load_floor_schedule_tool**
   - Loads and summarizes an existing floor_schedule.json
   - Use this to inspect current schedule without recomputing

== USAGE GUIDELINES ==

- If user asks for **current floor durations**, first try `load_floor_schedule_tool`
  - If file doesn't exist, suggest running `compute_floor_schedule_tool`

- If user asks a **what-if question** (change crews or hours/day):
  - Call `compute_floor_schedule_tool` with the new parameters
  - Compare results to the baseline if available

- Always **explain results clearly**:
  - Per-floor duration
  - Which floor controls the overall cycle (max duration = bottleneck)
  - Qualitative interpretation (e.g., "PISO 3 is the bottleneck at 3.68 days")

== KEY FIELDS EXPLAINED ==

- `crew_hours_total`: Total predicted crew-hours for a work package
- `n_crews_assigned`: Number of crews allocated to that work type
- `duration_days`: crew_hours_total / (n_crews_assigned × hours_per_day)
- `floor_duration_days`: Maximum duration among all packages on that floor
  (assumes different work types can proceed in parallel)

== DURATION FORMULA ==

```
duration_days = crew_hours_total / (n_crews * hours_per_day)
```

Example: 32 crew-hours with 2 crews and 8 hrs/day = 32 / (2 × 8) = 2 days

== OUTPUT FORMAT ==

Present results in clear, structured format:

📊 SCHEDULE SUMMARY
- Project: [name]
- Hours/day: [value]
- Crew allocation: [breakdown]

📅 FLOOR DURATIONS
| Floor | Duration (days) |
|-------|-----------------|
| PISO 2 | 3.15 |
| ... | ... |

⚠️ BOTTLENECK
- Critical floor: [floor_id]
- Duration: [X] days
- Reason: [brief explanation]

💡 RECOMMENDATIONS (if applicable)
- Suggestions for optimization

== IMPORTANT ==

- **Use tools** for schedule calculations - don't try to compute manually
- Return **concise, actionable** answers
- When comparing scenarios, show the **delta** (improvement or change)
- If asked about floors not in the data, explain what's available

== EXAMPLE QUERIES ==

- "What is the duration for each floor?"
- "Which floor is the bottleneck?"
- "What if I use 3 crews for beams instead of 2?"
- "How long would it take with 10-hour workdays?"
- "Compare current schedule with double the beam crews"
"""

    def __init__(self, model_name: str = "gpt-4.1-mini", temperature: float = 0.0):
        """Initialize the scheduling agent."""
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
        )
        self.tools = [compute_floor_schedule_tool, load_floor_schedule_tool]

        self.agent = create_react_agent(
            self.llm,
            tools=self.tools,
            prompt=self.SYSTEM_PROMPT,
        )

    def run(
        self,
        user_input: str,
        chat_history: Optional[List] = None,
    ) -> str:
        """
        Run the scheduling agent on a user query.

        Args:
            user_input: The user's question or request.
            chat_history: Optional list of previous messages for context.

        Returns:
            The final assistant message content as a string.
        """
        messages = []

        if chat_history:
            messages.extend(chat_history)

        messages.append(HumanMessage(content=user_input))

        result = self.agent.invoke({"messages": messages})

        if result.get("messages"):
            return result["messages"][-1].content

        return str(result)


# =============================================================================
# Standalone Helper
# =============================================================================

def run_schedule_from_cli(
    work_packages_path: str = DEFAULT_WORK_PACKAGES_PATH,
    hours_per_day: float = DEFAULT_HOURS_PER_DAY,
) -> Dict[str, Any]:
    """
    Convenience function: compute a schedule directly without LLM.

    Useful for quick tests and debugging.

    Args:
        work_packages_path: Path to work_packages.json file.
        hours_per_day: Working hours per day.

    Returns:
        The computed schedule dict, or {"error": "..."} on failure.
    """
    try:
        if not os.path.exists(work_packages_path):
            return {"error": f"File not found: {work_packages_path}"}

        with open(work_packages_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        crews_per_work_type = DEFAULT_CREWS_PER_WORK_TYPE.copy()

        schedule = build_floor_schedule(data, crews_per_work_type, hours_per_day)

        return schedule

    except Exception as e:
        logger.error(f"Error in run_schedule_from_cli: {e}")
        return {"error": str(e)}


# =============================================================================
# Main Entry Point (for testing)
# =============================================================================

if __name__ == "__main__":
    print("Scheduling Agent - Direct Test")
    print("=" * 40)

    # Test the standalone helper
    result = run_schedule_from_cli()

    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Project: {result.get('project_id')}")
        print(f"Hours/day: {result.get('hours_per_day')}")
        print(f"Floors: {len(result.get('floors', []))}")

        floors = result.get("floors", [])
        if floors:
            print("\nFloor Durations:")
            for f in floors[:5]:
                print(f"  {f.get('floor_id')}: {f.get('floor_duration_days', 0):.2f} days")
            if len(floors) > 5:
                print(f"  ... and {len(floors) - 5} more floors")
