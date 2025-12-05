Your task is to write a **Python module** that:

1. Exposes reusable functions to compute **predicted durations** for each work package (per floor / zone / work_type) based on crew capacity, and
2. Provides a **CLI entrypoint** so the module can be run as a script.

Do **not** generate explanations or commentary in the output of the script — only the code itself. All explanations belong here in this prompt, not in the generated `.py` file.

---

## 1. Overall design

The module must:

1. Define at least two functions:

   ```python
   def compute_duration_for_package(
       pkg: dict,
       crews_per_work_type: dict,
       hours_per_day: float
   ) -> dict:
       """
       Takes a single work package dict and returns a NEW dict
       with added duration fields based on the available crews
       and working hours per day.
       """
   ```

   ```python
   def build_floor_schedule(
       data: dict,
       crews_per_work_type: dict,
       hours_per_day: float
   ) -> dict:
       """
       Takes the full data dict loaded from work_packages.json:
           { "project_id": ..., "work_packages": [...] }
       and returns a NEW dict with per-floor schedules, including
       durations per package and per floor.
       """
   ```

2. Provide a CLI interface so that when the module is executed as a script:

   * It reads an input JSON file (default: `work_packages.json`),
   * Uses `build_floor_schedule(...)` with sensible default crew parameters,
   * Writes the resulting schedule to an output JSON file (default: `floor_schedule.json`).

This structure is important because later `build_floor_schedule` can be wrapped directly as a **LangChain tool**.

---

## 2. Input JSON structure (`work_packages.json`)

You can assume the input file has this structure (as produced by the previous aggregation step):

```json
{
  "project_id": "Ejemplo Mokara",
  "work_packages": [
    {
      "floor_id": "PISO 2",
      "zone_id": null,
      "work_type": "rebar_beams",
      "element_type": "beam",
      "element_ids": ["V-1", "V-2", "V-3"],
      "n_elements": 3,
      "w_total_ton": 2.123,
      "crew_hours_total": 22.0
    }
  ]
}
```

The script must **not** modify this file; it will read from it and produce a separate output JSON with the schedule.

---

## 3. Output JSON structure (`floor_schedule.json`)

The output of `build_floor_schedule` must have the following top-level structure:

```json
{
  "project_id": "Ejemplo Mokara",
  "hours_per_day": 8.0,
  "crews_per_work_type": {
    "rebar_beams": 2,
    "rebar_columns": 1,
    "rebar_walls": 1,
    "rebar_slabs": 2,
    "rebar_unknown": 1
  },
  "floors": [ /* list of floor schedules */ ]
}
```

Each item in `floors` represents a **single floor** with:

* A list of **scheduled work packages** (with durations and crew usage), and
* A consolidated **floor_duration_days** summarizing the time required for the modeled work on that floor.

### 3.1. Floor schedule schema

Each floor schedule must be a dict:

```json
{
  "floor_id": "PISO 2",
  "packages": [
    {
      "floor_id": "PISO 2",
      "zone_id": null,
      "work_type": "rebar_beams",
      "element_type": "beam",
      "element_ids": ["V-1", "V-2", "V-3"],
      "n_elements": 3,
      "w_total_ton": 2.123,
      "crew_hours_total": 22.0,
      "n_crews_assigned": 2,
      "duration_days": 1.375
    }
  ],
  "floor_duration_days": 1.375
}
```

Field definitions:

* `floor_id`: floor identifier copied from the work packages.

* `packages`: list of **package-level** objects, each being the original work package enriched with:

  * `n_crews_assigned`: number of crews allocated to this `work_type` (from `crews_per_work_type`).
  * `duration_days`: predicted duration in **calendar days** for that package, based on crew capacity.

* `floor_duration_days`:

  * The **maximum** `duration_days` among all packages for that floor (assuming all modeled work types can proceed in parallel on that floor).
  * For now, this is a simple “parallel work types” assumption; more complex sequencing can be added later without changing this interface.

---

## 4. Duration model

At this stage, the duration is computed only from:

* `crew_hours_total` in each work package,
* `hours_per_day`, and
* the number of crews available for the `work_type` of the package.

We are **not yet modeling** sequencing between different work types (e.g., columns → beams → slabs). We are only computing how long the **modeled work** (e.g., rebar of beams) would take per floor, assuming enough parallelization within each work type.

### 4.1. Inputs inside `compute_duration_for_package`

Given:

```python
pkg: dict
crews_per_work_type: dict
hours_per_day: float
```

You must:

1. Read from the package:

   ```python
   work_type = pkg.get("work_type")
   crew_hours_total = pkg.get("crew_hours_total", 0.0) or 0.0
   floor_id = pkg.get("floor_id")
   ```

2. Determine number of crews for this work_type:

   ```python
   n_crews = crews_per_work_type.get(work_type, 1)
   ```

   * If `n_crews` is `None`, zero, or negative, treat it as `1` (safety default).

3. Determine `hours_per_day`:

   * Use the `hours_per_day` argument directly.
   * If `hours_per_day <= 0.0`, default to `8.0` internally to avoid division by zero.

4. Compute **daily crew capacity** for this work_type:

   ```python
   daily_capacity = n_crews * hours_per_day  # crew-hours per day
   ```

   * If `daily_capacity <= 0.0`, treat as `1.0` (safety clamp) to avoid division by zero.

5. Compute **duration in days**:

   ```python
   duration_days = crew_hours_total / daily_capacity
   ```

   * You may leave it as a float with full precision or round to a reasonable number of decimals (e.g., 4). Rounding is optional.

6. Return a **new dict** with all original package keys plus:

   ```python
   "n_crews_assigned": n_crews,
   "duration_days": duration_days
   ```

---

## 5. Function behaviors

### 5.1. `compute_duration_for_package(pkg, crews_per_work_type, hours_per_day) -> dict`

Requirements:

* Must **not** mutate the input `pkg`.

* Must:

  * Determine `n_crews` for `pkg["work_type"]`.
  * Compute `duration_days` as described in §4.
  * Return a **new dict** containing all original keys plus:

    * `"n_crews_assigned"`
    * `"duration_days"`

* Must handle missing or malformed fields gracefully:

  * Missing `crew_hours_total` → treat as `0.0`.
  * Missing `work_type` → default `n_crews = 1`.

### 5.2. `build_floor_schedule(data, crews_per_work_type, hours_per_day) -> dict`

Requirements:

* Input `data` has keys `"project_id"` and `"work_packages"` (list).

* Must **not** mutate the input `data`.

* Processing steps:

  1. Extract:

     ```python
     project_id = data.get("project_id")
     packages = data.get("work_packages", [])
     ```

  2. For each package `pkg` in `packages`:

     * Call `compute_duration_for_package(pkg, crews_per_work_type, hours_per_day)` to get `pkg_sched`.

  3. Group `pkg_sched` by `floor_id`:

     * Use a dict keyed by `floor_id`:

       ```python
       floors = {}
       # key: floor_id
       # value: dict with {
       #   "floor_id": floor_id,
       #   "packages": [pkg_sched1, pkg_sched2, ...],
       #   "floor_duration_days": <max of durations>
       # }
       ```

     * For each `pkg_sched`:

       * Append to the corresponding floor’s `packages` list.

  4. For each floor:

     * Compute:

       ```python
       floor_duration_days = max(p["duration_days"] for p in floor["packages"]) if floor["packages"] else 0.0
       ```

     * Store under `floor["floor_duration_days"]`.

  5. Build the final list:

     ```python
     floors_list = list(floors.values())
     ```

* Must return:

  ```python
  {
      "project_id": project_id,
      "hours_per_day": hours_per_day,
      "crews_per_work_type": crews_per_work_type,
      "floors": floors_list
  }
  ```

* If `"work_packages"` is missing or not a list, treat it as an empty list and return an object with an empty `"floors"` list.

---

## 6. Default `crews_per_work_type` and `hours_per_day`

Inside the module, define reasonable defaults, for example:

```python
DEFAULT_HOURS_PER_DAY = 8.0

DEFAULT_CREWS_PER_WORK_TYPE = {
    "rebar_beams": 2,
    "rebar_columns": 1,
    "rebar_walls": 1,
    "rebar_slabs": 2,
    "rebar_unknown": 1,
}
```

These values will be used:

* By default in the CLI entrypoint, and
* As fallback in any helper that does not receive explicit values.

---

## 7. CLI entrypoint

At the bottom of the module, implement:

```python
if __name__ == "__main__":
    ...
```

Behavior:

1. Use `argparse` to support:

   * `--input` (or `-i`): path to input JSON file. Default: `"work_packages.json"`.
   * `--output` (or `-o`): path to output JSON file. Default: `"floor_schedule.json"`.
   * `--hours-per-day` (or `-hpd`): float, optional. Default: `DEFAULT_HOURS_PER_DAY`.

   For now, you do **not** need to support specifying `crews_per_work_type` via CLI; use `DEFAULT_CREWS_PER_WORK_TYPE` inside the script. (This can be extended later.)

2. Steps:

   * Load the input JSON from the given path.

   * Call:

     ```python
     schedule = build_floor_schedule(
         data,
         crews_per_work_type=DEFAULT_CREWS_PER_WORK_TYPE,
         hours_per_day=parsed_hours_per_day
     )
     ```

   * Write `schedule` as JSON to the output path:

     * UTF-8 encoding.
     * `indent=2`.

3. On errors (file not found, invalid JSON), print a clear error message and exit with non-zero code.

---

## 8. Output of the coding run

When responding to this prompt, **only** output the complete Python module code (in a single file), with no surrounding explanations, no markdown fences, and no extra text.

The module must be self-contained and runnable as-is (assuming the Python standard library is available).
