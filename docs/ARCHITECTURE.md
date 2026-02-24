# RC Agent Platform - Architecture Documentation

## Overview

The RC Agent Platform is a **construction intelligence system** for reinforced concrete (RC) projects. It combines a **deterministic data pipeline** with **LLM-powered AI agents** to optimize floor groupings, plan steel procurement, and analyze rebar installation schedules.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RC AGENT PLATFORM ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────┐     ┌──────────────────┐     ┌─────────────────────────┐  │
│   │   ProDet    │────▶│  Data Pipeline   │────▶│    JSON Artifacts       │  │
│   │  Excel File │     │  (Deterministic)  │     │  (Intermediate Data)    │  │
│   └─────────────┘     └──────────────────┘     └───────────┬─────────────┘  │
│                                                            │                 │
│                                                            ▼                 │
│   ┌─────────────┐     ┌──────────────────┐     ┌─────────────────────────┐  │
│   │    User     │────▶│    CLI / API     │────▶│    LangGraph Agents     │  │
│   │   Query     │     │   (cli.py)       │     │   (ReAct Pattern)       │  │
│   └─────────────┘     └──────────────────┘     └───────────┬─────────────┘  │
│                                                            │                 │
│                                                            ▼                 │
│                                              ┌─────────────────────────────┐ │
│                                              │     OpenAI GPT (LLM)        │ │
│                                              │  Reasoning + Tool Calling   │ │
│                                              └─────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **LLM Provider** | OpenAI GPT (gpt-4.1-mini) | Natural language understanding, reasoning, tool selection |
| **Agent Framework** | LangGraph + LangChain | ReAct agent orchestration, tool binding, message handling |
| **Data Validation** | Pydantic | Typed data models, input/output validation |
| **Data Processing** | Pandas, OpenPyXL | Excel parsing, data transformation |
| **PDF Generation** | ReportLab | Professional procurement reports |
| **Configuration** | python-dotenv | Environment variable management |
| **Runtime** | Python 3.8+ | Core application runtime |

---

## LangGraph Agent Architecture

The platform uses **LangGraph's `create_react_agent`** to implement the ReAct (Reasoning + Acting) pattern. Each agent follows the same architectural pattern:

### ReAct Agent Pattern

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LANGGRAPH REACT AGENT                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   User Query                                                                 │
│       │                                                                      │
│       ▼                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        AGENT LOOP (LangGraph)                        │   │
│   │  ┌─────────────────────────────────────────────────────────────┐    │   │
│   │  │                                                             │    │   │
│   │  │   ┌──────────┐    ┌──────────┐    ┌──────────┐             │    │   │
│   │  │   │  REASON  │───▶│  DECIDE  │───▶│   ACT    │             │    │   │
│   │  │   │  (LLM)   │    │  (LLM)   │    │  (Tool)  │             │    │   │
│   │  │   └──────────┘    └──────────┘    └────┬─────┘             │    │   │
│   │  │        ▲                               │                    │    │   │
│   │  │        │         ┌──────────┐          │                    │    │   │
│   │  │        └─────────│ OBSERVE  │◀─────────┘                    │    │   │
│   │  │                  │ (Result) │                               │    │   │
│   │  │                  └──────────┘                               │    │   │
│   │  │                                                             │    │   │
│   │  └─────────────────────────────────────────────────────────────┘    │   │
│   │                              │                                       │   │
│   │                              ▼ (Loop until done)                     │   │
│   │                      ┌──────────────┐                                │   │
│   │                      │ FINAL ANSWER │                                │   │
│   │                      └──────────────┘                                │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Agent Implementation Pattern

All three agents follow the same implementation pattern:

```python
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

class Agent:
    SYSTEM_PROMPT = """..."""  # Domain-specific instructions

    def __init__(self, model_name="gpt-4.1-mini", temperature=0.0):
        # 1. Initialize LLM
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)

        # 2. Define tools (deterministic Python functions)
        self.tools = [tool_1, tool_2, ...]

        # 3. Create ReAct agent via LangGraph
        self.agent = create_react_agent(
            self.llm,
            tools=self.tools,
            prompt=self.SYSTEM_PROMPT
        )

    def run(self, user_input, chat_history=None, max_iterations=15):
        # 4. Invoke agent with recursion limit
        result = self.agent.invoke(
            {"messages": messages},
            config={"recursion_limit": max_iterations}
        )
        return result["messages"][-1].content
```

---

## LangGraph Nodes and Edges

LangGraph's `create_react_agent` creates a **state machine** with the following structure:

### State Graph Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LANGGRAPH STATE MACHINE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                              ┌──────────────┐                                │
│                              │    START     │                                │
│                              └──────┬───────┘                                │
│                                     │                                        │
│                                     ▼                                        │
│                         ┌───────────────────────┐                            │
│                         │                       │                            │
│                         │    AGENT NODE         │ ◀────────────────┐         │
│                         │    (LLM Reasoning)    │                  │         │
│                         │                       │                  │         │
│                         └───────────┬───────────┘                  │         │
│                                     │                              │         │
│                          ┌──────────┴──────────┐                   │         │
│                          │                     │                   │         │
│                          ▼                     ▼                   │         │
│              ┌─────────────────┐    ┌─────────────────┐            │         │
│              │  Tool Call?     │    │  Final Answer?  │            │         │
│              │     YES         │    │      YES        │            │         │
│              └────────┬────────┘    └────────┬────────┘            │         │
│                       │                      │                     │         │
│                       ▼                      ▼                     │         │
│              ┌─────────────────┐    ┌─────────────────┐            │         │
│              │   TOOLS NODE    │    │      END        │            │         │
│              │ (Execute Tool)  │    │                 │            │         │
│              └────────┬────────┘    └─────────────────┘            │         │
│                       │                                            │         │
│                       └────────────────────────────────────────────┘         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Node Descriptions

| Node | Type | Description |
|------|------|-------------|
| **START** | Entry | Initial state, receives user message |
| **AGENT** | LLM Call | Sends messages to LLM, receives reasoning + tool calls or final answer |
| **TOOLS** | Execution | Executes requested tools, returns results to agent |
| **END** | Terminal | Agent has produced final response |

### Edge Conditions

| From | To | Condition |
|------|-----|-----------|
| START | AGENT | Always (initial message) |
| AGENT | TOOLS | LLM response contains tool calls |
| AGENT | END | LLM response is final answer (no tool calls) |
| TOOLS | AGENT | Tool execution complete, return results |

### Message Flow

```
Messages State (accumulates throughout conversation):
┌────────────────────────────────────────────────────────────────┐
│ [HumanMessage]     → User's query                              │
│ [AIMessage]        → LLM reasoning + tool_calls                │
│ [ToolMessage]      → Tool execution results                    │
│ [AIMessage]        → LLM reasoning + more tool_calls (or done) │
│ [ToolMessage]      → More tool results                         │
│ [AIMessage]        → Final answer (no tool_calls)              │
└────────────────────────────────────────────────────────────────┘
```

---

## Agent Implementations

### 1. Grouping Optimizer Agent

**File:** `grouping_optimizer.py`

**Purpose:** Optimize floor groupings to minimize steel consumption while considering construction duration trade-offs.

#### Tools

| Tool | Function | Description |
|------|----------|-------------|
| `inspect_data_file` | Exploration | Inspect Excel/CSV file to see available levels and steel values |
| `grouping_optimizer_v1` | Optimization | Run dynamic programming optimization for floor groupings |

#### System Prompt Summary
- Uses `data/summary.xlsx` as default input
- Evaluates hundreds of partition combinations
- Returns top N scenarios ranked by steel (primary) and duration (secondary)
- Explains trade-offs between steel savings and construction efficiency

#### Core Optimizer (Deterministic)
The `GroupingOptimizer` class implements:
- Dynamic programming for partition generation
- Envelope steel calculation per group
- Duration computation based on formwork reuse assumptions

```python
# Key formula
envelope_steel = max(steel_values_in_group)
group_duration = days_first_in_group + (group_size - 1) * days_repeated
```

---

### 2. Procurement Agent

**File:** `procurement_agent.py`

**Purpose:** Review ProDet reinforcement files and generate procurement reports with bar cutting lists.

#### Tools

| Tool | Function | Description |
|------|----------|-------------|
| `list_data_files` | Discovery | List available Excel/CSV files in a directory |
| `review_reinforcement_file` | Validation | Review file for completeness, detect issues |
| `list_available_floors` | Exploration | List all floors in the reinforcement file |
| `generate_procurement_report` | Generation | Generate detailed procurement report with optional PDF |

#### System Prompt Summary
- Understands ProDet file structure (5 sheets)
- Maps Spanish column names to standard schema
- Generates bar cutting lists grouped by diameter, shape, length
- Produces professional PDF reports via ReportLab

#### ProDet Schema Knowledge
The agent has built-in knowledge of ProDet Excel structure:

| Sheet | Purpose | Key Columns |
|-------|---------|-------------|
| `Resumen_Refuerzo` | Story totals | Nivel, Ref.Longitudinal, Ref.Transversal, Total por nivel |
| `RefLong_PorElemento` | Longitudinal by element | Piso, Elemento, Figura, Calibre, L_total, Cantidad, Peso |
| `RefLong_Total` | Global longitudinal | Figura, Calibre, L_total, Cantidad, Peso |
| `RefTrans_PorElemento` | Transverse by element | Piso, Elemento, Figura, Calibre, Base, Altura, Cantidad |
| `RefTrans_Total` | Global transverse | Figura, Calibre, Base, Altura, Cantidad, Peso |

---

### 3. Scheduling Agent

**File:** `scheduling_agent.py`

**Purpose:** Analyze rebar installation schedules, identify bottlenecks, and explore what-if scenarios.

#### Tools

| Tool | Function | Description |
|------|----------|-------------|
| `load_floor_schedule_tool` | Load | Load existing `floor_schedule.json` and summarize |
| `compute_floor_schedule_tool` | Compute | Compute fresh schedule with custom crew allocation |

#### System Prompt Summary
- Works with work packages and floor schedules from the data pipeline
- Computes duration based on crew-hours, crew count, and hours per day
- Identifies bottleneck floors (critical path)
- Enables what-if analysis (add crews, extend hours)

#### Duration Formula
```python
duration_days = crew_hours_total / (n_crews_assigned * hours_per_day)
floor_duration_days = max(package_durations_on_floor)  # Parallel work assumption
```

---

## Data Pipeline Architecture

The data pipeline transforms ProDet Excel exports into structured JSON artifacts consumed by the agents.

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA PIPELINE FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  reinforcement_solution.xlsx                                                 │
│            │                                                                 │
│            ▼                                                                 │
│  ┌─────────────────────────────────┐                                         │
│  │    STEP 1: PARSER               │  reinforcement_parser.py                │
│  │    Excel → Canonical JSON       │                                         │
│  └─────────────┬───────────────────┘                                         │
│                │                                                             │
│                ▼                                                             │
│         elements.json                                                        │
│                │                                                             │
│                ▼                                                             │
│  ┌─────────────────────────────────┐                                         │
│  │    STEP 2: COMPLEXITY INDEX     │  complexity_index.py                    │
│  │    Add CI score per element     │                                         │
│  └─────────────┬───────────────────┘                                         │
│                │                                                             │
│                ▼                                                             │
│         elements_with_ci.json                                                │
│                │                                                             │
│                ▼                                                             │
│  ┌─────────────────────────────────┐                                         │
│  │    STEP 3: PRODUCTIVITY         │  productivity.py                        │
│  │    Predict crew-hours/element   │                                         │
│  └─────────────┬───────────────────┘                                         │
│                │                                                             │
│                ▼                                                             │
│         elements_with_prod.json                                              │
│                │                                                             │
│                ▼                                                             │
│  ┌─────────────────────────────────┐                                         │
│  │    STEP 4: WORK PACKAGES        │  work_packages.py                       │
│  │    Aggregate by floor/type      │                                         │
│  └─────────────┬───────────────────┘                                         │
│                │                                                             │
│                ▼                                                             │
│         work_packages.json                                                   │
│                │                                                             │
│                ▼                                                             │
│  ┌─────────────────────────────────┐                                         │
│  │    STEP 5: FLOOR SCHEDULE       │  floor_schedule.py                      │
│  │    Compute durations            │                                         │
│  └─────────────┬───────────────────┘                                         │
│                │                                                             │
│                ▼                                                             │
│         floor_schedule.json                                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pipeline Orchestrator

**File:** `run_rebar_pipeline.py`

Runs all 5 steps sequentially with configurable parameters:

```bash
python run_rebar_pipeline.py --xlsx data/reinforcement_solution.xlsx
python run_rebar_pipeline.py --xlsx data/file.xlsx --hours-per-day 10 --data-dir output
```

### JSON Artifact Schema

#### elements.json
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
        "w_total_kgf": 705.3
      }
    }
  ]
}
```

#### elements_with_ci.json
```json
{
  "ci": 1.42,
  "ci_features": {
    "w_total_ton": 0.7053,
    "bar_count_long": 61,
    "bar_count_trans": 218,
    "n_shapes_long": 2,
    "n_diams_long": 2
  }
}
```

#### work_packages.json
```json
{
  "work_packages": [
    {
      "floor_id": "PISO 2",
      "work_type": "rebar_beams",
      "n_elements": 3,
      "w_total_ton": 2.123,
      "crew_hours_total": 22.0
    }
  ]
}
```

#### floor_schedule.json
```json
{
  "hours_per_day": 8.0,
  "crews_per_work_type": {"rebar_beams": 2, "rebar_columns": 1},
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

## CLI Architecture

**File:** `cli.py`

The CLI provides two modes of operation:

### Interactive Mode
```bash
python cli.py
```

```
┌──────────────────────────────────────────────────────────────┐
│                    INTERACTIVE MODE                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   Display Banner                                             │
│         │                                                    │
│         ▼                                                    │
│   Show Agent Menu                                            │
│         │                                                    │
│         ▼                                                    │
│   User Selects Agent (1, 2, 3)                               │
│         │                                                    │
│         ▼                                                    │
│   ┌─────────────────────────────────────────────────────┐    │
│   │              AGENT CHAT LOOP                        │    │
│   │                                                     │    │
│   │   User Input ──▶ Agent.run() ──▶ Display Response   │    │
│   │        ▲                              │             │    │
│   │        └──────────────────────────────┘             │    │
│   │                                                     │    │
│   │   Commands: 'back' → menu, 'exit' → quit            │    │
│   └─────────────────────────────────────────────────────┘    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Single Query Mode
```bash
python cli.py --grouping "Optimize floors with k=2,3,4"
python cli.py --procurement "Review reinforcement_solution.xlsx"
python cli.py --scheduling "Which floor is the bottleneck?"
```

### Chat History Management
The CLI maintains conversation history as LangChain message objects:

```python
chat_history = []
# After each exchange:
chat_history.append(HumanMessage(content=user_input))
chat_history.append(AIMessage(content=response))
# Passed to agent.run() for context preservation
```

---

## Tool Registration Pattern

Tools are registered using LangChain's `@tool` decorator:

```python
from langchain_core.tools import tool

@tool
def my_tool(
    param1: str,
    param2: int = 10
) -> Dict[str, Any]:
    """
    Tool description (used by LLM for tool selection).

    Args:
        param1: Description of param1
        param2: Description of param2. Default: 10

    Returns:
        Dictionary with results
    """
    # Deterministic computation
    result = compute_something(param1, param2)
    return result
```

The `@tool` decorator:
1. Extracts function signature for LLM tool calling
2. Parses docstring for tool description
3. Handles type conversion and validation
4. Wraps function for LangChain integration

---

## Error Handling

### Agent Level
- `max_iterations` parameter prevents infinite loops
- `recursion_limit` in LangGraph config
- Try-catch around agent invocation

### Tool Level
- All tools return `{"error": "message"}` on failure
- File existence checks before operations
- Type coercion with error handling

### Pipeline Level
- Each step validates inputs/outputs
- Pipeline halts on first failure
- Logging throughout for debugging

---

## Configuration

### Environment Variables (.env)
```
OPENAI_API_KEY=sk-proj-...
```

### Default Parameters

| Parameter | Default | Location |
|-----------|---------|----------|
| `model_name` | gpt-4.1-mini | Agent constructors |
| `temperature` | 0.0 | Agent constructors |
| `max_iterations` | 15 | agent.run() |
| `hours_per_day` | 8.0 | floor_schedule.py |
| `rebar_beams_crews` | 2 | floor_schedule.py |
| `rebar_columns_crews` | 1 | floor_schedule.py |

---

## Summary

The RC Agent Platform demonstrates a **hybrid architecture** combining:

1. **Deterministic Data Pipeline** - Reliable, reproducible transformations
2. **LangGraph ReAct Agents** - Flexible, reasoning-capable interfaces
3. **LangChain Tools** - Clean separation of concerns
4. **Structured JSON Artifacts** - Interoperable data exchange

This design ensures that critical calculations (optimization, scheduling) remain deterministic and testable, while the LLM layer handles natural language understanding, tool orchestration, and result explanation.
