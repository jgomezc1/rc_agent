"""
Phase-1 Reinforcement Solution (RS) Selector for StructuBIM

From shop_drawings.json, parse all candidate RS options and select/rank
the best solution(s) per user intent, constraints, and objective presets.
"""

import json
import re
from enum import Enum
from typing import Dict, List, Tuple, Optional, Union, Set
from dataclasses import dataclass


class RSObjective(Enum):
    """Predefined objective presets for RS selection"""
    MIN_COST = "min_cost"
    FASTEST = "fastest"
    LOW_CARBON = "low_carbon"
    HIGH_CONSTRUCT = "high_construct"
    BALANCED = "balanced"


class ConstraintError(Exception):
    """Raised when constraint references unknown field or invalid format"""
    pass


@dataclass
class RSDecoding:
    """Structure for decoded RS code components"""
    grouped: bool
    join: str  # 'EM' or 'TR'
    bars: Dict[str, int]  # {'min': int, 'max': int}
    L: int  # Length granularity (10, 20, 50, 100)


def load_catalog(path: str) -> Dict[str, Dict]:
    """Load RS catalog from shop_drawings.json"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            catalog = json.load(f)

        if not catalog:
            raise ValueError("Empty catalog file")

        # Validate that all entries have required fields
        required_fields = {
            'steel_tonnage', 'concrete_volume', 'steel_cost', 'concrete_cost',
            'manhours', 'duration_days', 'co2_tonnes', 'constructibility_index',
            'bar_geometries'
        }

        for rs_code, data in catalog.items():
            missing_fields = required_fields - set(data.keys())
            if missing_fields:
                raise ValueError(f"RS {rs_code} missing fields: {missing_fields}")

        return catalog

    except FileNotFoundError:
        raise FileNotFoundError(f"Catalog file not found: {path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in catalog file: {e}")


def decode_rs_code(code: str) -> Dict:
    """
    Decode RS code mnemonic into components

    Examples:
    - AG_EM_5a8_L50 → grouped=True, join='EM', bars={'min':5,'max':8}, L=50
    - TR_6_L10 → grouped=False, join='TR', bars={'min':6,'max':6}, L=10

    Returns:
    {
      'grouped': bool, 'join': 'EM'|'TR',
      'bars': {'min': int, 'max': int},
      'L': int,  # e.g., 10, 20, 50, 100
    }
    """
    # Regex pattern from specification
    pattern = r'^(?P<grouped>AG_)?(?P<join>EM|TR)_(?P<bars>\d+(?:a\d+)?)_(?P<L>L\d+)$'

    match = re.match(pattern, code)
    if not match:
        raise ValueError(f"Invalid RS code format: {code}")

    groups = match.groupdict()

    # Parse grouped prefix
    grouped = groups['grouped'] is not None

    # Parse join type
    join = groups['join']

    # Parse bars range
    bars_str = groups['bars']
    if 'a' in bars_str:
        # Range format like "5a8"
        min_bar, max_bar = map(int, bars_str.split('a'))
    else:
        # Single bar format like "6"
        min_bar = max_bar = int(bars_str)

    bars = {'min': min_bar, 'max': max_bar}

    # Parse length granularity
    L = int(groups['L'][1:])  # Remove 'L' prefix

    return {
        'grouped': grouped,
        'join': join,
        'bars': bars,
        'L': L
    }


def build_objective_weights(obj: RSObjective) -> Dict[str, float]:
    """Build weight dictionary for given objective preset"""

    weight_presets = {
        RSObjective.MIN_COST: {
            'steel_cost': 0.45,
            'concrete_cost': 0.25,
            'manhours': 0.15,
            'duration_days': 0.10,
            'co2_tonnes': 0.05
        },
        RSObjective.FASTEST: {
            'duration_days': 0.55,
            'manhours': 0.25,
            'steel_cost': 0.10,
            'concrete_cost': 0.05,
            'co2_tonnes': 0.05
        },
        RSObjective.LOW_CARBON: {
            'co2_tonnes': 0.60,
            'steel_tonnage': 0.20,
            'duration_days': 0.10,
            'steel_cost': 0.10
        },
        RSObjective.HIGH_CONSTRUCT: {
            'constructibility_index': 0.55,
            'bar_geometries': 0.25,
            'manhours': 0.10,
            'duration_days': 0.10
        },
        RSObjective.BALANCED: {
            'steel_tonnage': 1/8,
            'steel_cost': 1/8,
            'concrete_cost': 1/8,
            'manhours': 1/8,
            'duration_days': 1/8,
            'co2_tonnes': 1/8,
            'constructibility_index': 1/8,
            'bar_geometries': 1/8
        }
    }

    return weight_presets[obj]


def apply_constraints(catalog: Dict[str, Dict], *,
                     join: Optional[List[str]] = None,
                     grouped: Optional[bool] = None,
                     bars: Optional[str] = None,  # '5-8', '6', '6-6'
                     L: Optional[List[int]] = None,  # [10,50]
                     kpi_filters: Optional[Dict] = None  # e.g., {'duration_days': ('<=', 70)}
                     ) -> Dict[str, Dict]:
    """Apply constraints to filter catalog"""

    filtered_catalog = {}

    for rs_code, data in catalog.items():
        try:
            # Decode RS for mnemonic constraints
            decoded = decode_rs_code(rs_code)

            # Check mnemonic constraints
            if join is not None and decoded['join'] not in join:
                continue

            if grouped is not None and decoded['grouped'] != grouped:
                continue

            if bars is not None:
                # Parse bars constraint (e.g., '5-8', '6', '6-6')
                if '-' in bars and bars.count('-') == 1:
                    # Range format '5-8' - RS must have exactly this range
                    req_min, req_max = map(int, bars.split('-'))
                    if not (decoded['bars']['min'] == req_min and decoded['bars']['max'] == req_max):
                        continue
                else:
                    # Single value format '6' - RS must contain this bar size
                    req_bar = int(bars)
                    if not (decoded['bars']['min'] <= req_bar <= decoded['bars']['max']):
                        continue

            if L is not None and decoded['L'] not in L:
                continue

            # Check KPI constraints
            if kpi_filters:
                skip_rs = False
                for metric, (operator, value) in kpi_filters.items():
                    if metric not in data:
                        raise ConstraintError(f"Metric '{metric}' not found in RS data")

                    rs_value = data[metric]

                    if operator == '<=':
                        if not (rs_value <= value):
                            skip_rs = True
                            break
                    elif operator == '<':
                        if not (rs_value < value):
                            skip_rs = True
                            break
                    elif operator == '>=':
                        if not (rs_value >= value):
                            skip_rs = True
                            break
                    elif operator == '>':
                        if not (rs_value > value):
                            skip_rs = True
                            break
                    elif operator == '==':
                        if not (rs_value == value):
                            skip_rs = True
                            break
                    elif operator == '!=':
                        if not (rs_value != value):
                            skip_rs = True
                            break
                    else:
                        raise ConstraintError(f"Unsupported operator: {operator}")

                if skip_rs:
                    continue

            # RS passed all constraints
            filtered_catalog[rs_code] = data

        except ValueError as e:
            # Skip RS with invalid code format
            print(f"Warning: Skipping RS {rs_code} due to invalid format: {e}")
            continue

    return filtered_catalog


def normalize_metrics(catalog: Dict[str, Dict], metric_keys: List[str]) -> Dict[str, Dict]:
    """
    Normalize metrics to [0,1] using min-max scaling
    All metrics are oriented to "lower is better" (0 = best, 1 = worst)
    """
    if not catalog:
        return catalog

    # Find min/max for each metric
    metric_ranges = {}
    for metric in metric_keys:
        values = []
        for rs_data in catalog.values():
            if metric in rs_data:
                values.append(rs_data[metric])

        if values:
            metric_ranges[metric] = {
                'min': min(values),
                'max': max(values)
            }

    # Normalize catalog
    normalized_catalog = {}
    for rs_code, data in catalog.items():
        normalized_data = data.copy()

        for metric in metric_keys:
            if metric in data and metric in metric_ranges:
                min_val = metric_ranges[metric]['min']
                max_val = metric_ranges[metric]['max']

                if max_val == min_val:
                    # All values are the same, normalize to 0
                    normalized_data[f"{metric}_norm"] = 0.0
                else:
                    # Min-max normalization (lower is better)
                    raw_val = data[metric]
                    normalized_val = (raw_val - min_val) / (max_val - min_val)
                    normalized_data[f"{metric}_norm"] = normalized_val

        normalized_catalog[rs_code] = normalized_data

    return normalized_catalog


def score_weighted_sum(catalog: Dict[str, Dict],
                      weights: Dict[str, float]) -> List[Tuple[str, float]]:
    """
    Calculate weighted sum scores for all RS options
    Return sorted list of (rs_code, score); lower is better
    """
    scores = []

    for rs_code, data in catalog.items():
        score = 0.0
        total_weight = 0.0

        for metric, weight in weights.items():
            norm_key = f"{metric}_norm"
            if norm_key in data:
                score += weight * data[norm_key]
                total_weight += weight

        # Normalize score by actual total weight used
        if total_weight > 0:
            final_score = score / total_weight
        else:
            final_score = float('inf')  # No valid metrics

        scores.append((rs_code, final_score))

    # Sort by score (lower is better)
    scores.sort(key=lambda x: x[1])

    return scores


def pareto_front(catalog: Dict[str, Dict], metrics: List[str]) -> Set[str]:
    """
    Compute Pareto frontier over chosen metrics
    Returns set of non-dominated RS codes
    """
    rs_codes = list(catalog.keys())
    pareto_set = set()

    for i, rs1 in enumerate(rs_codes):
        data1 = catalog[rs1]
        is_dominated = False

        for j, rs2 in enumerate(rs_codes):
            if i == j:
                continue

            data2 = catalog[rs2]

            # Check if rs1 is dominated by rs2
            # rs2 dominates rs1 if rs2 is better or equal in all metrics
            # and strictly better in at least one
            better_count = 0
            worse_count = 0

            for metric in metrics:
                norm_key = f"{metric}_norm"
                if norm_key in data1 and norm_key in data2:
                    val1 = data1[norm_key]
                    val2 = data2[norm_key]

                    if val2 < val1:  # rs2 is better (lower is better)
                        better_count += 1
                    elif val2 > val1:  # rs2 is worse
                        worse_count += 1

            # rs2 dominates rs1 if rs2 is better in at least one metric
            # and not worse in any metric
            if better_count > 0 and worse_count == 0:
                is_dominated = True
                break

        if not is_dominated:
            pareto_set.add(rs1)

    return pareto_set


def generate_detailed_explanation(result: Dict, objective: RSObjective) -> str:
    """
    Generate detailed natural language explanation of the analysis results
    """
    explanation_parts = []

    # Objective explanation
    obj_explanations = {
        RSObjective.MIN_COST: "You prioritized minimizing total project costs, emphasizing steel and concrete expenses with moderate weight on labor and schedule.",
        RSObjective.FASTEST: "You prioritized speed of construction, heavily weighting duration and manhours to minimize project timeline.",
        RSObjective.LOW_CARBON: "You prioritized environmental sustainability, heavily weighting CO2 emissions and steel tonnage to minimize carbon footprint.",
        RSObjective.HIGH_CONSTRUCT: "You prioritized constructibility, emphasizing simplicity through constructibility index and reduced bar geometry complexity.",
        RSObjective.BALANCED: "You chose equal weighting across all criteria—cost, time, labor, CO2, tonnage, constructibility, and bar-geometry complexity get equal consideration in a true compromise approach."
    }

    explanation_parts.append(f"**OBJECTIVE INTERPRETATION:**")
    explanation_parts.append(obj_explanations.get(objective, "Custom objective weighting applied."))

    # Pareto frontier analysis
    pareto_size = result.get('pareto_size', 0)
    total_candidates = result.get('total_candidates', 0)

    explanation_parts.append(f"\n**PARETO EFFICIENCY:**")
    explanation_parts.append(f"Out of {total_candidates} candidates, only {pareto_size} were non-dominated—meaning no other solution beats them across all metrics simultaneously.")

    if pareto_size > 1:
        pareto_codes = result.get('pareto_frontier', [])[:3]  # Show top 3
        explanation_parts.append(f"The efficient solutions are: {', '.join(pareto_codes)}.")
        explanation_parts.append("These form the 'efficient frontier'—everything else is suboptimal on at least one KPI without compensating advantages.")
    else:
        explanation_parts.append("Only one solution dominated all others across the weighted criteria.")

    # Recommendation explanation
    recommendations = result.get('recommendations', [])
    if recommendations:
        best_rec = recommendations[0]
        best_code = best_rec['rs_code']

        try:
            decoded = decode_rs_code(best_code)
            explanation_parts.append(f"\n**RECOMMENDED SOLUTION BREAKDOWN:**")
            explanation_parts.append(f"**{best_code}** decodes as:")

            if decoded['grouped']:
                explanation_parts.append(f"• **AG (Grouped)**: Standardized lengths reduce procurement complexity and stabilize supply lots")
            else:
                explanation_parts.append(f"• **Non-grouped**: Allows flexible length optimization per element")

            join_desc = "mechanical couplers" if decoded['join'] == 'EM' else "traditional lap splices"
            explanation_parts.append(f"• **{decoded['join']} (Join)**: Uses {join_desc}")

            if decoded['bars']['min'] == decoded['bars']['max']:
                explanation_parts.append(f"• **Bar #{decoded['bars']['min']}**: Single diameter simplifies procurement and installation")
            else:
                explanation_parts.append(f"• **Bars #{decoded['bars']['min']}-{decoded['bars']['max']}**: Mixed diameters optimize material usage and reduce congestion")

            explanation_parts.append(f"• **L{decoded['L']} (Length)**: Cut in {decoded['L']}cm increments")

            if decoded['L'] <= 20:
                explanation_parts.append(f"  → Fine granularity maximizes cutting efficiency and waste reduction")
            else:
                explanation_parts.append(f"  → Coarse granularity reduces SKU complexity and handling")

        except ValueError:
            pass

    # Trade-off analysis
    if len(recommendations) >= 2 and result.get('tradeoff_explanation'):
        explanation_parts.append(f"\n**TRADE-OFF ANALYSIS:**")
        explanation_parts.append(result['tradeoff_explanation'])

        # Add interpretation of trade-offs
        second_code = recommendations[1]['rs_code']
        explanation_parts.append(f"\nThis means choosing {best_code} over {second_code} provides these measurable benefits without sacrificing other objectives under your selected weighting scheme.")

    # Client-ready summary
    if recommendations:
        best_rec = recommendations[0]
        best_data = best_rec['data']

        explanation_parts.append(f"\n**CLIENT-READY SUMMARY:**")
        explanation_parts.append(f"From {total_candidates} evaluated solutions, we recommend **{best_rec['rs_code']}** with:")
        explanation_parts.append(f"• Steel cost: ${best_data.get('steel_cost', 0):,.0f}")
        explanation_parts.append(f"• Construction duration: {best_data.get('duration_days', 0):.0f} days")
        explanation_parts.append(f"• Carbon footprint: {best_data.get('co2_tonnes', 0):.0f} tCO2")
        explanation_parts.append(f"• Labor requirement: {best_data.get('manhours', 0):.0f} manhours")

        if len(recommendations) > 1:
            explanation_parts.append(f"\nThis solution outperforms the next-best alternative while maintaining balance across your prioritized criteria.")

    return "\n".join(explanation_parts)


def explain_tradeoff(best_code: str, second_code: str,
                    catalog: Dict[str, Dict], preset: RSObjective) -> str:
    """
    Generate trade-off explanation between best and runner-up solutions
    """
    if best_code not in catalog or second_code not in catalog:
        return "Cannot compare: missing RS data"

    best_data = catalog[best_code]
    second_data = catalog[second_code]

    # Calculate deltas for key metrics
    deltas = {}
    key_metrics = ['steel_cost', 'concrete_cost', 'duration_days', 'co2_tonnes', 'manhours']

    for metric in key_metrics:
        if metric in best_data and metric in second_data:
            delta = best_data[metric] - second_data[metric]
            deltas[metric] = delta

    # Format delta descriptions
    delta_parts = []
    if 'steel_cost' in deltas:
        delta = deltas['steel_cost']
        if delta < 0:
            delta_parts.append(f"−${abs(delta):,.0f} steel")
        elif delta > 0:
            delta_parts.append(f"+${delta:,.0f} steel")

    if 'duration_days' in deltas:
        delta = deltas['duration_days']
        if delta < 0:
            delta_parts.append(f"−{abs(delta):.1f} days")
        elif delta > 0:
            delta_parts.append(f"+{delta:.1f} days")

    if 'co2_tonnes' in deltas:
        delta = deltas['co2_tonnes']
        if delta < 0:
            delta_parts.append(f"−{abs(delta):.1f} tCO2")
        elif delta > 0:
            delta_parts.append(f"+{delta:.1f} tCO2")

    if 'manhours' in deltas:
        delta = deltas['manhours']
        if delta < 0:
            delta_parts.append(f"−{abs(delta):.0f} manhours")
        elif delta > 0:
            delta_parts.append(f"+{delta:.0f} manhours")

    # Generate mnemonic implications
    try:
        best_decoded = decode_rs_code(best_code)
        second_decoded = decode_rs_code(second_code)

        implications = []

        if best_decoded['join'] != second_decoded['join']:
            if best_decoded['join'] == 'EM':
                implications.append("EM reduces congestion vs TR")
            else:
                implications.append("TR reduces cost vs EM")

        if best_decoded['L'] != second_decoded['L']:
            if best_decoded['L'] > second_decoded['L']:
                implications.append(f"L{best_decoded['L']} reduces SKU fragmentation vs L{second_decoded['L']}")
            else:
                implications.append(f"L{best_decoded['L']} increases cutting flexibility vs L{second_decoded['L']}")

        if best_decoded['grouped'] != second_decoded['grouped']:
            if best_decoded['grouped']:
                implications.append("AG_ stabilizes procurement lots")
            else:
                implications.append("Non-grouped allows order flexibility")

    except ValueError:
        implications = []

    # Combine explanation
    explanation_parts = []
    if delta_parts:
        explanation_parts.append(f"vs #{second_code}: {'; '.join(delta_parts)}")

    if implications:
        explanation_parts.append(f"Implications: {'; '.join(implications)}")

    if not explanation_parts:
        explanation_parts.append("No significant differences identified")

    return ". ".join(explanation_parts) + "."


def get_top_k_recommendations(catalog: Dict[str, Dict],
                             objective: RSObjective,
                             k: int = 5,
                             **constraints) -> Dict:
    """
    Get top-K RS recommendations with complete analysis
    """
    # Apply constraints
    filtered_catalog = apply_constraints(catalog, **constraints)

    if not filtered_catalog:
        return {
            'recommendations': [],
            'rationale': 'No solutions satisfy the given constraints',
            'tradeoff_explanation': '',
            'pareto_frontier': [],
            'pareto_size': 0,
            'total_candidates': 0,
            'objective_weights': build_objective_weights(objective)
        }

    # Get objective weights
    weights = build_objective_weights(objective)

    # Normalize metrics
    normalized_catalog = normalize_metrics(filtered_catalog, list(weights.keys()))

    # Score and rank
    ranked_solutions = score_weighted_sum(normalized_catalog, weights)

    # Get Pareto frontier
    pareto_codes = pareto_front(normalized_catalog, list(weights.keys()))

    # Get top-K
    top_k = ranked_solutions[:k]

    # Generate rationale
    rationale_parts = [f"Selected using {objective.value} objective"]
    if constraints:
        constraint_desc = []
        for key, value in constraints.items():
            if value is not None:
                constraint_desc.append(f"{key}={value}")
        if constraint_desc:
            rationale_parts.append(f"with constraints: {', '.join(constraint_desc)}")

    rationale_parts.append(f"from {len(filtered_catalog)} candidate solutions")

    # Generate trade-off explanation for top 2
    tradeoff_explanation = ""
    if len(top_k) >= 2:
        best_code = top_k[0][0]
        second_code = top_k[1][0]
        tradeoff_explanation = explain_tradeoff(best_code, second_code, normalized_catalog, objective)

    return {
        'recommendations': [
            {
                'rs_code': code,
                'score': score,
                'data': normalized_catalog[code]
            }
            for code, score in top_k
        ],
        'rationale': '. '.join(rationale_parts) + '.',
        'tradeoff_explanation': tradeoff_explanation,
        'pareto_frontier': list(pareto_codes),
        'pareto_size': len(pareto_codes),
        'total_candidates': len(filtered_catalog),
        'objective_weights': weights
    }