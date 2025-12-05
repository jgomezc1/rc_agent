# ProDet Agent System - Usage Guide

## Overview

The ProDet Agent System is a construction intelligence platform for reinforced concrete projects. It provides three specialized AI agents:

1. **Floor Grouping Optimizer** - Optimize floor groupings to minimize steel consumption
2. **Procurement Agent** - Review reinforcement files and plan material procurement
3. **Scheduling Agent** - Plan rebar installation schedules and analyze floor durations

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

Create a `.env` file in the project root with your OpenAI API key:

```
OPENAI_API_KEY=sk-your-key-here
```

---

## Data Pipeline

Before using the Scheduling Agent, you need to process your ProDet reinforcement Excel file through the data pipeline. This generates the required JSON artifacts.

### Pipeline Overview

```
reinforcement_solution.xlsx
         │
         ▼
    elements.json              (reinforcement_parser.py)
         │
         ▼
    elements_with_ci.json      (complexity_index.py)
         │
         ▼
    elements_with_prod.json    (productivity.py)
         │
         ▼
    work_packages.json         (work_packages.py)
         │
         ▼
    floor_schedule.json        (floor_schedule.py)
```

### Option 1: Run Full Pipeline (Recommended)

Use the pipeline script to process everything in one command:

```bash
python run_rebar_pipeline.py --xlsx data/reinforcement_solution.xlsx
```

Or with short flags:

```bash
python run_rebar_pipeline.py -x data/reinforcement_solution.xlsx
```

Optional parameters:

```bash
# Specify output directory
python run_rebar_pipeline.py -x data/reinforcement_solution.xlsx --data-dir output

# Override hours per day for scheduling
python run_rebar_pipeline.py -x data/reinforcement_solution.xlsx --hours-per-day 10
```

### Option 2: Run Steps Individually

If you need more control, run each step separately:

```bash
# Step 1: Parse Excel to elements.json
python reinforcement_parser.py -i data/reinforcement_solution.xlsx -o data/elements.json

# Step 2: Add Complexity Index
python complexity_index.py -i data/elements.json -o data/elements_with_ci.json

# Step 3: Add Productivity predictions
python productivity.py -i data/elements_with_ci.json -o data/elements_with_prod.json

# Step 4: Aggregate into work packages
python work_packages.py -i data/elements_with_prod.json -o data/work_packages.json

# Step 5: Compute floor schedule
python floor_schedule.py -i data/work_packages.json -o data/floor_schedule.json
```

### Input File Format

The input Excel file (`reinforcement_solution.xlsx`) must be a ProDet export with these sheets:

| Sheet Name | Purpose |
|------------|---------|
| `Resumen_Refuerzo` | Summary with project name and per-floor totals |
| `RefLong_PorElemento` | Longitudinal reinforcement per element |
| `RefLong_Total` | Longitudinal reinforcement totals (optional) |
| `RefTrans_PorElemento` | Transverse reinforcement (stirrups) per element |
| `RefTrans_Total` | Transverse reinforcement totals (optional) |

---

## CLI Usage

### Interactive Mode

Launch the interactive CLI with agent selection:

```bash
python cli.py
```

This displays a menu to select from the available agents.

### Single Query Mode

Execute a single query without entering interactive mode:

```bash
# Grouping Optimizer
python cli.py --grouping "Optimize data/summary.xlsx from PISO 5 to PISO 15 with k=2,3,4"

# Procurement Agent
python cli.py --procurement "Generate a PDF report for floors PISO 5 through PISO 11"

# Scheduling Agent
python cli.py --scheduling "What is the duration for each floor?"
```

---

## Agent 1: Floor Grouping Optimizer

Optimizes floor groupings for geometrically identical stories, minimizing steel consumption while considering construction duration.

### Example Queries

```
Optimize data/summary.xlsx from PISO 5 to PISO 15 with k=2,3,4
What levels are available in data/summary.xlsx?
Find the optimal grouping using 2, 3, 4, and 5 groups
```

### Direct Python Usage

```python
from grouping_optimizer import run_optimization, format_results_summary

results = run_optimization(
    file_path="data/summary.xlsx",
    start_level="PISO 5",
    end_level="PISO 15",
    candidate_k_values=[2, 3, 4, 5],
    days_first_in_group=10.0,
    days_repeated=7.0,
)

print(format_results_summary(results))
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `candidate_k_values` | - | List of group counts to evaluate |
| `days_first_in_group` | 10.0 | Workdays for first level in each group |
| `days_repeated` | 7.0 | Workdays for subsequent levels |
| `workdays_per_month` | 21.725 | Conversion factor for months |
| `top_n` | 5 | Number of top scenarios to return |

---

## Agent 2: Procurement Agent

Reviews ProDet reinforcement files and generates procurement reports with detailed bar lists.

### Example Queries

```
Review the reinforcement solution file
What floors are available?
Give me a procurement report for PISO 5
Generate a PDF report for floors PISO 5 through PISO 11
Show me all bar lengths for PISO 5 to PISO 8
```

### Features

- Multi-sheet Excel file parsing
- Floor-specific or floor-range reports
- Aggregation by diameter, shape, and length
- Detailed bar cutting lists
- PDF report generation

### Direct Python Usage

```python
from procurement_agent import ProcurementAgent

agent = ProcurementAgent()
response = agent.run("Generate a PDF report for PISO 5 to PISO 11")
print(response)
```

---

## Agent 3: Scheduling Agent

Plans rebar installation schedules and analyzes floor durations based on crew allocations.

### Prerequisites

Before using the Scheduling Agent, run the data pipeline to generate the required JSON files:

```bash
python run_rebar_pipeline.py -x data/reinforcement_solution.xlsx
```

### Example Queries

```
What is the duration for each floor?
Which floor is the bottleneck?
What if I use 3 crews for beams instead of 2?
How long would it take with 10-hour workdays?
Compare current schedule with double the beam crews
```

### Key Concepts

| Term | Description |
|------|-------------|
| `crew_hours_total` | Total predicted crew-hours for a work package |
| `n_crews_assigned` | Number of crews allocated to a work type |
| `duration_days` | `crew_hours_total / (n_crews × hours_per_day)` |
| `floor_duration_days` | Maximum duration among packages on a floor |

### Default Crew Allocation

| Work Type | Default Crews |
|-----------|---------------|
| rebar_beams | 2 |
| rebar_columns | 1 |
| rebar_walls | 1 |
| rebar_slabs | 2 |
| rebar_unknown | 1 |

### Direct Python Usage

```python
from scheduling_agent import SchedulingAgent

agent = SchedulingAgent()
response = agent.run("What if I use 4 crews for beams?")
print(response)
```

### Using Tools Directly (No LLM)

```python
from floor_schedule import build_floor_schedule, DEFAULT_CREWS_PER_WORK_TYPE
import json

# Load work packages
with open("data/work_packages.json") as f:
    data = json.load(f)

# Compute schedule with custom crews
crews = DEFAULT_CREWS_PER_WORK_TYPE.copy()
crews["rebar_beams"] = 4  # Double beam crews

schedule = build_floor_schedule(data, crews, hours_per_day=8.0)

# Print floor durations
for floor in schedule["floors"]:
    print(f"{floor['floor_id']}: {floor['floor_duration_days']:.2f} days")
```

---

## Generated JSON Artifacts

### elements.json

Canonical representation of all reinforcement elements:

```json
{
  "project_id": "Ejemplo Mokara",
  "elements": [
    {
      "floor_id": "PISO 2",
      "element_id": "V-3",
      "element_type": "beam",
      "reinforcement": {
        "w_long_kgf": 528.1,
        "w_trans_kgf": 177.2,
        "w_total_kgf": 705.3,
        "longitudinal_rows": [...],
        "transverse_rows": [...]
      }
    }
  ]
}
```

### elements_with_ci.json

Adds Complexity Index (CI) to each element:

```json
{
  "ci": 1.42,
  "ci_features": {
    "w_total_ton": 0.7053,
    "n_shapes_long": 2,
    "n_diams_long": 2,
    "bar_count_long": 61,
    "n_shapes_trans": 2,
    "n_diams_trans": 1,
    "bar_count_trans": 218
  }
}
```

### elements_with_prod.json

Adds productivity predictions:

```json
{
  "prod_pred_ton_per_crew_hour": 0.083,
  "crew_hours_pred": 8.5
}
```

### work_packages.json

Aggregated work packages per floor/zone/work_type:

```json
{
  "project_id": "Ejemplo Mokara",
  "work_packages": [
    {
      "floor_id": "PISO 2",
      "zone_id": null,
      "work_type": "rebar_beams",
      "element_ids": ["V-1", "V-2", "V-3"],
      "n_elements": 3,
      "w_total_ton": 2.123,
      "crew_hours_total": 22.0
    }
  ]
}
```

### floor_schedule.json

Floor-by-floor schedule with durations:

```json
{
  "project_id": "Ejemplo Mokara",
  "hours_per_day": 8.0,
  "crews_per_work_type": {
    "rebar_beams": 2,
    "rebar_columns": 1
  },
  "floors": [
    {
      "floor_id": "PISO 2",
      "packages": [...],
      "floor_duration_days": 3.15
    }
  ]
}
```

---

## Notes

- **Build Order**: Floor groups are presented bottom-to-top (construction sequence)
- **Envelope Steel**: Each group uses the maximum steel value within that group
- **Bottleneck**: The floor with maximum duration controls the overall cycle
- **Parallel Work**: Different work types on the same floor are assumed to run in parallel
