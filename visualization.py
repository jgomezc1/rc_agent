#!/usr/bin/env python3
"""
Visualization — Interactive HTML dashboard for RC Agent projects.

Generates a 4-panel Plotly dashboard (steel by floor, steel by diameter,
floor schedule, complexity profile) from pipeline JSON artifacts and
auto-opens it in the browser.

Usage:
    python visualization.py -p mokara
    python visualization.py -p mokara -o custom.html
    python visualization.py -p mokara --no-open
    python visualization.py --project-path /abs/path/to/project/
"""

import argparse
import json
import os
import webbrowser
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import plotly.graph_objects as go

from paths import RC_AGENT_PROJECTS
from scheduling_agent import WORK_TYPE_COLORS, WORK_TYPE_LABELS, _floor_sort_key

# Mapping element_type → work_type key (used for colors)
_ELEMENT_TO_WORK_TYPE = {
    "beam": "rebar_beams",
    "column": "rebar_columns",
    "wall": "rebar_walls",
    "slab": "rebar_slabs",
}

# Standard rebar diameter ordering (smallest → largest)
_DIAMETER_ORDER = [
    '3/8"', '1/2"', '5/8"', '3/4"', '7/8"', '1"', '1-1/8"', '1-3/8"',
    '#3', '#4', '#5', '#6', '#7', '#8', '#9', '#10', '#11',
    '6mm', '8mm', '10mm', '12mm', '16mm', '20mm', '25mm', '32mm',
]


# =============================================================================
# Data Loading
# =============================================================================

def load_project_data(project_path: str) -> Dict[str, Any]:
    """Load elements_with_ci.json and floor_schedule.json from a project folder.

    Returns dict with keys "elements" (list) and "schedule" (dict).
    Raises FileNotFoundError if either file is missing.
    """
    elements_path = os.path.join(project_path, "elements_with_ci.json")
    schedule_path = os.path.join(project_path, "floor_schedule.json")

    if not os.path.isfile(elements_path):
        raise FileNotFoundError(f"Missing: {elements_path}")
    if not os.path.isfile(schedule_path):
        raise FileNotFoundError(f"Missing: {schedule_path}")

    with open(elements_path, "r", encoding="utf-8") as f:
        elements_data = json.load(f)
    with open(schedule_path, "r", encoding="utf-8") as f:
        schedule_data = json.load(f)

    return {
        "elements": elements_data.get("elements", []),
        "schedule": schedule_data,
        "project_id": elements_data.get("project_id", os.path.basename(project_path)),
    }


# =============================================================================
# Panel 1 — Steel by Floor (horizontal stacked bar)
# =============================================================================

def fig_steel_by_floor(elements: List[Dict]) -> go.Figure:
    """Horizontal stacked bar: total steel (kg) per floor, stacked by element_type."""
    # Aggregate w_total_kgf by (floor_id, element_type)
    weight_map: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for el in elements:
        floor_id = el.get("floor_id", "?")
        etype = el.get("element_type", "unknown")
        weight_map[floor_id][etype] += el.get("reinforcement", {}).get("w_total_kgf", 0.0) or el.get("w_total_kgf", 0.0)

    # Sort floors bottom-up
    sorted_floors = sorted(weight_map.keys(), key=_floor_sort_key)

    # Collect all element types present
    all_types = set()
    for by_type in weight_map.values():
        all_types.update(by_type.keys())

    type_order = ["beam", "column", "wall", "slab", "unknown"]
    ordered_types = [t for t in type_order if t in all_types]
    ordered_types += sorted(all_types - set(type_order))

    fig = go.Figure()
    for etype in ordered_types:
        wt_key = _ELEMENT_TO_WORK_TYPE.get(etype, "rebar_unknown")
        values = [weight_map[f].get(etype, 0.0) for f in sorted_floors]
        fig.add_trace(go.Bar(
            y=sorted_floors,
            x=values,
            orientation="h",
            name=WORK_TYPE_LABELS.get(wt_key, etype.capitalize()),
            marker_color=WORK_TYPE_COLORS.get(wt_key, "#95a5a6"),
            hovertemplate="%{y}: %{x:,.0f} kg<extra>" + WORK_TYPE_LABELS.get(wt_key, etype) + "</extra>",
        ))

    fig.update_layout(
        title="Steel by Floor",
        xaxis_title="Weight (kg)",
        yaxis=dict(categoryorder="array", categoryarray=sorted_floors),
        barmode="stack",
        template="plotly_white",
        height=max(400, len(sorted_floors) * 30 + 120),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=120, r=30, t=60, b=40),
    )
    return fig


# =============================================================================
# Panel 2 — Steel by Diameter (vertical bar)
# =============================================================================

def fig_steel_by_diameter(elements: List[Dict]) -> go.Figure:
    """Vertical bar: total steel (kg) by rebar diameter across all elements."""
    diameter_weight: Dict[str, float] = defaultdict(float)

    for el in elements:
        reinf = el.get("reinforcement", {})
        for row in reinf.get("longitudinal_rows", []):
            calibre = row.get("calibre", "?")
            diameter_weight[calibre] += row.get("peso_kgf", 0.0)
        for row in reinf.get("transverse_rows", []):
            calibre = row.get("calibre", "?")
            diameter_weight[calibre] += row.get("peso_kgf", 0.0)

    # Sort by standard order, then alphabetical for unknowns
    order_map = {d: i for i, d in enumerate(_DIAMETER_ORDER)}
    sorted_diameters = sorted(
        diameter_weight.keys(),
        key=lambda d: (order_map.get(d, 999), d),
    )

    values = [diameter_weight[d] for d in sorted_diameters]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sorted_diameters,
        y=values,
        marker_color="#3498db",
        hovertemplate="%{x}: %{y:,.0f} kg<extra></extra>",
    ))

    fig.update_layout(
        title="Steel by Diameter",
        xaxis_title="Diameter",
        yaxis_title="Weight (kg)",
        template="plotly_white",
        height=400,
        margin=dict(l=80, r=30, t=60, b=60),
    )
    return fig


# =============================================================================
# Panel 3 — Floor Schedule (Gantt chart)
# =============================================================================

def fig_floor_schedule(schedule: Dict) -> go.Figure:
    """Gantt chart: floors on Y-axis (bottom-up), X-axis is cumulative project days.

    Each floor starts after the previous floor finishes (sequential scheduling).
    Within a floor, work-type bars are overlaid (parallel work types).
    """
    floors_raw = schedule.get("floors", [])
    sorted_floors = sorted(floors_raw, key=lambda f: _floor_sort_key(f.get("floor_id", "")))

    # Compute cumulative start day for each floor
    cumulative_start = 0.0
    for f in sorted_floors:
        f["_start_day"] = cumulative_start
        cumulative_start += f.get("floor_duration_days", 0.0)
    total_days = cumulative_start

    floor_ids = [f.get("floor_id", "?") for f in sorted_floors]

    # Collect present work types
    seen_types = set()
    for f in sorted_floors:
        for p in f.get("packages", []):
            seen_types.add(p.get("work_type", "rebar_unknown"))

    wt_order = ["rebar_beams", "rebar_columns", "rebar_walls", "rebar_slabs", "rebar_unknown"]

    fig = go.Figure()
    for wt in wt_order:
        if wt not in seen_types:
            continue
        bases = []
        widths = []
        y_labels = []
        hover_texts = []

        for f in sorted_floors:
            pkg = next((p for p in f.get("packages", []) if p.get("work_type") == wt), None)
            if pkg is None:
                continue
            start = f["_start_day"]
            duration = pkg.get("duration_days", 0.0)
            crew_hours = pkg.get("crew_hours_total", 0.0)
            tonnage = pkg.get("w_total_ton", pkg.get("total_weight_tonf", 0.0))
            n_crews = pkg.get("n_crews_assigned", 0)

            bases.append(start)
            widths.append(duration)
            y_labels.append(f.get("floor_id", "?"))
            hover_texts.append(
                f"<b>{f.get('floor_id', '?')}</b><br>"
                f"Work type: {WORK_TYPE_LABELS.get(wt, wt)}<br>"
                f"Start: day {start:.1f}<br>"
                f"Duration: {duration:.2f} days<br>"
                f"Crew-hours: {crew_hours:.1f}<br>"
                f"Tonnage: {tonnage:.2f} ton<br>"
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

    # Summary subtitle
    hours_per_day = schedule.get("hours_per_day", 8.0)
    crews = schedule.get("crews_per_work_type", {})
    crew_str = ", ".join(
        f"{WORK_TYPE_LABELS.get(k, k)}: {v}" for k, v in sorted(crews.items())
    )

    fig.update_layout(
        title="Rebar Installation — Gantt Chart",
        xaxis_title="Project Days (cumulative)",
        yaxis=dict(categoryorder="array", categoryarray=floor_ids, title=""),
        barmode="overlay",
        template="plotly_white",
        height=max(400, len(floor_ids) * 35 + 150),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=120, r=40, t=60, b=80),
        bargap=0.3,
        annotations=[
            dict(
                text=(
                    f"{len(floor_ids)} floors | {hours_per_day} hrs/day | "
                    f"Crews: {crew_str} | Total: {total_days:.1f} days"
                ),
                xref="paper", yref="paper",
                x=0.5, y=-0.08,
                showarrow=False,
                font=dict(size=11, color="#636e72"),
            ),
        ],
    )
    return fig


# =============================================================================
# Panel 4 — Complexity Profile (horizontal bar)
# =============================================================================

def fig_complexity_profile(elements: List[Dict]) -> go.Figure:
    """Horizontal bar: average complexity index per floor."""
    ci_accum: Dict[str, List[float]] = defaultdict(list)
    for el in elements:
        floor_id = el.get("floor_id", "?")
        ci = el.get("ci")
        if ci is not None:
            ci_accum[floor_id].append(ci)

    sorted_floors = sorted(ci_accum.keys(), key=_floor_sort_key)
    avg_ci = [sum(ci_accum[f]) / len(ci_accum[f]) for f in sorted_floors]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=sorted_floors,
        x=avg_ci,
        orientation="h",
        marker_color="#e74c3c",
        hovertemplate="%{y}: CI = %{x:.3f}<extra></extra>",
    ))

    fig.update_layout(
        title="Complexity Profile — Average CI per Floor",
        xaxis_title="Average Complexity Index",
        yaxis=dict(categoryorder="array", categoryarray=sorted_floors),
        template="plotly_white",
        height=max(400, len(sorted_floors) * 30 + 120),
        margin=dict(l=120, r=30, t=60, b=40),
    )
    return fig


# =============================================================================
# Dashboard Assembly
# =============================================================================

def generate_dashboard(
    project_path: str,
    output_path: Optional[str] = None,
    auto_open: bool = True,
) -> str:
    """Generate a 4-panel HTML dashboard and optionally open it in the browser.

    Args:
        project_path: Absolute or relative path to a project folder containing
                      elements_with_ci.json and floor_schedule.json.
        output_path:  Where to write the HTML. Defaults to <project_path>/dashboard.html.
        auto_open:    Whether to open the file in the default browser.

    Returns:
        The path to the generated HTML file.
    """
    data = load_project_data(project_path)
    elements = data["elements"]
    schedule = data["schedule"]
    project_id = data["project_id"]

    if output_path is None:
        output_path = os.path.join(project_path, "dashboard.html")

    # Build the four figures
    f1 = fig_steel_by_floor(elements)
    f2 = fig_steel_by_diameter(elements)
    f3 = fig_floor_schedule(schedule)
    f4 = fig_complexity_profile(elements)

    # Assemble HTML
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    header_html = (
        f"<h1 style='font-family:sans-serif;color:#1a5f7a;margin:24px 40px 4px 40px;'>"
        f"RC Agent Dashboard — {project_id}</h1>"
        f"<p style='font-family:sans-serif;color:#636e72;margin:0 40px 20px 40px;'>"
        f"Generated on {timestamp}</p>"
    )

    parts = [
        "<html><head><meta charset='utf-8'><title>RC Agent Dashboard</title></head><body>",
        header_html,
        f1.to_html(full_html=False, include_plotlyjs=True),
        f2.to_html(full_html=False, include_plotlyjs=False),
        f3.to_html(full_html=False, include_plotlyjs=False),
        f4.to_html(full_html=False, include_plotlyjs=False),
        "</body></html>",
    ]

    html_content = "\n".join(parts)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    if auto_open:
        webbrowser.open(f"file://{os.path.abspath(output_path)}")

    return output_path


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate an interactive HTML dashboard for an RC Agent project.",
    )
    parser.add_argument(
        "-p", "--project",
        help="Project name (subfolder under projects/). E.g. 'mokara'.",
    )
    parser.add_argument(
        "--project-path",
        help="Explicit absolute path to the project folder (overrides -p).",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output HTML file path. Default: projects/<name>/dashboard.html.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Don't auto-open the dashboard in the browser.",
    )
    args = parser.parse_args()

    if args.project_path:
        project_path = args.project_path
    elif args.project:
        project_path = os.path.join(RC_AGENT_PROJECTS, args.project)
    else:
        parser.error("Provide either -p/--project or --project-path.")

    if not os.path.isdir(project_path):
        parser.error(f"Project folder not found: {project_path}")

    html_path = generate_dashboard(
        project_path=project_path,
        output_path=args.output,
        auto_open=not args.no_open,
    )
    print(f"Dashboard saved to: {html_path}")


if __name__ == "__main__":
    main()
