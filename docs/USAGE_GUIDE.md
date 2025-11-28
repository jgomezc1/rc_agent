# Grouping Optimizer v1 - Usage Guide

## Overview

The Grouping Optimizer solves floor-grouping problems for geometrically identical stories, minimizing steel consumption while considering construction duration.

## Installation

```bash
# Activate your virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Environment Setup

Ensure your `.env` file contains your OpenAI API key:

```
OPENAI_API_KEY=sk-your-key-here
```

## Two Ways to Use the Optimizer

### 1. Direct Optimization (No LLM)

Use this for programmatic access - faster and doesn't require API calls:

```python
from grouping_optimizer import run_optimization, format_results_summary

results = run_optimization(
    file_path="data/summary.xlsx",
    start_level="PISO 5",
    end_level="PISO 15",
    candidate_k_values=[2, 3, 4, 5],
    days_first_in_group=10.0,      # optional, default=10
    days_repeated=7.0,              # optional, default=7
    workdays_per_month=21.725,      # optional, default=21.725
    top_n=5                         # optional, default=5
)

# Print formatted results
print(format_results_summary(results))

# Or access raw data
for scenario in results["scenarios"]:
    print(f"k={scenario['k']}: {scenario['total_steel_tonf']} tonf")
```

### 2. LLM Agent (Natural Language)

Use this for conversational interaction - the agent explains results:

```python
from grouping_optimizer import GroupingOptimizerAgent

# Initialize agent
agent = GroupingOptimizerAgent()

# Option A: Structured call
response = agent.optimize_from_file(
    file_path="data/summary.xlsx",
    start_level="PISO 5",
    end_level="PISO 15",
    candidate_k_values=[2, 3, 4]
)
print(response)

# Option B: Natural language
response = agent.run("""
Analyze floor groupings for data/summary.xlsx from PISO 5 to PISO 15.
Try 2, 3, and 4 groups. Use 8 days for first level and 5 days for repeated.
""")
print(response)
```

## CLI Usage

```bash
# Interactive mode
python cli.py

# Single query mode
python cli.py "Optimize data/summary.xlsx from PISO 5 to PISO 15 with k=2,3,4"
```

## Input Data Format

Your Excel/CSV file should have:

| Column | Required | Description |
|--------|----------|-------------|
| `level` or `Nivel` | Yes | Floor identifier (e.g., "PISO 5", "L5") |
| `steel_total_per_level` or `Total por nivel` | Yes | Steel quantity per level [tonf] |
| `concrete_per_level` | No | Concrete quantity (for reference) |
| `labor_hours` | No | Labor hours (for reference) |

The optimizer auto-detects:
- Header row location (scans first 10 rows)
- Column names (supports English and Spanish)
- Filters out unit rows, totals, and invalid data

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `candidate_k_values` | - | List of group counts to evaluate, e.g., `[2, 3, 4]` |
| `days_first_in_group` | 10.0 | Workdays for the first level in each group |
| `days_repeated` | 7.0 | Workdays for each subsequent level in a group |
| `workdays_per_month` | 21.725 | Conversion factor for duration in months |
| `top_n` | 5 | Number of top scenarios to return |

## Output Structure

```python
{
    "scenarios": [
        {
            "rank": 1,
            "k": 4,
            "total_steel_tonf": 51.53,
            "total_duration_days": 89.0,
            "total_duration_months": 4.10,
            "groups": [
                {
                    "group_id": 1,
                    "level_range": "PISO 5-PISO 7",
                    "levels": ["PISO 5", "PISO 6", "PISO 7"],
                    "envelope_steel_per_level": 4.81,
                    "group_steel_total": 14.43,
                    "group_duration_days": 24.0
                },
                ...
            ]
        },
        ...
    ],
    "total_scenarios_evaluated": 175,
    "levels_analyzed": 11,
    "level_range": "PISO 5 to PISO 15",
    "imputations_log": [],
    "parameters": {
        "days_first_in_group": 10.0,
        "days_repeated": 7.0,
        "workdays_per_month": 21.725
    }
}
```

## Notes

- **Build Order**: Groups are presented bottom-to-top (construction sequence)
- **Envelope Steel**: Each group uses the maximum steel value within that group, multiplied by the number of levels
- **Ranking**: Scenarios sorted by lowest steel first, then shortest duration for ties
- **Imputation**: Missing steel values are filled by averaging immediate neighbors (logged explicitly)
