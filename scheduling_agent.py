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
import re
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

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

# Plotly import for interactive Gantt chart (optional dependency)
try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except Exception as e:
    PLOTLY_AVAILABLE = False
    import sys as _sys
    logger.warning(
        "plotly import failed: %s (%s). Python: %s. "
        "Gantt chart generation will be disabled.",
        e, type(e).__name__, _sys.executable,
    )


# =============================================================================
# Defaults
# =============================================================================

DEFAULT_WORK_PACKAGES_PATH = "projects/work_packages.json"
DEFAULT_FLOOR_SCHEDULE_PATH = "projects/floor_schedule.json"


# =============================================================================
# Gantt Chart Helpers
# =============================================================================

def _floor_sort_key(floor_id: str):
    """Sort floors: PISO 2..23 numerically, then CUBIERTA, then CUB. MÁQUINAS."""
    fid = floor_id.strip().upper()
    m = re.match(r"PISO\s+(\d+)", fid, re.IGNORECASE)
    if m:
        return (0, int(m.group(1)))
    if "CUBIERTA" in fid and "MÁQ" not in fid and "MAQ" not in fid:
        return (1, 0)
    if "CUB" in fid and ("MÁQ" in fid or "MAQ" in fid):
        return (2, 0)
    return (3, 0)


WORK_TYPE_COLORS = {
    "rebar_beams":   "#3498db",  # blue
    "rebar_joists":  "#1abc9c",  # teal
    "rebar_columns": "#e67e22",  # orange
    "rebar_walls":   "#2ecc71",  # green
    "rebar_slabs":   "#9b59b6",  # purple
    "rebar_unknown": "#95a5a6",  # grey
}

WORK_TYPE_LABELS = {
    "rebar_beams":   "Beams",
    "rebar_joists":  "Joists",
    "rebar_columns": "Columns",
    "rebar_walls":   "Walls",
    "rebar_slabs":   "Slabs",
    "rebar_unknown": "Unknown",
}


# =============================================================================
# Gantt Chart Generator
# =============================================================================

class GanttChartGenerator:
    """Generates an interactive Gantt chart HTML from a floor schedule using Plotly."""

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def _sort_floors(self, floors: List[Dict]) -> List[Dict]:
        """Return floors sorted bottom-up (PISO 2 first, CUB. MÁQUINAS last)."""
        return sorted(floors, key=lambda f: _floor_sort_key(f.get("floor_id", "")))

    def _compute_cumulative_starts(self, sorted_floors: List[Dict]) -> List[Dict]:
        """Add cumulative_start_day to each floor (sequential scheduling)."""
        cum = 0.0
        result = []
        for f in sorted_floors:
            entry = dict(f)
            entry["cumulative_start_day"] = cum
            cum += f.get("floor_duration_days", 0.0)
            result.append(entry)
        return result

    def generate_html(self, schedule: Dict, filename: str = None) -> str:
        """Generate an interactive Gantt chart HTML and return the file path."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project_id = schedule.get("project_id", "project")
            safe_name = re.sub(r"[^\w\-]", "_", str(project_id))
            filename = f"gantt_chart_{safe_name}_{timestamp}.html"

        html_path = os.path.join(self.output_dir, filename)

        floors_raw = schedule.get("floors", [])
        sorted_floors = self._sort_floors(floors_raw)
        floors = self._compute_cumulative_starts(sorted_floors)

        # Floor IDs for Y-axis (bottom-up order matches list order)
        floor_ids = [f.get("floor_id", "?") for f in floors]

        # Build one trace per work type
        # Collect which work types appear so we only add those traces
        seen_types = set()
        for f in floors:
            for p in f.get("packages", []):
                seen_types.add(p.get("work_type", "rebar_unknown"))

        fig = go.Figure()

        work_type_order = ["rebar_beams", "rebar_joists", "rebar_columns", "rebar_walls", "rebar_slabs", "rebar_unknown"]

        for wt in work_type_order:
            if wt not in seen_types:
                continue

            bases = []
            widths = []
            y_labels = []
            hover_texts = []

            for f in floors:
                floor_id = f.get("floor_id", "?")
                start_day = f.get("cumulative_start_day", 0.0)
                packages = f.get("packages", [])

                pkg = next((p for p in packages if p.get("work_type") == wt), None)
                if pkg is None:
                    continue

                duration = pkg.get("duration_days", 0.0)
                crew_hours = pkg.get("crew_hours_total", 0.0)
                tonnage = pkg.get("total_weight_tonf", 0.0)
                n_crews = pkg.get("n_crews_assigned", 0)

                bases.append(start_day)
                widths.append(duration)
                y_labels.append(floor_id)
                hover_texts.append(
                    f"<b>{floor_id}</b><br>"
                    f"Work type: {WORK_TYPE_LABELS.get(wt, wt)}<br>"
                    f"Duration: {duration:.2f} days<br>"
                    f"Crew-hours: {crew_hours:.1f}<br>"
                    f"Tonnage: {tonnage:.2f} tonf<br>"
                    f"Crews: {n_crews}"
                )

            fig.add_trace(go.Bar(
                y=y_labels,
                x=widths,
                base=bases,
                orientation="h",
                name=WORK_TYPE_LABELS.get(wt, wt),
                marker_color=WORK_TYPE_COLORS.get(wt, "#95a5a6"),
                hovertext=hover_texts,
                hoverinfo="text",
            ))

        # Summary stats for subtitle
        hours_per_day = schedule.get("hours_per_day", 8.0)
        crews = schedule.get("crews_per_work_type", {})
        crew_str = ", ".join(f"{WORK_TYPE_LABELS.get(k, k)}: {v}" for k, v in sorted(crews.items()))
        total_days = sum(f.get("floor_duration_days", 0) for f in floors)

        fig.update_layout(
            title=dict(
                text=f"Rebar Installation Gantt Chart — {schedule.get('project_id', 'Project')}",
                font=dict(size=20, color="#1a5f7a"),
            ),
            xaxis_title="Project Days (cumulative)",
            yaxis=dict(
                categoryorder="array",
                categoryarray=floor_ids,
                title="",
            ),
            barmode="overlay",
            bargap=0.3,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
            ),
            template="plotly_white",
            height=max(400, len(floors) * 35 + 150),
            annotations=[
                dict(
                    text=f"{len(floors)} floors | {hours_per_day} hrs/day | Crews: {crew_str} | Total: {total_days:.1f} days",
                    xref="paper", yref="paper",
                    x=0.5, y=-0.12,
                    showarrow=False,
                    font=dict(size=11, color="#636e72"),
                ),
                dict(
                    text=f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')} by RC Agent — Scheduling Module",
                    xref="paper", yref="paper",
                    x=1.0, y=-0.18,
                    showarrow=False,
                    font=dict(size=9, color="#b2bec3"),
                    xanchor="right",
                ),
            ],
            margin=dict(l=120, r=40, t=80, b=100),
        )

        fig.write_html(html_path, full_html=True, include_plotlyjs=True)
        logger.info(f"Gantt chart HTML saved to: {html_path}")
        return html_path


# =============================================================================
# LangChain Tools
# =============================================================================

@tool
def compute_floor_schedule_tool(
    work_packages_path: str = DEFAULT_WORK_PACKAGES_PATH,
    hours_per_day: float = DEFAULT_HOURS_PER_DAY,
    rebar_beams_crews: int = 2,
    rebar_joists_crews: int = 2,
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
                           Default: "projects/work_packages.json"
        hours_per_day: Working hours per day. Default: 8.0
        rebar_beams_crews: Number of crews for beam rebar work. Default: 2
        rebar_joists_crews: Number of crews for joist (nervio) rebar work. Default: 2
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
        crews_per_work_type["rebar_joists"] = max(1, int(rebar_joists_crews or 1))
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
                            Default: "projects/floor_schedule.json"

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


@tool
def generate_gantt_chart(
    work_packages_path: str = DEFAULT_WORK_PACKAGES_PATH,
    floor_schedule_path: str = DEFAULT_FLOOR_SCHEDULE_PATH,
    hours_per_day: float = DEFAULT_HOURS_PER_DAY,
    rebar_beams_crews: int = 2,
    rebar_joists_crews: int = 2,
    rebar_columns_crews: int = 1,
    rebar_walls_crews: int = 1,
    rebar_slabs_crews: int = 2,
    rebar_unknown_crews: int = 1,
    use_existing_schedule: bool = True,
) -> Dict[str, Any]:
    """
    Generate an interactive HTML Gantt chart showing the rebar installation timeline across floors.

    The chart shows each floor as a horizontal bar on the Y-axis, with the X-axis
    representing cumulative project days. Bars are color-coded by work type
    (beams=blue, joists=teal, columns=orange, walls=green, slabs=purple).
    The HTML file can be opened in any browser with zoom, pan, and hover tooltips.

    Args:
        work_packages_path: Path to work_packages.json (used if computing fresh schedule).
                           Default: "projects/work_packages.json"
        floor_schedule_path: Path to floor_schedule.json (used if use_existing_schedule=True).
                            Default: "projects/floor_schedule.json"
        hours_per_day: Working hours per day. Default: 8.0
        rebar_beams_crews: Number of crews for beam rebar work. Default: 2
        rebar_joists_crews: Number of crews for joist (nervio) rebar work. Default: 2
        rebar_columns_crews: Number of crews for column rebar work. Default: 1
        rebar_walls_crews: Number of crews for wall rebar work. Default: 1
        rebar_slabs_crews: Number of crews for slab rebar work. Default: 2
        rebar_unknown_crews: Number of crews for unknown rebar work. Default: 1
        use_existing_schedule: If True, load floor_schedule.json; if False, compute fresh.
                              Default: True

    Returns:
        Dictionary with html_path, chart_generated (bool), total_project_days, n_floors,
        or {"error": "..."} if something fails.
    """
    if not PLOTLY_AVAILABLE:
        return {"error": "plotly is not installed. Install it with: pip install plotly"}

    try:
        schedule = None

        if use_existing_schedule and os.path.exists(floor_schedule_path):
            with open(floor_schedule_path, "r", encoding="utf-8") as f:
                schedule = json.load(f)
        else:
            # Compute fresh schedule from work packages
            if not os.path.exists(work_packages_path):
                return {"error": f"File not found: {work_packages_path}"}

            with open(work_packages_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            crews_per_work_type = DEFAULT_CREWS_PER_WORK_TYPE.copy()
            crews_per_work_type["rebar_beams"] = max(1, int(rebar_beams_crews or 1))
            crews_per_work_type["rebar_joists"] = max(1, int(rebar_joists_crews or 1))
            crews_per_work_type["rebar_columns"] = max(1, int(rebar_columns_crews or 1))
            crews_per_work_type["rebar_walls"] = max(1, int(rebar_walls_crews or 1))
            crews_per_work_type["rebar_slabs"] = max(1, int(rebar_slabs_crews or 1))
            crews_per_work_type["rebar_unknown"] = max(1, int(rebar_unknown_crews or 1))

            if hours_per_day is None or hours_per_day <= 0:
                hours_per_day = DEFAULT_HOURS_PER_DAY

            schedule = build_floor_schedule(data, crews_per_work_type, hours_per_day)

        if schedule is None:
            return {"error": "Could not load or compute a floor schedule."}

        generator = GanttChartGenerator()
        html_path = generator.generate_html(schedule)

        floors = schedule.get("floors", [])
        sorted_floors = sorted(floors, key=lambda f: _floor_sort_key(f.get("floor_id", "")))
        total_project_days = sum(f.get("floor_duration_days", 0.0) for f in sorted_floors)

        return {
            "html_path": html_path,
            "chart_generated": True,
            "total_project_days": round(total_project_days, 2),
            "n_floors": len(floors),
            "message": f"Interactive Gantt chart saved to {html_path}. Open in a browser for zoom, pan, and hover tooltips.",
        }

    except Exception as e:
        logger.error(f"Error generating Gantt chart: {e}")
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

3. **generate_gantt_chart**
   - Generates an interactive HTML Gantt chart showing the rebar installation timeline across all floors
   - Bars are color-coded by work type (beams=blue, joists=teal, columns=orange, walls=green, slabs=purple)
   - Floors are sorted bottom-up (PISO 2 at bottom, CUB. MÁQUINAS at top)
   - The HTML file can be opened in any browser with zoom, pan, and hover tooltips
   - Can use an existing floor_schedule.json or compute a fresh one
   - Use this when the user asks for a visual timeline, Gantt chart, or chart of the schedule

== USAGE GUIDELINES ==

- If user asks for **current floor durations**, first try `load_floor_schedule_tool`
  - If file doesn't exist, suggest running `compute_floor_schedule_tool`

- If user asks a **what-if question** (change crews or hours/day):
  - Call `compute_floor_schedule_tool` with the new parameters
  - Compare results to the baseline if available

- If user asks for a **Gantt chart**, **visual timeline**, or **chart**:
  - Call `generate_gantt_chart` (defaults use existing schedule)
  - For what-if Gantt charts, set `use_existing_schedule=False` and pass crew counts
  - Report the HTML file path and total project duration
  - Mention they can open it in a browser for interactive zoom, pan, and hover tooltips

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
- "Generate a Gantt chart for the current schedule"
- "Create a Gantt chart with 3 beam crews and 10-hour days"

== PROJECT-SPECIFIC DATA ==

If the user mentions a project name or the message contains [Active project: X],
use project-specific paths:
  - work_packages_path: "projects/<project_name>/work_packages.json"
  - floor_schedule_path: "projects/<project_name>/floor_schedule.json"
If no project is specified, use the defaults.
"""

    def __init__(self, model_name: str = "claude-sonnet-4-6", temperature: float = 0.0):
        """Initialize the scheduling agent."""
        self.llm = ChatAnthropic(
            model=model_name,
            temperature=temperature,
        )
        self.tools = [compute_floor_schedule_tool, load_floor_schedule_tool, generate_gantt_chart]

        self.agent = create_react_agent(
            self.llm,
            tools=self.tools,
            prompt=self.SYSTEM_PROMPT,
        )

    def run(
        self,
        user_input: str,
        chat_history: Optional[List] = None,
        max_iterations: int = 15,
    ) -> str:
        """
        Run the scheduling agent on a user query.

        Args:
            user_input: The user's question or request.
            chat_history: Optional list of previous messages for context.
            max_iterations: Maximum number of agent iterations to prevent infinite loops (default: 15)

        Returns:
            The final assistant message content as a string.
        """
        messages = []

        if chat_history:
            messages.extend(chat_history)

        messages.append(HumanMessage(content=user_input))

        # Invoke with recursion limit to prevent infinite loops
        result = self.agent.invoke(
            {"messages": messages},
            config={"recursion_limit": max_iterations}
        )

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
