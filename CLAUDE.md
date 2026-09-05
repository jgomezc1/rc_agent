# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RC Agent Platform — a Construction Intelligence System for reinforced concrete projects. Combines deterministic data pipelines with LLM-powered ReAct agents (via LangGraph) to optimize floor groupings, plan steel procurement, and analyze rebar installation schedules. Domain: AEC (Architecture, Engineering, Construction).

## Commands

```bash
# Setup — Windows, web app (creates both venvs under %LOCALAPPDATA%, installs deps)
setup.bat

# Setup — CLI only / non-Windows
python3 -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run the web app (FastAPI on :8000 and Vite on :5273, in two windows)
start.bat

# Or run the two halves manually
%LOCALAPPDATA%\rc_agent\venvs\backend\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000
cd frontend && npm run dev

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
| Grouping Optimizer | `grouping_optimizer.py` | Estimate floor groupings, user selects, create config, run ProDet, compare results | `load_baseline_steel`, `estimate_groupings`, `apply_grouping`, `compare_grouping_results` |
| Procurement | `procurement_agent.py` | Review reinforcement files, generate bar lists & PDF reports | `load_reinforcement_file`, `list_available_floors`, `get_floor_data`, `analyze_bars_by_diameter`, `analyze_bars_by_shape`, `generate_pdf_report` |
| Scheduling | `scheduling_agent.py` | Plan rebar installation schedules | `compute_floor_schedule_tool`, `load_floor_schedule_tool` |
| ProDet Runner | `prodet_agent.py` | Run ProDet, copy output, run data pipeline, generate planos & memorias | `list_projects`, `inspect_project`, `run_prodet`, `generate_planos_memorias`, `copy_output_to_rc_agent`, `run_data_pipeline` |
| Config Agent | `config_agent.py` | NL ↔ project.config translation — describe design intent, modify configs & set up floor groupings | `load_config_summary`, `update_config`, `set_floor_groups` |

### Unified Agent Pattern

All agents follow the same template:
1. Class with `SYSTEM_PROMPT`, `__init__` (creates `ChatAnthropic` + tools → `create_react_agent`), and `run()` method
2. Tools are `@tool`-decorated pure functions that perform deterministic computation
3. LLM (Claude Sonnet) handles reasoning; tools handle data processing
4. `cli.py` provides the entry point with chat history, agent switching, and spinner UI

### Web Application

A FastAPI backend (`api/main.py`) wraps the same agents the CLI uses; a React +
Vite frontend (`frontend/`) provides the chat UI.

- **Backend** — `uvicorn api.main:app` on port 8000. `/api/chat/stream` accepts
  `query`, `project`, `chat_history`, and `forced_agent`. `/api/health` reports
  ProDet runtime readiness via `check_prodet_runtime()` in `prodet_agent.py`,
  which also runs at import time so a missing venv surfaces at startup instead
  of halfway through a tool call.
- **Routing** — `ProDetAgentTeam.run` classifies with an LLM router by default;
  passing a valid `forced_agent` skips the router entirely. The sidebar's agent
  selector sets it, with "Auto-route" (`null`) as the default.
- **Frontend** — Vite dev server on port 5273 (`strictPort: true`, because 5173
  is taken by another app on this machine), proxying `/api` to the backend. The
  sidebar footer shows a build badge with the branch and short commit currently
  being served, plus an amber asterisk when the working tree is dirty. In dev it
  re-reads `GET /__git-info` on window focus, so a `git checkout` is reflected
  without restarting anything — see `frontend/vite-plugin-git-info.js`.
- **Dropbox caveat** — this repo lives in Dropbox, which locks files while
  syncing and breaks atomic renames. Both Python venvs and Vite's dep-optimizer
  cache therefore live under `%LOCALAPPDATA%\rc_agent\`, never inside the repo.
  Symptoms of getting this wrong: pip installs failing partway through, and a
  blank frontend with 504 "Outdated Optimize Dep" on every dependency.

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

### Solution Composition

Vigas and nervios are independently parameterized in ProDet, so users run
separate parametric studies for each element type and then combine the best
variant per type into a "building solution."

**Tool:** `compose_solution` in `prodet_agent.py`

**Solution folders:** Named `{source}_sol_{name}` (e.g., `mokara_sol_balanced`).
Contain xlsx files from selected variants, pipeline artifacts, and `solution.json`
recording provenance. Solution folders are indistinguishable from normal project
folders for downstream agents — procurement and scheduling tools work on them
without modification.

**`solution.json` fields:** `source_project`, `solution_name`,
`element_type_sources` (dict mapping element type → variant project name),
`created_at`, `pipeline_ran`, `artifacts`, `xlsx_files`, `cantidades_files`,
`structubim_files`.

### Grouping Optimizer — End-to-End Workflow

The Grouping Optimizer agent loads an existing ProDet solution, estimates the
impact of various floor groupings, asks the user to select one, then creates
a new config variant with floor groups, runs ProDet, and reports actual results
compared to the ungrouped baseline.

**Flow:**
1. `load_baseline_steel` — loads floor-level steel from existing reinforcement xlsx
2. Agent asks user to confirm which floors are geometrically identical
3. `estimate_groupings` — runs combinatorial optimizer, reports estimated deltas
4. User selects a specific grouping
5. `apply_grouping` — creates config variant with grupos_niveles, runs ProDet,
   runs pipeline, compares actual results
6. Agent reports actual steel delta, bar type reduction, and next steps

**Estimation model:** envelope_steel = max(steel_per_level) in group × group_size.
Approximation of ProDet's "envolvente" mode. Actual results typically differ by
1-3% from estimates.

**Key reuse:** `set_floor_groups` (config_agent) for validated config creation,
`_run_prodet_single` (prodet_agent) for ProDet execution,
`compare_reinforcement` (procurement_agent) for actual comparison.

### ProDet Excel Schema

The procurement agent parses multi-sheet Excel files with these key sheets:
- `Resumen_Refuerzo` — story-by-story steel totals
- `RefLong_PorElemento` / `RefLong_Total` — longitudinal reinforcement
- `RefTrans_PorElemento` / `RefTrans_Total` — transverse reinforcement (stirrups)

### Project Families

Projects often produce multiple variant folders sharing a base name (e.g. `mokara`, `mokara_v1`, `mokara_lh50cm`, `mokara_sol_balanced`). The platform groups these into **project families** using `paths.py`:

- `base_project_name(folder)` — extracts the base name by progressively stripping `_suffix` segments and checking for an existing source project folder with `project.config`. Falls back to regex for `_v\d+` and `_sol_*` patterns.
- `list_project_families()` — groups all project folders by base name.
- `resolve_project_family(name)` — returns all folders in the same family.

All five agents have a `list_project_family` tool (defined in `prodet_agent.py`, imported by others). When a user references a project by base name (e.g. "mokara"), agents discover all variants and either operate on all of them or ask the user which ones to include.

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
- `PRODET_PYTHON` in `.env` — optional absolute path to ProDet's venv python. Auto-discovered when unset: `%LOCALAPPDATA%\rc_agent\venvs\prodet\Scripts\python.exe` (created by `setup.bat`), then a `.venv`/`venv`/`env` beside `PRODET_ROOT`. ProDet is no longer launched through conda.
- Default crew allocations in `scheduling_agent.py`: beams=2, columns=1, walls=1, slabs=2
- Scheduling formulas: `duration_days = crew_hours / (n_crews × hours_per_day)`, floor duration = max across work types
