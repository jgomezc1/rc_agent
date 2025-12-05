Your task is to write a **Python module** that defines:

1. A set of **LangChain tools** for working with the **RC rebar scheduling JSONs** (`work_packages.json` and `floor_schedule.json`), and
2. An **LCEL + LangGraph agent** class `SchedulingAgent`, implemented in a style consistent with `ProcurementAgent` in `procurement_agent.py`. 

Do **not** generate explanations or commentary in the output of the script — only the code itself. All explanations belong here in this prompt, not in the generated `.py` file.

The module will be used in the same project as `procurement_agent.py`.

---

## 1. Context and assumptions

Previous steps in the pipeline already exist as separate modules/scripts:

* `elements_from_xlsx_tool` → `elements.json`
* `ci_tool` → `elements_with_ci.json`
* `prod_tool` → `elements_with_prod.json`
* `aggregate_workload_tool` → `work_packages.json`
* `schedule_tool` → `floor_schedule.json`

In this prompt we focus on the **last stage**:

* Consuming **`work_packages.json`** to compute **floor-level schedules** via `schedule_tool.build_floor_schedule`.
* Reading / interrogating **`floor_schedule.json`**.

Assume there is a module `schedule_tool.py` already created from a previous step, with at least:

```python
DEFAULT_HOURS_PER_DAY: float
DEFAULT_CREWS_PER_WORK_TYPE: dict

def compute_duration_for_package(pkg: dict, crews_per_work_type: dict, hours_per_day: float) -> dict: ...
def build_floor_schedule(data: dict, crews_per_work_type: dict, hours_per_day: float) -> dict: ...
```

You must **import and reuse** these functions and defaults; do not re-implement the scheduling math.

---

## 2. High-level goals

This module must provide:

1. **LangChain tools**:

   * `compute_floor_schedule_tool`

     * Given `work_packages.json` (or a path) and crew parameters, returns a fresh schedule dict.

   * `load_floor_schedule_tool`

     * Given a `floor_schedule.json` path, loads and returns the schedule plus some helpful derived summaries.

2. A `SchedulingAgent` class:

   * Uses `ChatOpenAI` and `create_react_agent` from LangGraph, just like `ProcurementAgent`. 
   * Uses the tools above.
   * Exposes a `run(...)` method that:

     * Accepts a `user_input` string and optional `chat_history` list.
     * Invokes the LangGraph agent with LCEL style and returns the **assistant’s final message text**.

---

## 3. Module structure

### 3.1. Imports and logging

At the top of the module:

* Standard:

  ```python
  import os
  import json
  import logging
  from typing import Dict, Any, List, Optional
  ```

* Third-party:

  ```python
  from langchain_openai import ChatOpenAI
  from langchain_core.tools import tool
  from langchain_core.messages import HumanMessage
  from langgraph.prebuilt import create_react_agent
  ```

* Local:

  ```python
  from schedule_tool import (
      DEFAULT_HOURS_PER_DAY,
      DEFAULT_CREWS_PER_WORK_TYPE,
      build_floor_schedule,
  )
  ```

Configure logging like in `procurement_agent.py` (basicConfig + `logger = logging.getLogger(__name__)`). 

### 3.2. Defaults and helpers

Define:

```python
DEFAULT_WORK_PACKAGES_PATH = "data/work_packages.json"
DEFAULT_FLOOR_SCHEDULE_PATH = "data/floor_schedule.json"
```

You may also define small internal helper functions if needed (e.g., to safely load JSON).

---

## 4. Tool 1: `compute_floor_schedule_tool`

Define a LangChain tool:

```python
@tool
def compute_floor_schedule_tool(
    work_packages_path: str = DEFAULT_WORK_PACKAGES_PATH,
    hours_per_day: float = DEFAULT_HOURS_PER_DAY,
    rebar_beams_crews: int = 2,
    rebar_columns_crews: int = 1,
    rebar_walls_crews: int = 1,
    rebar_slabs_crews: int = 2,
    rebar_unknown_crews: int = 1,
) -> Dict[str, Any]:
    """
    Compute a fresh floor-level schedule from work_packages.json.

    Uses schedule_tool.build_floor_schedule and returns the full schedule dict.
    """
```

**Behavior:**

1. Validate that `work_packages_path` exists; if not, return `{ "error": "..."}`

2. Load the JSON:

   ```python
   with open(work_packages_path, "r", encoding="utf-8") as f:
       data = json.load(f)
   ```

3. Build `crews_per_work_type` from parameters:

   ```python
   crews_per_work_type = DEFAULT_CREWS_PER_WORK_TYPE.copy()
   crews_per_work_type["rebar_beams"] = max(1, int(rebar_beams_crews or 1))
   crews_per_work_type["rebar_columns"] = max(1, int(rebar_columns_crews or 1))
   crews_per_work_type["rebar_walls"] = max(1, int(rebar_walls_crews or 1))
   crews_per_work_type["rebar_slabs"] = max(1, int(rebar_slabs_crews or 1))
   crews_per_work_type["rebar_unknown"] = max(1, int(rebar_unknown_crews or 1))
   ```

   * If any crew argument is `None`, 0, or negative, clamp it to `1`.

4. Sanitize `hours_per_day`:

   ```python
   if hours_per_day is None or hours_per_day <= 0:
       hours_per_day = DEFAULT_HOURS_PER_DAY
   ```

5. Call `build_floor_schedule(data, crews_per_work_type, hours_per_day)`.

6. Return the resulting schedule dict.

7. Wrap in `try/except` and log errors; on exception return `{ "error": str(e) }`.

---

## 5. Tool 2: `load_floor_schedule_tool`

Define a second tool:

```python
@tool
def load_floor_schedule_tool(
    floor_schedule_path: str = DEFAULT_FLOOR_SCHEDULE_PATH,
) -> Dict[str, Any]:
    """
    Load an existing floor_schedule.json file and return a summarized view.

    Useful when you already have a schedule computed and want to inspect it.
    """
```

**Behavior:**

1. Check file existence (`os.path.exists`); if missing, return `{ "error": "...not found..." }`.

2. Load:

   ```python
   with open(floor_schedule_path, "r", encoding="utf-8") as f:
       schedule = json.load(f)
   ```

3. Derive a lightweight summary:

   * Extract list of floor_ids and their `floor_duration_days`.

   * Compute:

     ```python
     floors = schedule.get("floors", [])
     floor_summaries = []
     for f in floors:
         floor_id = f.get("floor_id")
         duration = f.get("floor_duration_days", 0.0)
         floor_summaries.append({"floor_id": floor_id, "floor_duration_days": duration})
     ```

   * Compute `max_floor_duration_days` and `total_floors`.

4. Return a dict like:

   ```python
   return {
       "file_path": floor_schedule_path,
       "project_id": schedule.get("project_id"),
       "hours_per_day": schedule.get("hours_per_day"),
       "crews_per_work_type": schedule.get("crews_per_work_type"),
       "floors": schedule.get("floors", []),
       "summary": {
           "total_floors": len(floor_summaries),
           "floor_durations": floor_summaries,
           "max_floor_duration_days": max_duration,
       },
   }
   ```

5. Use `try/except` and logging; on error, return `{ "error": str(e) }`.

---

## 6. `SchedulingAgent` class

Create a class similar in spirit to `ProcurementAgent` in `procurement_agent.py`. 

### 6.1. Docstring

At class level:

```python
class SchedulingAgent:
    """
    LCEL-based agent for rebar scheduling and floor cycle planning.

    Helps analyze rebar workloads (in tonf & crew-hours), evaluate floor-level
    durations, and explore what-if scenarios with different crew allocations.
    """
```

### 6.2. SYSTEM_PROMPT

Define a `SYSTEM_PROMPT` string constant inside the class, in the same style and level of detail as `ProcurementAgent.SYSTEM_PROMPT`. It must:

* Set the role: *“You are an expert construction planner specializing in reinforced concrete rebar scheduling.”*

* Explain what the agent does:

  * Consumes **work packages** and **floor schedules** generated from ProDet.
  * Helps:

    * Understand `crew_hours_total` per floor/work_type.
    * Compute `duration_days` given crew allocations and hours/day.
    * Compare floors, identify the critical (slowest) floor, etc.
    * Run simple what-if analyses (e.g., “What if I add one more rebar_beams crew?”).

* Enumerate available tools:

  1. `compute_floor_schedule_tool` – compute schedule from `work_packages.json` and crew parameters.
  2. `load_floor_schedule_tool` – load and summarize an existing `floor_schedule.json`.

* Give **usage guidelines** to the LLM:

  * If the user asks for **current floor durations**, first try `load_floor_schedule_tool`. If it fails because the file does not exist, suggest running `compute_floor_schedule_tool`.
  * If the user asks a **what-if** question (change crews or hours/day), call `compute_floor_schedule_tool` with appropriate parameters and compare the new schedule to previously loaded one if available.
  * Always explain results clearly:

    * Per-floor duration.
    * Which floor controls the overall cycle (max duration).
    * Qualitative interpretation (e.g., “PISO 10 is currently the bottleneck”).

* Briefly recap the meaning of key fields:

  * `crew_hours_total`: total predicted crew-hours for that work package.
  * `n_crews_assigned`: crews available for that work_type.
  * `duration_days = crew_hours_total / (n_crews_assigned * hours_per_day)`.
  * `floor_duration_days`: max duration among packages on that floor.

* Instruct the agent to:

  * Prefer **calling tools** for schedule math instead of trying to compute everything internally.
  * Return concise, structured answers (e.g., bullet lists, small tables in markdown).

The content style should follow the tone and richness of the `ProcurementAgent.SYSTEM_PROMPT` (detailed but practical). 

### 6.3. `__init__`

Implement:

```python
def __init__(self, model_name: str = "gpt-4.1-mini", temperature: float = 0.0):
    """Initialize the scheduling agent."""
    self.llm = ChatOpenAI(
        model=model_name,
        temperature=temperature,
    )
    self.tools = [compute_floor_schedule_tool, load_floor_schedule_tool]

    self.agent = create_react_agent(
        self.llm,
        tools=self.tools,
        prompt=self.SYSTEM_PROMPT,
    )
```

(Use the same pattern / signature for `create_react_agent` as in `ProcurementAgent`.) 

### 6.4. `run` method

Implement:

```python
def run(
    self,
    user_input: str,
    chat_history: Optional[List[HumanMessage]] = None,
) -> str:
    """
    Run the scheduling agent on a user query.

    Returns the final assistant message content as a string.
    """
```

Behavior:

1. Initialize `messages: List[HumanMessage] = []`.

2. If `chat_history` is provided and non-empty, extend `messages` with it.

3. Append `HumanMessage(content=user_input)` to `messages`.

4. Invoke the agent:

   ```python
   result = self.agent.invoke({"messages": messages})
   ```

5. If `result` has a `"messages"` key and is a list, return the **content of the last message**. Otherwise, cast `result` to string and return.

Same pattern as in `ProcurementAgent.run` (or equivalent method). 

---

## 7. Optional standalone helper

At the bottom of the module, after the class definition, add a small standalone function:

```python
def run_schedule_from_cli(
    work_packages_path: str = DEFAULT_WORK_PACKAGES_PATH,
    hours_per_day: float = DEFAULT_HOURS_PER_DAY,
) -> Dict[str, Any]:
    """
    Convenience function: compute a schedule directly without LLM.

    Useful for quick tests and debugging.
    """
```

Behavior:

* Build a `crews_per_work_type` dict from `DEFAULT_CREWS_PER_WORK_TYPE` (no overrides).
* Load `work_packages_path`, call `build_floor_schedule`, and return the schedule dict.
* On error, return `{ "error": str(e) }`.

This function is not a LangChain tool and is just for direct Python use.

---

## 8. Output of the coding run

When responding to this prompt, **only** output the complete Python module code (in a single file), with no surrounding explanations, no markdown fences, and no extra text.

The module must be self-contained (aside from the import of `schedule_tool`) and runnable as-is, assuming:

* `schedule_tool.py` exists with the functions described above, and
* The LangChain / LangGraph / OpenAI environment is properly installed and configured.
