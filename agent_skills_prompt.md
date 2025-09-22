# Vibecoding Prompt: Agent Skills Implementation for RC Construction Decision Support

Help me extend the capabilities of the agent so it operates in two phases:
1. **Phase A (Select)** → Ingest `shop_drawings.json` (scenario summaries) and select the best solution under project constraints.
2. **Phase B (Execute)** → Ingest `shop_drawings_structuBIM.json` (element-level detail for the chosen solution) and provide actionable operational insights.

---

## 🎯 Mission
Implement a Python package that provides robust **decision-support skills** for reinforced concrete construction.  
The agent must be able to:
- Select the best reinforcement solution among alternatives (`shop_drawings.json`).
- Once selected, analyze the chosen solution in detail (`shop_drawings_structuBIM.json`).
- Expose well-defined functions (skills) for optimization, constructibility analysis, procurement, scheduling, and reporting.

---

## 🧩 Agent Skills Mapping

### 0) Core Services (shared)
- **Data Router** → detect input type and route to Phase A or B.
- **Constraints & Objectives Manager** → normalize constraints (budget, CO₂ caps, labor) into an OptimizationSpec.
- **Validation & Integrity Check** → enforce data consistency, unit correctness, element-sum checks.

### Phase A — Select (with `shop_drawings.json`)
- **Scenario Screening** → filter infeasible scenarios by constraints.
- **Multi-Objective Scoring** → rank feasible scenarios (lexicographic or weighted).
- **Pareto Frontier** → extract non-dominated sets across cost, time, CO₂.
- **Sensitivity & What-If** → test shocks in steel price, labor, availability.
- **Procurement Readiness Score** → penalize many bar geometries or unavailable diameters/connectors.
- **Phase-Gate Recommendation** → produce selection memo (best choice + rationale + risks + alternates).

### Phase B — Execute (with `shop_drawings_structuBIM.json`)
- **Element Risk Radar** → flag high-complexity/high-labor elements (bottlenecks).
- **Crew & Sequence Planner** → suggest crew allocation and sequencing.
- **Procurement & Call-Offs** → translate bar/stirrup quantities into rolling purchase lots.
- **QA/QC Checks** → flag anomalies (reinforcement ratios, stirrup spacing, connector misplacements).
- **Constructibility Insights** → simplification tips (bar families, bend reuse, staging).
- **Short-Interval Control (SIC)** → reforecast plan based on progress and adjust procurement/crew.
- **Environmental & Reporting** → CO₂, cost, rework variance reports.

### Cross-Cutting Skills
- **Health Check & Data Integrity** → machine-readable validation report.
- **Latency & Scale Controls** → toggles for exact vs. pre-aggregated answers, lazy loading.
- **Explainability Layer** → every recommendation must return rationale + metrics + constraints.

---

## 📦 Interfaces (API Contracts)
- `select_solution(spec: OptimizationSpec) -> SelectionResult`
- `generate_execution_plan(data: BIMData, window_days=14) -> ExecPlan`
- `what_if(shocks: Dict[str,float]) -> ReRankResult`
- `validate_data(dataset) -> ValidationReport`

**Key Data Contracts**
- **ScenarioSummary** (from shop_drawings.json): steel_cost, concrete_cost, manhours, duration_days, co2_tonnes, constructibility_index, bar_geometries.
- **ElementMetrics** (from shop_drawings_structuBIM.json): bars_by_diameter, stirrups_by_diameter, connectors, heads, complexity_score, labor_hours_modifier, total_rebar_weight, vol_concreto.

---

## 🚀 Implementation Strategy
1. **Task 1 — Core**: router, validation, selection pipeline (A1–A3), explainability.
2. **Task 2 — Robustness**: sensitivity, procurement scoring, phase-gate memo.
3. **Task 3 — Execution**: risk radar, crew planner, QA/QC.
4. **Task 4 — Operations**: procurement calls, constructibility tips, SIC loop, reporting.

---

## 🔑 Deliverables
- A modular Python package with dataclasses, JSON loaders, validators.
- Reusable API functions (skills) with clear docstrings and typed outputs (not just strings).
- Reporting outputs in **both machine (JSON)** and **human-readable (Markdown/HTML)** formats.

---