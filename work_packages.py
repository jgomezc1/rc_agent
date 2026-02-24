#!/usr/bin/env python3
"""
Work Packages Aggregation Module

This module aggregates element-level predictions (with CI and productivity)
into work packages per floor/zone/work type. It can be used as a library
(for LangChain tool integration) or run as a standalone CLI script.

Usage:
    python work_packages.py [-i INPUT] [-o OUTPUT]

    Defaults:
        INPUT:  data/elements_with_prod.json
        OUTPUT: data/work_packages.json
"""

import sys
import json
import argparse
from typing import Dict, List, Any


# =============================================================================
# Work Type Mapping
# =============================================================================

def map_element_to_work_type(element: Dict) -> str:
    """
    Takes a single element dict and returns a work_type string
    (e.g. 'rebar_beams', 'rebar_columns', etc.).

    Args:
        element: A dictionary representing a structural element.

    Returns:
        A string representing the work type.
    """
    element_type = element.get("element_type", "")
    if element_type is None:
        element_type = ""
    element_type = element_type.lower()

    if element_type == "beam":
        return "rebar_beams"
    elif element_type == "column":
        return "rebar_columns"
    elif element_type == "wall":
        return "rebar_walls"
    elif element_type == "slab":
        return "rebar_slabs"
    else:
        return "rebar_unknown"


# =============================================================================
# Aggregation Functions
# =============================================================================

def _get_w_total_ton(element: Dict) -> float:
    """
    Extract w_total_ton from element, preferring ci_features.
    Falls back to reinforcement.w_total_kgf / 1000.
    """
    ci_features = element.get("ci_features")
    if ci_features is not None:
        w_total_ton = ci_features.get("w_total_ton")
        if w_total_ton is not None:
            return float(w_total_ton)

    # Fallback to reinforcement
    reinforcement = element.get("reinforcement", {})
    if reinforcement is None:
        reinforcement = {}
    w_total_kgf = reinforcement.get("w_total_kgf", 0.0)
    if w_total_kgf is None:
        w_total_kgf = 0.0
    return float(w_total_kgf) / 1000.0


def _get_crew_hours(element: Dict) -> float:
    """
    Extract crew_hours_pred from element.
    Returns 0.0 if missing or None.
    """
    crew_hours = element.get("crew_hours_pred", 0.0)
    if crew_hours is None:
        crew_hours = 0.0
    return float(crew_hours)


def build_work_packages(data: Dict) -> Dict:
    """
    Takes the full data dict loaded from elements_with_prod.json:
        { "project_id": ..., "elements": [...] }
    and returns a NEW dict with aggregated work packages per
    (floor_id, zone_id, work_type).

    Args:
        data: Dictionary with 'project_id' and 'elements' keys.

    Returns:
        A new dictionary with:
        - 'project_id': same as input
        - 'work_packages': list of aggregated work package dicts
    """
    project_id = data.get("project_id", "Unknown")
    elements = data.get("elements", [])

    if elements is None or not isinstance(elements, list):
        elements = []

    # Aggregation structure keyed by (floor_id, zone_id, work_type)
    packages: Dict[tuple, Dict[str, Any]] = {}

    for element in elements:
        # Extract grouping keys
        floor_id = element.get("floor_id")
        zone_id = element.get("zone_id")  # May be None
        element_id = element.get("element_id")
        element_type = element.get("element_type")

        # Compute work type
        work_type = map_element_to_work_type(element)

        # Extract values to aggregate
        w_total_ton = _get_w_total_ton(element)
        crew_hours = _get_crew_hours(element)

        # Create tuple key
        key = (floor_id, zone_id, work_type)

        # Initialize package if new key
        if key not in packages:
            packages[key] = {
                "floor_id": floor_id,
                "zone_id": zone_id,
                "work_type": work_type,
                "element_type": element_type,
                "element_ids": [],
                "n_elements": 0,
                "w_total_ton": 0.0,
                "crew_hours_total": 0.0,
            }

        # Accumulate
        pkg = packages[key]
        pkg["element_ids"].append(element_id)
        pkg["n_elements"] += 1
        pkg["w_total_ton"] += w_total_ton
        pkg["crew_hours_total"] += crew_hours

    # Round aggregated values
    for pkg in packages.values():
        pkg["w_total_ton"] = round(pkg["w_total_ton"], 4)
        pkg["crew_hours_total"] = round(pkg["crew_hours_total"], 4)

    # Build final list
    work_packages_list = list(packages.values())

    return {
        "project_id": project_id,
        "work_packages": work_packages_list
    }


# =============================================================================
# CLI Entrypoint
# =============================================================================

def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Aggregate element-level data into work packages."
    )
    parser.add_argument(
        "-i", "--input",
        default="data/elements_with_prod.json",
        help="Path to input JSON file (default: data/elements_with_prod.json)"
    )
    parser.add_argument(
        "-o", "--output",
        default="data/work_packages.json",
        help="Path to output JSON file (default: data/work_packages.json)"
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

    # Build work packages
    result = build_work_packages(data)

    # Write output file
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Error: Could not write output file: {e}", file=sys.stderr)
        sys.exit(1)

    # Print summary
    work_packages = result.get("work_packages", [])
    print(f"Work Packages Aggregation")
    print(f"=" * 40)
    print(f"Input:  {args.input}")
    print(f"Output: {args.output}")
    print(f"Project: {result.get('project_id', 'Unknown')}")
    print(f"Work packages created: {len(work_packages)}")

    if work_packages:
        # Summary by floor
        floors = {}
        for pkg in work_packages:
            floor = pkg.get("floor_id", "Unknown")
            if floor not in floors:
                floors[floor] = {"packages": 0, "elements": 0, "crew_hours": 0.0, "weight": 0.0}
            floors[floor]["packages"] += 1
            floors[floor]["elements"] += pkg.get("n_elements", 0)
            floors[floor]["crew_hours"] += pkg.get("crew_hours_total", 0.0)
            floors[floor]["weight"] += pkg.get("w_total_ton", 0.0)

        print(f"\nSummary by Floor:")
        print(f"{'Floor':<20} {'Pkgs':>6} {'Elems':>7} {'Tons':>8} {'Crew-Hrs':>10}")
        print(f"-" * 55)

        # Sort floors
        def floor_sort_key(f):
            import re
            match = re.search(r'\d+', str(f))
            return (int(match.group()) if match else 0, str(f))

        for floor in sorted(floors.keys(), key=floor_sort_key):
            info = floors[floor]
            print(f"{floor:<20} {info['packages']:>6} {info['elements']:>7} "
                  f"{info['weight']:>8.2f} {info['crew_hours']:>10.2f}")

        # Summary by work type
        work_types = {}
        for pkg in work_packages:
            wt = pkg.get("work_type", "unknown")
            if wt not in work_types:
                work_types[wt] = {"packages": 0, "elements": 0, "crew_hours": 0.0, "weight": 0.0}
            work_types[wt]["packages"] += 1
            work_types[wt]["elements"] += pkg.get("n_elements", 0)
            work_types[wt]["crew_hours"] += pkg.get("crew_hours_total", 0.0)
            work_types[wt]["weight"] += pkg.get("w_total_ton", 0.0)

        print(f"\nSummary by Work Type:")
        print(f"{'Work Type':<20} {'Pkgs':>6} {'Elems':>7} {'Tons':>8} {'Crew-Hrs':>10}")
        print(f"-" * 55)
        for wt in sorted(work_types.keys()):
            info = work_types[wt]
            print(f"{wt:<20} {info['packages']:>6} {info['elements']:>7} "
                  f"{info['weight']:>8.2f} {info['crew_hours']:>10.2f}")

        # Totals
        total_weight = sum(pkg.get("w_total_ton", 0.0) for pkg in work_packages)
        total_crew_hours = sum(pkg.get("crew_hours_total", 0.0) for pkg in work_packages)
        total_elements = sum(pkg.get("n_elements", 0) for pkg in work_packages)

        print(f"\nTotals:")
        print(f"  Elements: {total_elements}")
        print(f"  Steel: {total_weight:.2f} tons")
        print(f"  Crew-Hours: {total_crew_hours:.2f}")

    print(f"\nOutput written to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
