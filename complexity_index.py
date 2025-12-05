#!/usr/bin/env python3
"""
Complexity Index (CI) Computation Module

This module computes a Complexity Index for reinforcement elements based on
their steel weight, bar counts, shapes, and diameters. It can be used as a
library (for LangChain tool integration) or run as a standalone CLI script.

Usage:
    python complexity_index.py [-i INPUT] [-o OUTPUT]

    Defaults:
        INPUT:  data/elements.json
        OUTPUT: data/elements_with_ci.json
"""

import sys
import json
import argparse
import copy
from typing import Dict, List, Any, Set


# =============================================================================
# Reference Constants
# =============================================================================

REF_W_TON = 0.50              # reference total steel weight per element (tons)
REF_BAR_COUNT_LONG = 40       # reference longitudinal bar count
REF_BAR_COUNT_TRANS = 150     # reference transverse bar/stirrup count
REF_SHAPES = 2                # reference number of shapes
REF_DIAMS = 2                 # reference number of bar diameters

W_W = 0.30    # weight for total weight ratio
W_BL = 0.30   # weight for longitudinal bar count ratio
W_BT = 0.30   # weight for transverse bar count ratio
W_SH = 0.05   # weight for number of longitudinal shapes
W_D = 0.05    # weight for number of longitudinal diameters


# =============================================================================
# Feature Extraction Functions
# =============================================================================

def _count_distinct_values(rows: List[Dict], key: str) -> int:
    """
    Count distinct non-null, non-empty values for a given key in a list of rows.
    """
    values: Set[str] = set()
    for row in rows:
        val = row.get(key)
        if val is not None and str(val).strip():
            values.add(str(val).strip())
    return len(values)


def _sum_cantidad(rows: List[Dict]) -> int:
    """
    Sum the 'cantidad' field across all rows.
    Treats missing or null values as 0.
    """
    total = 0
    for row in rows:
        cantidad = row.get("cantidad")
        if cantidad is not None:
            try:
                total += int(cantidad)
            except (ValueError, TypeError):
                pass
    return total


def _extract_features(reinforcement: Dict) -> Dict[str, Any]:
    """
    Extract CI features from the reinforcement data.

    Returns a dictionary with:
        - w_total_ton: total weight in tons
        - n_shapes_long: distinct longitudinal shapes
        - n_diams_long: distinct longitudinal diameters
        - bar_count_long: total longitudinal bar count
        - n_shapes_trans: distinct transverse shapes
        - n_diams_trans: distinct transverse diameters
        - bar_count_trans: total transverse bar count
    """
    # Get weight in tons
    w_total_kgf = reinforcement.get("w_total_kgf")
    if w_total_kgf is None:
        w_total_kgf = 0.0
    w_total_ton = float(w_total_kgf) / 1000.0

    # Get row lists
    long_rows = reinforcement.get("longitudinal_rows", [])
    trans_rows = reinforcement.get("transverse_rows", [])

    # Longitudinal features
    if long_rows:
        n_shapes_long = _count_distinct_values(long_rows, "figura")
        n_diams_long = _count_distinct_values(long_rows, "calibre")
        bar_count_long = _sum_cantidad(long_rows)
    else:
        n_shapes_long = 0
        n_diams_long = 0
        bar_count_long = 0

    # Transverse features
    if trans_rows:
        n_shapes_trans = _count_distinct_values(trans_rows, "figura")
        n_diams_trans = _count_distinct_values(trans_rows, "calibre")
        bar_count_trans = _sum_cantidad(trans_rows)
    else:
        n_shapes_trans = 0
        n_diams_trans = 0
        bar_count_trans = 0

    return {
        "w_total_ton": round(w_total_ton, 4),
        "n_shapes_long": n_shapes_long,
        "n_diams_long": n_diams_long,
        "bar_count_long": bar_count_long,
        "n_shapes_trans": n_shapes_trans,
        "n_diams_trans": n_diams_trans,
        "bar_count_trans": bar_count_trans,
    }


def _compute_ci(features: Dict[str, Any]) -> float:
    """
    Compute the Complexity Index from extracted features.

    Uses a weighted combination of ratios against reference values.
    """
    w_total_ton = features.get("w_total_ton", 0.0)
    bar_count_long = features.get("bar_count_long", 0)
    bar_count_trans = features.get("bar_count_trans", 0)
    n_shapes_long = features.get("n_shapes_long", 0)
    n_diams_long = features.get("n_diams_long", 0)

    # If no reinforcement, CI is 0
    if w_total_ton == 0.0:
        return 0.0

    # Compute ratios (with safety against division by zero)
    r_w = w_total_ton / REF_W_TON if REF_W_TON > 0 else 0.0
    r_bl = bar_count_long / REF_BAR_COUNT_LONG if REF_BAR_COUNT_LONG > 0 else 0.0
    r_bt = bar_count_trans / REF_BAR_COUNT_TRANS if REF_BAR_COUNT_TRANS > 0 else 0.0
    r_sh = n_shapes_long / REF_SHAPES if REF_SHAPES > 0 else 0.0
    r_d = n_diams_long / REF_DIAMS if REF_DIAMS > 0 else 0.0

    # Clamp ratios to minimum of 0.0 (no negatives)
    r_w = max(0.0, r_w)
    r_bl = max(0.0, r_bl)
    r_bt = max(0.0, r_bt)
    r_sh = max(0.0, r_sh)
    r_d = max(0.0, r_d)

    # Compute weighted CI
    ci_raw = W_W * r_w + W_BL * r_bl + W_BT * r_bt + W_SH * r_sh + W_D * r_d

    return round(ci_raw, 4)


# =============================================================================
# Public API Functions
# =============================================================================

def compute_ci_for_element(element: Dict) -> Dict:
    """
    Takes a single element dict (as in elements.json) and returns
    a NEW element dict with added 'ci' and 'ci_features'.
    The input element must not be mutated.

    Args:
        element: A dictionary representing a single structural element
                 with reinforcement data.

    Returns:
        A new dictionary with all original keys plus:
        - 'ci': float (Complexity Index)
        - 'ci_features': dict with intermediate feature values
    """
    # Create a deep copy to avoid mutating the input
    enriched = copy.deepcopy(element)

    # Get reinforcement data (empty dict if missing)
    reinforcement = element.get("reinforcement", {})
    if reinforcement is None:
        reinforcement = {}

    # Extract features
    features = _extract_features(reinforcement)

    # Compute CI
    ci = _compute_ci(features)

    # Add to enriched element
    enriched["ci"] = ci
    enriched["ci_features"] = features

    return enriched


def add_ci_to_elements(data: Dict) -> Dict:
    """
    Takes the full data dict loaded from elements.json:
        { "project_id": ..., "elements": [...] }
    and returns a NEW dict with the same structure, but with
    each element enriched with 'ci' and 'ci_features'.

    Args:
        data: Dictionary with 'project_id' and 'elements' keys.

    Returns:
        A new dictionary with the same structure, where each element
        has been enriched with CI data.
    """
    # Get project_id and elements list
    project_id = data.get("project_id", "Unknown")
    elements = data.get("elements", [])

    # Enrich each element
    enriched_elements = [compute_ci_for_element(elem) for elem in elements]

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
        description="Compute Complexity Index (CI) for reinforcement elements."
    )
    parser.add_argument(
        "-i", "--input",
        default="data/elements.json",
        help="Path to input JSON file (default: data/elements.json)"
    )
    parser.add_argument(
        "-o", "--output",
        default="data/elements_with_ci.json",
        help="Path to output JSON file (default: data/elements_with_ci.json)"
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

    # Compute CI for all elements
    enriched_data = add_ci_to_elements(data)

    # Write output file
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(enriched_data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Error: Could not write output file: {e}", file=sys.stderr)
        sys.exit(1)

    # Print summary
    elements = enriched_data.get("elements", [])
    print(f"Complexity Index Computation")
    print(f"=" * 40)
    print(f"Input:  {args.input}")
    print(f"Output: {args.output}")
    print(f"Project: {enriched_data.get('project_id', 'Unknown')}")
    print(f"Elements processed: {len(elements)}")

    if elements:
        ci_values = [e.get("ci", 0.0) for e in elements]
        avg_ci = sum(ci_values) / len(ci_values)
        min_ci = min(ci_values)
        max_ci = max(ci_values)

        print(f"\nCI Statistics:")
        print(f"  Min CI:  {min_ci:.4f}")
        print(f"  Max CI:  {max_ci:.4f}")
        print(f"  Avg CI:  {avg_ci:.4f}")

        # Show top 5 most complex elements
        sorted_elements = sorted(elements, key=lambda e: e.get("ci", 0.0), reverse=True)
        print(f"\nTop 5 Most Complex Elements:")
        for elem in sorted_elements[:5]:
            print(f"  {elem.get('floor_id', '?')}/{elem.get('element_id', '?')}: CI={elem.get('ci', 0.0):.4f}")

    print(f"\nOutput written to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
