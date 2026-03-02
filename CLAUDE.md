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

# Run a workflow
python cli.py --workflow config-impact mokara "simplify for faster construction"

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
| Config Agent | `config_agent.py` | NL ↔ project.config translation — describe design intent, modify configs & set up floor groupings | `load_config_summary`, `update_config`, `set_floor_groups` |

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

### Config Agent — Reasoning Framework & Floor Grouping

The Config Agent uses a structured reasoning framework to translate between natural language and ProDet `project.config` files. Key concepts:

**Eight Construction Outcome Dimensions:** Material Cost (D1), Piece Count (D2), Field Error Risk (D3), Installation Speed (D4), Required Skill Level (D5), Drawing Clarity (D6), Inspection Complexity (D7), Adaptability (D8). The fundamental trade-off: Material Cost and Piece Count are negatively correlated — optimizing for less steel produces more bar types.

**Six Parameter Clusters:** A (Bar Complexity Envelope), B (Splice & Development Strategy), C (Stirrup Configuration), D (Geometric Tolerances & Merging), E (Per-Level Overrides), F (Drawing & Presentation). Each has a Simple→Optimized spectrum. Critical interaction: A×E is multiplicative — never push both toward Optimized simultaneously.

**Six Archetype Profiles:** Simple/Robust, Balanced, Cost-Optimized, High-Rise Repetitive, Speed-Focused, Prefab-Ready. The agent selects the closest archetype from user intent and adjusts specific clusters.

**Floor Grouping (`grupos_niveles`):** Groups geometrically identical floors so ProDet computes reinforcement from the envelope of forces — every floor in the group gets the same rebar layout. Trade-off: ~3-8% more steel vs. significant construction speed gains from crew repetition. The `set_floor_groups` tool enforces a 5-layer validation (floor existence, identical range gate, consecutive check, min group size ≥2, no duplicates) and requires the user to declare which floors are geometrically identical before grouping. Synergistic with Cluster E (disabled overrides) and Archetype 4 (High-Rise Repetitive). Not applicable to transfer floors, mezzanines, roof, or podium levels.

**Reference documentation** in `docs/`:
- `config_agent_system_prompt.py` — full system prompt reference copy
- `parameter_semantic_catalog_guide.md` — parameter clusters, Simple/Balanced/Optimized values, floor grouping trade-off table
- `impact_matrix_guide.md` — causal impact of each cluster on the 8 dimensions, plus floor grouping row
- `archetype_profiles_guide.md` — complete archetype parameter snapshots

### Workflows

Multi-step automated pipelines implemented as LangGraph `StateGraph` with explicit nodes. Unlike agents (which are free-form ReAct loops), workflows follow a fixed node sequence with optional LLM nodes and user interrupts.

**Workflow 1: Config Impact Analysis** (`workflows/config_impact.py`)

Automates the loop: load baseline config → LLM proposes changes → user confirms → create variant → run ProDet → compare reinforcement → LLM narrates trade-off.

```
load_baseline → propose_changes (LLM) → [interrupt: user confirms]
                                              │
                                        create_variant → run_prodet_all → compare_all → narrate_tradeoff (LLM)
```

Run: `python cli.py --workflow config-impact <project> "<intent>"`
Example: `python cli.py --workflow config-impact mokara "simplify for faster construction"`

Produces a trade-off narrative with specific numbers, e.g.: "Switching from Balanced to Simple costs 847 kg more steel (+11.3%) but eliminates 142 unique bar entries (-58%)."

Key tool: `compare_reinforcement` in `procurement_agent.py` — diffs `Resumen_Refuerzo`, `RefLong_Total`, and `RefTrans_Total` between two project folders.

Reuses internal helpers from `prodet_agent.py` (`_create_variant_config`, `_run_prodet_single`) and `config_agent.py` (`load_config_summary`).

### ProDet Excel Schema

The procurement agent parses multi-sheet Excel files with these key sheets:
- `Resumen_Refuerzo` — story-by-story steel totals
- `RefLong_PorElemento` / `RefLong_Total` — longitudinal reinforcement
- `RefTrans_PorElemento` / `RefTrans_Total` — transverse reinforcement (stirrups)

### Data Flow

Every project has its own subfolder under `projects/<project_name>/` (e.g. `projects/mokara/`, `projects/supernovaA/`). There is no single "default" project — mokara and supernovaA are simply example projects included in the repo. Each project folder contains:

- **ProDet source files** (seed data, never overwritten):
  - `project.config` — design configuration (the Config Agent reads/writes this)
  - `project.cargas` — load definitions
  - `project.geom` — geometry model
  - `project.prodes` — structural design results
- **Pipeline artifacts** (generated by `run_rebar_pipeline.py`):
  - `elements.json`, `elements_with_ci.json`, `elements_with_prod.json`, `work_packages.json`, `floor_schedule.json`
- **ProDet output** (generated by ProDet via the ProDet Runner agent):
  - `reinforcement_solution_V.xlsx`, `reinforcement_solution_N.xlsx`, etc.

JSON artifacts are the bridge between the pipeline and agents. The pipeline writes them; agents read them via their tools. Key structures: elements have `floor_id`, `element_id`, `element_type` (beam/column/wall/slab), reinforcement details, complexity index (`ci`), and productivity predictions (`crew_hours_pred`).

**project.config structure:** A JSON file with top-level keys including `nombre_inf`, `modo`, `postensado`, `vigas`, `nervios`, `columnas` (element-type sections each containing `materiales`, `norma`, `param_despiece`, `estribos`), and `grupos_niveles` (floor grouping array). Floor names are extracted from `vigas.param_despiece.forzar_ref_ppal.por_nivel`. Seed configs must never be overwritten — when modifying a config, always save to a new project subfolder (e.g. `projects/mokara_v2/`), and companion files (`project.cargas`, `project.geom`, `project.prodes`) are auto-copied from the source.

## Configuration

- `ANTHROPIC_API_KEY` in `.env` (required)
- `CLAUDE_MODEL` in `.env` (optional, defaults to `claude-sonnet-4-6`)
- `PRODET_ROOT` in `.env` — path to ProDes-Core source (Windows or WSL paths accepted, auto-converted)
- `PRODET_PROJECTS` in `.env` — optional override for project folders (defaults to `projects/`; Windows or WSL paths accepted, auto-converted)
- `PRODET_CONDA_ENV` in `.env` — conda environment name for ProDet (default: `ProDet-py39`)
- Default crew allocations in `scheduling_agent.py`: beams=2, columns=1, walls=1, slabs=2
- Scheduling formulas: `duration_days = crew_hours / (n_crews × hours_per_day)`, floor duration = max across work types
