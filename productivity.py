#!/usr/bin/env python3
"""
Productivity Computation Module

This module computes predicted productivity and crew-hours for reinforcement
elements based on their Complexity Index (CI) and total weight. It can be used
as a library (for LangChain tool integration) or run as a standalone CLI script.

Usage:
    python productivity.py [-i INPUT] [-o OUTPUT]

    Defaults:
        INPUT:  data/elements_with_ci.json
        OUTPUT: data/elements_with_prod.json
"""

import sys
import json
import argparse
import copy
from typing import Dict, Any


# =============================================================================
# Model Constants
# =============================================================================

BASE_PRODUCTIVITIES = {
    "beam":   0.05,   # tons per crew-hour
    "column": 0.04,
    "wall":   0.04,
    "slab":   0.06,
}

DEFAULT_BASE_PRODUCTIVITY = 0.08  # tons per crew-hour

K_VALUES = {
    "beam":   1.0,
    "column": 0.5,
    "wall":   0.5,
    "slab":   0.5,
}

DEFAULT_K_VALUE = 0.5


# =============================================================================
# Public API Functions
# =============================================================================

def compute_productivity_for_element(element: Dict) -> Dict:
    """
    Takes a single CI-enriched element dict and returns a NEW element dict
    with added productivity fields:
    - 'prod_pred_ton_per_crew_hour'
    - 'crew_hours_pred'

    The input element must not be mutated.

    Args:
        element: A dictionary representing a single structural element
                 with CI data (ci, ci_features).

    Returns:
        A new dictionary with all original keys plus:
        - 'prod_pred_ton_per_crew_hour': float
        - 'crew_hours_pred': float
    """
    # Extract CI
    ci = element.get("ci", 0.0)
    if ci is None:
        ci = 0.0

    # Extract w_total_ton
    ci_features = element.get("ci_features", {})
    if ci_features is None:
        ci_features = {}

    w_total_ton = ci_features.get("w_total_ton")

    if w_total_ton is None:
        # Compute from reinforcement if not in ci_features
        reinforcement = element.get("reinforcement", {})
        if reinforcement is None:
            reinforcement = {}
        w_total_kgf = reinforcement.get("w_total_kgf", 0.0)
        if w_total_kgf is None:
            w_total_kgf = 0.0
        w_total_ton = float(w_total_kgf) / 1000.0

    # Handle negative or None
    if w_total_ton is None or w_total_ton < 0:
        w_total_ton = 0.0

    # Extract element type
    element_type = element.get("element_type", "unknown")
    if element_type is None:
        element_type = "unknown"

    # Get base productivity and k value
    base_prod = BASE_PRODUCTIVITIES.get(element_type, DEFAULT_BASE_PRODUCTIVITY)
    k = K_VALUES.get(element_type, DEFAULT_K_VALUE)

    # Handle edge case: no reinforcement
    if w_total_ton <= 0.0:
        prod_pred = 0.0
        crew_hours_pred = 0.0
    else:
        # Determine effective CI
        if ci <= 0.0:
            ci_effective = 1.0
        else:
            ci_effective = ci

        # Compute productivity
        denom = 1.0 + k * (ci_effective - 1.0)
        if denom <= 0.0:
            denom = 0.1  # Safety clamp

        prod_pred = base_prod / denom  # tons per crew-hour

        # Compute crew-hours
        crew_hours_pred = w_total_ton / prod_pred

    # Round to reasonable precision
    prod_pred = round(prod_pred, 4)
    crew_hours_pred = round(crew_hours_pred, 4)

    # Create new enriched element (deep copy to avoid mutation)
    enriched = copy.deepcopy(element)
    enriched["prod_pred_ton_per_crew_hour"] = prod_pred
    enriched["crew_hours_pred"] = crew_hours_pred

    return enriched


def add_productivity_to_elements(data: Dict) -> Dict:
    """
    Takes the full data dict loaded from elements_with_ci.json:
        { "project_id": ..., "elements": [...] }
    and returns a NEW dict with the same structure, but with
    each element enriched with productivity-related fields.

    Args:
        data: Dictionary with 'project_id' and 'elements' keys.

    Returns:
        A new dictionary with the same structure, where each element
        has been enriched with productivity data.
    """
    project_id = data.get("project_id", "Unknown")
    elements = data.get("elements", [])

    if elements is None or not isinstance(elements, list):
        elements = []

    # Enrich each element
    enriched_elements = [compute_productivity_for_element(e) for e in elements]

    # Return new dict (not mutating input)
    return {
        "project_id": project_id,
        "elements": enriched_elements
    }


# =============================================================================
# CLI Entrypoint
# =============================================================================

def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Compute productivity predictions for reinforcement elements."
    )
    parser.add_argument(
        "-i", "--input",
        default="data/elements_with_ci.json",
        help="Path to input JSON file (default: data/elements_with_ci.json)"
    )
    parser.add_argument(
        "-o", "--output",
        default="data/elements_with_prod.json",
        help="Path to output JSON file (default: data/elements_with_prod.json)"
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

    # Compute productivity for all elements
    enriched_data = add_productivity_to_elements(data)

    # Write output file
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(enriched_data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Error: Could not write output file: {e}", file=sys.stderr)
        sys.exit(1)

    # Print summary
    elements = enriched_data.get("elements", [])
    print(f"Productivity Computation")
    print(f"=" * 40)
    print(f"Input:  {args.input}")
    print(f"Output: {args.output}")
    print(f"Project: {enriched_data.get('project_id', 'Unknown')}")
    print(f"Elements processed: {len(elements)}")

    if elements:
        # Filter elements with actual reinforcement
        valid_elements = [e for e in elements if e.get("crew_hours_pred", 0) > 0]

        if valid_elements:
            prod_values = [e.get("prod_pred_ton_per_crew_hour", 0.0) for e in valid_elements]
            crew_hours = [e.get("crew_hours_pred", 0.0) for e in valid_elements]

            avg_prod = sum(prod_values) / len(prod_values)
            min_prod = min(prod_values)
            max_prod = max(prod_values)

            total_crew_hours = sum(crew_hours)
            avg_crew_hours = sum(crew_hours) / len(crew_hours)

            print(f"\nProductivity Statistics (tons/crew-hour):")
            print(f"  Min:  {min_prod:.4f}")
            print(f"  Max:  {max_prod:.4f}")
            print(f"  Avg:  {avg_prod:.4f}")

            print(f"\nCrew-Hours Statistics:")
            print(f"  Total: {total_crew_hours:.2f} crew-hours")
            print(f"  Avg per element: {avg_crew_hours:.2f} crew-hours")

            # Show top 5 most labor-intensive elements
            sorted_elements = sorted(valid_elements, key=lambda e: e.get("crew_hours_pred", 0.0), reverse=True)
            print(f"\nTop 5 Most Labor-Intensive Elements:")
            for elem in sorted_elements[:5]:
                floor = elem.get('floor_id', '?')
                eid = elem.get('element_id', '?')
                ch = elem.get('crew_hours_pred', 0.0)
                prod = elem.get('prod_pred_ton_per_crew_hour', 0.0)
                print(f"  {floor}/{eid}: {ch:.2f} crew-hrs (prod={prod:.4f} ton/ch)")

    print(f"\nOutput written to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
