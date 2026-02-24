#!/usr/bin/env python3
"""
Floor Schedule Module

This module computes predicted durations for each work package (per floor/zone/work_type)
based on crew capacity. It can be used as a library (for LangChain tool integration)
or run as a standalone CLI script.

Usage:
    python floor_schedule.py [-i INPUT] [-o OUTPUT] [--hours-per-day HPD]

    Defaults:
        INPUT:  data/work_packages.json
        OUTPUT: data/floor_schedule.json
        HPD:    8.0
"""

import sys
import json
import argparse
import copy
from typing import Dict, List, Any


# =============================================================================
# Default Constants
# =============================================================================

DEFAULT_HOURS_PER_DAY = 8.0

DEFAULT_CREWS_PER_WORK_TYPE = {
    "rebar_beams": 2,
    "rebar_columns": 1,
    "rebar_walls": 1,
    "rebar_slabs": 2,
    "rebar_unknown": 1,
}


# =============================================================================
# Duration Computation
# =============================================================================

def compute_duration_for_package(
    pkg: Dict,
    crews_per_work_type: Dict,
    hours_per_day: float
) -> Dict:
    """
    Takes a single work package dict and returns a NEW dict
    with added duration fields based on the available crews
    and working hours per day.

    Args:
        pkg: A work package dictionary with crew_hours_total and work_type.
        crews_per_work_type: Dict mapping work_type to number of crews.
        hours_per_day: Working hours per day.

    Returns:
        A new dict with all original keys plus:
        - 'n_crews_assigned': number of crews for this work_type
        - 'duration_days': predicted duration in calendar days
    """
    # Extract values from package
    work_type = pkg.get("work_type")
    crew_hours_total = pkg.get("crew_hours_total", 0.0)
    if crew_hours_total is None:
        crew_hours_total = 0.0
    crew_hours_total = float(crew_hours_total)

    # Determine number of crews for this work_type
    n_crews = crews_per_work_type.get(work_type, 1)
    if n_crews is None or n_crews <= 0:
        n_crews = 1

    # Handle hours_per_day
    if hours_per_day is None or hours_per_day <= 0.0:
        hours_per_day = DEFAULT_HOURS_PER_DAY

    # Compute daily crew capacity
    daily_capacity = n_crews * hours_per_day  # crew-hours per day
    if daily_capacity <= 0.0:
        daily_capacity = 1.0  # Safety clamp

    # Compute duration in days
    duration_days = crew_hours_total / daily_capacity

    # Round to reasonable precision
    duration_days = round(duration_days, 4)

    # Create new dict with all original keys plus new fields
    result = copy.deepcopy(pkg)
    result["n_crews_assigned"] = n_crews
    result["duration_days"] = duration_days

    return result


# =============================================================================
# Floor Schedule Builder
# =============================================================================

def build_floor_schedule(
    data: Dict,
    crews_per_work_type: Dict,
    hours_per_day: float
) -> Dict:
    """
    Takes the full data dict loaded from work_packages.json:
        { "project_id": ..., "work_packages": [...] }
    and returns a NEW dict with per-floor schedules, including
    durations per package and per floor.

    Args:
        data: Dictionary with 'project_id' and 'work_packages' keys.
        crews_per_work_type: Dict mapping work_type to number of crews.
        hours_per_day: Working hours per day.

    Returns:
        A new dictionary with:
        - 'project_id': same as input
        - 'hours_per_day': the hours per day used
        - 'crews_per_work_type': the crew allocation used
        - 'floors': list of floor schedule dicts
    """
    project_id = data.get("project_id", "Unknown")
    packages = data.get("work_packages", [])

    if packages is None or not isinstance(packages, list):
        packages = []

    # Handle hours_per_day default
    if hours_per_day is None or hours_per_day <= 0.0:
        hours_per_day = DEFAULT_HOURS_PER_DAY

    # Group packages by floor_id
    floors: Dict[str, Dict[str, Any]] = {}

    for pkg in packages:
        # Compute duration for this package
        pkg_sched = compute_duration_for_package(pkg, crews_per_work_type, hours_per_day)

        # Get floor_id
        floor_id = pkg_sched.get("floor_id")

        # Initialize floor entry if needed
        if floor_id not in floors:
            floors[floor_id] = {
                "floor_id": floor_id,
                "packages": [],
                "floor_duration_days": 0.0
            }

        # Append package to floor
        floors[floor_id]["packages"].append(pkg_sched)

    # Compute floor_duration_days for each floor (max of package durations)
    for floor_id, floor_data in floors.items():
        pkgs = floor_data["packages"]
        if pkgs:
            max_duration = max(p.get("duration_days", 0.0) for p in pkgs)
        else:
            max_duration = 0.0
        floor_data["floor_duration_days"] = round(max_duration, 4)

    # Build final list
    floors_list = list(floors.values())

    return {
        "project_id": project_id,
        "hours_per_day": hours_per_day,
        "crews_per_work_type": crews_per_work_type,
        "floors": floors_list
    }


# =============================================================================
# CLI Entrypoint
# =============================================================================

def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Compute floor schedules from work packages."
    )
    parser.add_argument(
        "-i", "--input",
        default="data/work_packages.json",
        help="Path to input JSON file (default: data/work_packages.json)"
    )
    parser.add_argument(
        "-o", "--output",
        default="data/floor_schedule.json",
        help="Path to output JSON file (default: data/floor_schedule.json)"
    )
    parser.add_argument(
        "--hours-per-day", "-hpd",
        type=float,
        default=DEFAULT_HOURS_PER_DAY,
        help=f"Working hours per day (default: {DEFAULT_HOURS_PER_DAY})"
    )

    args = parser.parse_args()

    # Load input file
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
        sys.exit(1)

    # Build floor schedule
    schedule = build_floor_schedule(
        data,
        crews_per_work_type=DEFAULT_CREWS_PER_WORK_TYPE,
        hours_per_day=args.hours_per_day
    )

    # Write output file
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(schedule, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Error: Could not write output file: {e}", file=sys.stderr)
        sys.exit(1)

    # Print summary
    floors = schedule.get("floors", [])
    print(f"Floor Schedule Computation")
    print(f"=" * 50)
    print(f"Input:  {args.input}")
    print(f"Output: {args.output}")
    print(f"Project: {schedule.get('project_id', 'Unknown')}")
    print(f"Hours per day: {schedule.get('hours_per_day', 0.0)}")
    print(f"Floors scheduled: {len(floors)}")

    print(f"\nCrew Allocation:")
    for wt, n_crews in schedule.get("crews_per_work_type", {}).items():
        print(f"  {wt}: {n_crews} crew(s)")

    if floors:
        print(f"\nFloor Schedule Summary:")
        print(f"{'Floor':<20} {'Pkgs':>6} {'Duration (days)':>16}")
        print(f"-" * 45)

        # Sort floors
        def floor_sort_key(f):
            import re
            floor_id = f.get("floor_id", "")
            match = re.search(r'\d+', str(floor_id))
            return (int(match.group()) if match else 0, str(floor_id))

        total_duration = 0.0
        for floor in sorted(floors, key=floor_sort_key):
            floor_id = floor.get("floor_id", "Unknown")
            n_pkgs = len(floor.get("packages", []))
            duration = floor.get("floor_duration_days", 0.0)
            total_duration += duration
            print(f"{floor_id:<20} {n_pkgs:>6} {duration:>16.2f}")

        print(f"-" * 45)
        print(f"{'TOTAL':<20} {len(floors):>6} {total_duration:>16.2f}")

        # Summary statistics
        durations = [f.get("floor_duration_days", 0.0) for f in floors]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        min_duration = min(durations) if durations else 0.0
        max_duration = max(durations) if durations else 0.0

        print(f"\nDuration Statistics:")
        print(f"  Min: {min_duration:.2f} days")
        print(f"  Max: {max_duration:.2f} days")
        print(f"  Avg: {avg_duration:.2f} days")
        print(f"  Sum: {total_duration:.2f} days (sequential)")

    print(f"\nOutput written to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
