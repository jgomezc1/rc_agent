# RC Agent Platform - Customer Demo Script

## Project Overview

**Project:** Ejemplo Mokara
**Building:** 23-story residential tower + rooftop mechanical room
**Data:** ProDet reinforcement solution file

| Metric | Value |
|--------|-------|
| Total Elements | 212 beams |
| Total Floors | 24 levels |
| Total Steel | 109.3 tons (as-designed) |
| Estimated Duration | 148.5 days (baseline) |

---

## Interactive Mode (Recommended for Demos)

The CLI supports two modes: **single-query mode** (one command, one response) and **interactive mode** (continuous conversation with an agent). For demos, **interactive mode is recommended** as it allows natural follow-up questions and feels more conversational.

### Starting Interactive Mode

```bash
python3 cli.py
```

This displays the agent selection menu:

```
Available Agents:

  [1] Floor Grouping Optimizer
      Optimize floor groupings to minimize steel consumption

  [2] Procurement Agent
      Review reinforcement files and plan material procurement

  [3] Scheduling Agent
      Plan rebar installation schedules and analyze floor durations

  [q] Quit
```

### Interactive Mode Commands

| Command | Action |
|---------|--------|
| `1`, `2`, or `3` | Select an agent |
| `back` | Return to agent selection menu |
| `exit` or `q` | Quit the application |

### Example Interactive Session

```
Select agent [1-3]: 1

━━━ Floor Grouping Optimizer ━━━

Type 'back' to return to agent selection, 'exit' to quit.

You: What levels are available in summary.xlsx?
Agent: [Response about available levels...]

You: Compare optimal groupings for 2, 3, and 4 groups
Agent: [Detailed comparison...]

You: What if I need to finish in under 140 days?
Agent: [Deadline-constrained analysis...]

You: back
[Returns to agent menu]

Select agent [1-3]: 3
━━━ Scheduling Agent ━━━

You: Which floor is the bottleneck?
Agent: [Critical path analysis...]
```

### Benefits for Demos

1. **Conversational flow** - Ask follow-up questions naturally
2. **Context preserved** - Agent remembers previous questions in the session
3. **Professional appearance** - Clean interface with spinner animations
4. **Flexible exploration** - Switch between agents as needed

### Single-Query Mode (Alternative)

For scripted demos or quick one-off queries, use command-line arguments:

```bash
python3 cli.py --grouping "your query here"
python3 cli.py --procurement "your query here"
python3 cli.py --scheduling "your query here"
```

---

## Construction Workflow Context

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: STRUCTURAL DESIGN (ProDet)                             │
│  Engineer generates rebar shop drawings with exact quantities   │
│  per floor - no grouping, each floor optimized individually     │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: FLOOR GROUPING OPTIMIZATION (Grouping Agent)           │
│  Decide how to group floors for formwork reuse                  │
│  Trade-off: steel envelope waste vs. construction speed         │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: PROCUREMENT PLANNING (Procurement Agent)               │
│  Based on selected grouping, plan steel procurement             │
│  Generate cutting lists, validate data, phase deliveries        │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: SCHEDULE OPTIMIZATION (Scheduling Agent)               │
│  Optimize crew allocation and work sequencing                   │
│  What-if analysis for resource decisions                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Data Pipeline (2 min)

### Context
The structural engineer has delivered the ProDet file with exact reinforcement quantities per floor. This is the baseline "as-designed" solution before any construction optimization.

### What It Does
Transforms the raw ProDet Excel export into structured, analyzable data with automatic complexity scoring, productivity predictions, and schedule generation.

### Command
```bash
python3 run_rebar_pipeline.py --xlsx data/reinforcement_solution.xlsx
```

### Talking Points
- "This is the starting point - exact reinforcement per floor from structural design"
- "Each floor is optimized individually by the engineer - no grouping yet"
- "The pipeline analyzes complexity and predicts installation effort for each element"
- "This gives us the baseline: 109.3 tons of steel, 148.5 days duration"

---

## Phase 2: Floor Grouping Optimization

### Context
Before procurement, we must decide how to group floors. Grouping floors means using the same formwork and rebar configuration across multiple levels. The trade-off:
- **More groups** = Less steel waste, but more formwork changes
- **Fewer groups** = More steel waste (envelope), but faster construction

### 2.1 Multi-Scenario Comparison

**Purpose:** Compare grouping strategies to find the optimal balance

```bash
python3 cli.py --grouping "Load summary.xlsx and compare optimal groupings for 2, 3, and 4 groups. Show me the trade-off between steel consumption and construction duration for each scenario. Which option gives the best balance?"
```

**Talking Points:**
- "We're evaluating hundreds of possible floor combinations"
- "Each group uses an envelope - the maximum steel from any floor in that group"
- "More groups means less waste but more formwork changes"
- "The agent finds the optimal partition for each group count"

---

### 2.2 Deadline-Constrained Optimization

**Purpose:** Find the minimum groups needed to meet a schedule target

```bash
python cli.py --grouping "Using summary.xlsx, optimize floor groupings but I need to complete the project in under 150 days. What's the minimum number of groups required? Show the grouping that minimizes steel while meeting this deadline."
```

**Talking Points:**
- "Real projects have deadline constraints"
- "The agent works backwards from your target"
- "Finds the solution that minimizes steel waste within schedule limits"

---

### 2.3 Typical Floors Analysis

**Purpose:** Focus optimization on the repetitive tower floors

```bash
python3 cli.py --grouping "Analyze only the tower floors (PISO 5 to PISO 20) for 3 groups. These are my typical floors. What's the optimal grouping and how much steel variation exists between the envelope and actual quantities per group?"
```

**Talking Points:**
- "Typical floors are where grouping has the biggest impact"
- "We can quantify exactly how much steel we're adding for constructability"
- "This informs the value engineering discussion with the owner"

---

### Decision Point

> **At this point, the team selects a grouping scenario.** For this demo, let's assume we selected **3 groups** with the following configuration:
> - Group 1: PISO 2 to PISO 4 (high steel floors)
> - Group 2: PISO 5 to CUBIERTA (typical floors)
> - Group 3: CUB. MAQUINAS (mechanical)

---

## Phase 3: Procurement Planning

### Context
With the grouping decision made, we now know the actual steel quantities to procure. Each group uses the envelope quantity, so procurement is based on grouped quantities, not as-designed quantities.

### 3.1 Complete Quality Review

**Purpose:** Validate the ProDet file before generating purchase orders

```bash
python3 cli.py --procurement "Perform a complete quality review of reinforcement_solution.xlsx. Check for data anomalies, missing values, and provide a procurement readiness assessment. List the top 5 concerns I should address before ordering steel."
```

**Talking Points:**
- "Before we order steel, we validate the source data"
- "The agent understands ProDet file structure and checks all 5 sheets"
- "Catches errors that would cause problems in fabrication"

---

### 3.2 Bar Cutting List Analysis

**Purpose:** Generate procurement-ready bar lists with optimization recommendations

```bash
python cli.py --procurement "Analyze the RefLong_Total sheet and give me a bar cutting list summary grouped by diameter. Which bar sizes have the highest quantities? Recommend standard commercial lengths to minimize waste."
```

**Talking Points:**
- "Direct input for steel purchasing and fabrication"
- "Optimization recommendations based on commercial bar lengths"
- "Reduces cutting waste and speeds up fabrication"

---

### 3.3 Phased Procurement by Group

**Purpose:** Plan steel deliveries aligned with the selected floor grouping

```bash
python3 cli.py --procurement "Based on our grouping decision, I need to procure steel for the first group (PISO 2 through PISO 4) first. Extract the total steel quantities for these floors broken down by longitudinal and transverse reinforcement. What's the delivery timeline recommendation?"
```

**Talking Points:**
- "Procurement aligns with construction sequence"
- "First group steel arrives first, reduces site storage"
- "Just-in-time delivery planning"

---

### 3.4 Group Envelope Quantities

**Purpose:** Calculate actual procurement quantities including envelope waste

```bash
python3 cli.py --procurement "For floors PISO 5 through PISO 15, calculate the envelope steel quantity assuming all floors use the maximum reinforcement from any floor in this range. Compare this to the as-designed total. What's the percentage increase?"
```

**Talking Points:**
- "This is the real cost of grouping - quantified"
- "Envelope quantities are what we actually procure"
- "Enables informed trade-off discussions"

---

## Phase 4: Schedule Optimization

### Context
With grouping decided and procurement planned, we optimize the installation schedule. The scheduling agent uses complexity-based productivity predictions to estimate crew-hours per floor.

### 4.1 Critical Path Analysis

**Purpose:** Identify bottleneck floors and schedule drivers

```bash
python3 cli.py --scheduling "Load the floor schedule and give me a complete critical path analysis. Which floors are bottlenecks? Rank all floors by duration and identify which work packages are driving the schedule on the slowest floors."
```

**Talking Points:**
- "Complexity Index drives realistic duration estimates"
- "PISO 3 and PISO 4 are the bottlenecks - highest complexity"
- "Focus optimization efforts where they matter most"

---

### 4.2 Resource vs. Hours Trade-off

**Purpose:** Compare resource allocation alternatives

```bash
python3 cli.py --scheduling "I have budget for either 1 additional beam crew OR extending workdays to 10 hours. Compare both scenarios: which option reduces total project duration more? Show me the impact on the top 5 slowest floors."
```

**Talking Points:**
- "Real construction decisions require trade-off analysis"
- "Quantified comparison, not gut feeling"
- "Shows impact on actual bottleneck floors"

---

### 4.3 Target-Based Schedule Compression

**Purpose:** Determine resources needed to hit an aggressive target

```bash
python3 cli.py --scheduling "My client wants to finish rebar installation in 100 days instead of 148. Calculate the crew configuration needed to achieve this. How many beam crews would I need? What would be the new bottleneck floor?"
```

**Talking Points:**
- "Start with the goal, work backwards to requirements"
- "Identifies what it takes to meet aggressive schedules"
- "Shows where diminishing returns begin"

---

### 4.4 Executive Summary Scenarios

**Purpose:** Generate presentation-ready scenario comparison

```bash
python3 cli.py --scheduling "Generate three scenarios: (1) baseline with 2 beam crews and 8-hour days, (2) moderate acceleration with 3 beam crews, (3) maximum acceleration with 4 beam crews and 10-hour days. For each, show total duration and the percentage reduction from baseline."
```

**Talking Points:**
- "Executive-ready output for decision meetings"
- "Clear cost-benefit for each acceleration level"
- "Supports budget vs. schedule negotiations"

---

## Quick Reference - All Commands

### Pipeline
```bash
python3 run_rebar_pipeline.py --xlsx data/reinforcement_solution.xlsx
```

### Grouping Optimizer (Run First - Decide Grouping)
```bash
# Multi-Scenario Comparison
python3 cli.py --grouping "Load summary.xlsx and compare optimal groupings for 2, 3, and 4 groups. Show me the trade-off between steel consumption and construction duration for each scenario. Which option gives the best balance?"

# Deadline-Constrained
python3 cli.py --grouping "Using summary.xlsx, optimize floor groupings but I need to complete the project in under 150 days. What's the minimum number of groups required? Show the grouping that minimizes steel while meeting this deadline."

# Typical Floors Only
python3 cli.py --grouping "Analyze only the tower floors (PISO 5 to PISO 20) for 3 groups. These are my typical floors. What's the optimal grouping and how much steel variation exists between the envelope and actual quantities per group?"
```

### Procurement Agent (Run After Grouping Decision)
```bash
# Quality Review
python3 cli.py --procurement "Perform a complete quality review of reinforcement_solution.xlsx. Check for data anomalies, missing values, and provide a procurement readiness assessment. List the top 5 concerns I should address before ordering steel."

# Bar Cutting List
python3 cli.py --procurement "Analyze the RefLong_Total sheet and give me a bar cutting list summary grouped by diameter. Which bar sizes have the highest quantities? Recommend standard commercial lengths to minimize waste."

# Phased Procurement
python3 cli.py --procurement "Based on our grouping decision, I need to procure steel for the first group (PISO 2 through PISO 4) first. Extract the total steel quantities for these floors broken down by longitudinal and transverse reinforcement. What's the delivery timeline recommendation?"

# Envelope Quantities
python3 cli.py --procurement "For floors PISO 5 through PISO 15, calculate the envelope steel quantity assuming all floors use the maximum reinforcement from any floor in this range. Compare this to the as-designed total. What's the percentage increase?"
```

### Scheduling Agent
```bash
# Critical Path
python3 cli.py --scheduling "Load the floor schedule and give me a complete critical path analysis. Which floors are bottlenecks? Rank all floors by duration and identify which work packages are driving the schedule on the slowest floors."

# Resource Trade-off
python3 cli.py --scheduling "I have budget for either 1 additional beam crew OR extending workdays to 10 hours. Compare both scenarios: which option reduces total project duration more? Show me the impact on the top 5 slowest floors."

# Schedule Compression
python3 cli.py --scheduling "My client wants to finish rebar installation in 100 days instead of 148. Calculate the crew configuration needed to achieve this. How many beam crews would I need? What would be the new bottleneck floor?"

# Executive Scenarios
python3 cli.py --scheduling "Generate three scenarios: (1) baseline with 2 beam crews and 8-hour days, (2) moderate acceleration with 3 beam crews, (3) maximum acceleration with 4 beam crews and 10-hour days. For each, show total duration and the percentage reduction from baseline."
```

---

## Recommended Demo Flow

| Step | Duration | Phase | Demo Focus |
|------|----------|-------|------------|
| 1 | 2 min | Pipeline | Show data transformation |
| 2 | 4 min | Grouping | Multi-scenario comparison |
| 3 | 2 min | Grouping | Select a grouping (decision point) |
| 4 | 3 min | Procurement | Quality review |
| 5 | 3 min | Procurement | Phased procurement by group |
| 6 | 3 min | Scheduling | Critical path analysis |
| 7 | 3 min | Scheduling | Resource trade-off |
| **Total** | **20 min** | | |

### Interactive Mode Demo Flow

For a more conversational demo experience, use interactive mode:

```bash
# Step 1: Run the pipeline first
python3 run_rebar_pipeline.py --xlsx data/reinforcement_solution.xlsx

# Step 2: Launch interactive mode
python3 cli.py
```

**Suggested flow in interactive mode:**

1. **Select Agent 1** (Grouping Optimizer)
   - "What levels are available in summary.xlsx?"
   - "Compare optimal groupings for 2, 3, and 4 groups"
   - "What if I need to finish in under 150 days?"
   - Type `back` to return to menu

2. **Select Agent 2** (Procurement)
   - "Perform a quality review of reinforcement_solution.xlsx"
   - "Give me a bar cutting list grouped by diameter"
   - "What are the steel quantities for PISO 2 through PISO 4?"
   - Type `back` to return to menu

3. **Select Agent 3** (Scheduling)
   - "Which floor is the bottleneck?"
   - "Compare adding 1 beam crew vs extending to 10-hour days"
   - "Generate baseline, moderate, and aggressive acceleration scenarios"

**Tip:** In interactive mode, you can ask follow-up questions naturally. The agent remembers context from earlier in the conversation.

---

## Key Value Propositions

1. **Workflow Alignment**: Follows real construction decision sequence - group first, then procure
2. **Optimization**: Data-driven grouping decisions with quantified trade-offs
3. **Integration**: Works directly with ProDet exports - no manual data conversion
4. **Speed**: Hours of manual analysis reduced to seconds
5. **Intelligence**: AI understands construction context and engineering terminology

---

## Closing Statement

> "RC Agent bridges the gap between structural design and construction execution. Starting from ProDet output, it helps you make optimal grouping decisions, plan procurement accordingly, and optimize your installation schedule - all through natural language queries. The platform turns your engineering data into construction intelligence."
