# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RC Agent Platform — a Construction Intelligence System for reinforced concrete projects. Combines deterministic data pipelines with LLM-powered ReAct agents (via LangGraph) to optimize floor groupings, plan steel procurement, and analyze rebar installation schedules. Domain: AEC (Architecture, Engineering, Construction).

## Commands

```bash
# Setup
python3 -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run interactive CLI (agent selection menu)
python cli.py

# Run single query against a specific agent
python cli.py --grouping "Optimize from PISO 5 to PISO 15 with k=2,3,4"
python cli.py --procurement "Review the reinforcement solution file"
python cli.py --scheduling "What is the duration for each floor?"
python cli.py --prodet "What projects are available?"
python cli.py --config "Describe the mokara config"

# Run full data pipeline (generates all JSON artifacts from Excel input)
python run_rebar_pipeline.py -x projects/mokara/reinforcement_solution.xlsx -d projects/mokara/

# Run individual pipeline steps
python reinforcement_parser.py -i projects/reinforcement_solution.xlsx -o projects/elements.json
python complexity_index.py -i projects/elements.json -o projects/elements_with_ci.json
python productivity.py -i projects/elements_with_ci.json -o projects/elements_with_prod.json
python work_packages.py -i projects/elements_with_prod.json -o projects/work_packages.json
python floor_schedule.py -i projects/work_packages.json -o projects/floor_schedule.json

# Run tests
python test_optimizer.py
```

## Architecture

### Two-Layer Design

**Layer 1 — Deterministic Data Pipeline:** A 5-step chain that transforms a ProDet Excel file into structured JSON artifacts:

```
reinforcement_solution.xlsx
  → reinforcement_parser.py   → elements.json
  → complexity_index.py       → elements_with_ci.json
  → productivity.py           → elements_with_prod.json
  → work_packages.py          → work_packages.json
  → floor_schedule.py         → floor_schedule.json
```

**Layer 2 — LLM Agents:** Five specialized ReAct agents (LangGraph `create_react_agent`) that use deterministic Python functions as tools:

| Agent | Module | Purpose | Key Tools |
|-------|--------|---------|-----------|
| Grouping Optimizer | `grouping_optimizer.py` | Minimize steel via optimal floor groupings | `inspect_data_file`, `grouping_optimizer_v1` |
| Procurement | `procurement_agent.py` | Review reinforcement files, generate bar lists & PDF reports | `load_reinforcement_file`, `list_available_floors`, `get_floor_data`, `analyze_bars_by_diameter`, `analyze_bars_by_shape`, `generate_pdf_report` |
| Scheduling | `scheduling_agent.py` | Plan rebar installation schedules | `compute_floor_schedule_tool`, `analyze_bottleneck`, `compare_scenarios` |
| ProDet Runner | `prodet_agent.py` | Run ProDet, copy output, run data pipeline | `list_projects`, `inspect_project`, `run_prodet`, `copy_output_to_rc_agent`, `run_data_pipeline` |
| Config Agent | `config_agent.py` | NL ↔ project.config translation — describe design intent & modify configs | `load_config_summary`, `update_config` |

### Unified Agent Pattern

All agents follow the same template:
1. Class with `SYSTEM_PROMPT`, `__init__` (creates `ChatAnthropic` + tools → `create_react_agent`), and `run()` method
2. Tools are `@tool`-decorated pure functions that perform deterministic computation
3. LLM (Claude Sonnet) handles reasoning; tools handle data processing
4. `cli.py` provides the entry point with chat history, agent switching, and spinner UI

### Key Dependencies

- **LangGraph/LangChain** for agent orchestration and tool binding
- **langchain-anthropic** (`ChatAnthropic`) as the LLM provider — model: `claude-sonnet-4-6`
- **Pandas + OpenPyXL** for Excel parsing
- **Pydantic v2** for all data models
- **ReportLab** for PDF report generation
- **python-dotenv** for `.env` configuration

### ProDet Excel Schema

The procurement agent parses multi-sheet Excel files with these key sheets:
- `Resumen_Refuerzo` — story-by-story steel totals
- `RefLong_PorElemento` / `RefLong_Total` — longitudinal reinforcement
- `RefTrans_PorElemento` / `RefTrans_Total` — transverse reinforcement (stirrups)

### Data Flow

JSON artifacts in `projects/` are the bridge between the pipeline and agents. Each project has its own subfolder under `projects/<project_name>/` containing both ProDet source files (project.config, project.prodes) and pipeline artifacts. The pipeline writes them; agents read them via their tools. Key structures: elements have `floor_id`, `element_id`, `element_type` (beam/column/wall/slab), reinforcement details, complexity index (`ci`), and productivity predictions (`crew_hours_pred`).

## Configuration

- `ANTHROPIC_API_KEY` in `.env` (required)
- `CLAUDE_MODEL` in `.env` (optional, defaults to `claude-sonnet-4-6`)
- `PRODET_ROOT` in `.env` — path to ProDes-Core source (Windows or WSL paths accepted, auto-converted)
- `PRODET_PROJECTS` in `.env` — optional override for project folders (defaults to `projects/`; Windows or WSL paths accepted, auto-converted)
- `PRODET_CONDA_ENV` in `.env` — conda environment name for ProDet (default: `ProDet-py39`)
- Default crew allocations in `scheduling_agent.py`: beams=2, columns=1, walls=1, slabs=2
- Scheduling formulas: `duration_days = crew_hours / (n_crews × hours_per_day)`, floor duration = max across work types
