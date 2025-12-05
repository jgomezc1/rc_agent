Your task is to write a **Python module** that:

1. Exposes reusable functions to aggregate **element-level predictions** (with CI and productivity) into **work packages per floor / zone / work type**, and
2. Provides a **CLI entrypoint** so the module can be run as a script.

Do **not** generate explanations or commentary in the output of the script — only the code itself. All explanations belong here in this prompt, not in the generated `.py` file.

---

## 1. Overall design

The module must:

1. Define at least two functions:

   ```python
   def build_work_packages(data: dict) -> dict:
       """
       Takes the full data dict loaded from elements_with_prod.json:
           { "project_id": ..., "elements": [...] }
       and returns a NEW dict with aggregated work packages per
       (floor_id, zone_id, work_type).
       """
   ```

   ```python
   def map_element_to_work_type(element: dict) -> str:
       """
       Takes a single element dict and returns a work_type string
       (e.g. 'rebar_beams', 'rebar_columns', etc.).
       """
   ```

2. Provide a CLI interface so that when the module is executed as a script:

   * It reads an input JSON file (default: `elements_with_prod.json`),
   * Uses `build_work_packages(...)` to aggregate the data,
   * Writes the aggregated workloads to an output JSON file (default: `work_packages.json`).

This structure is important because later `build_work_packages` will be wrapped as a **LangChain tool**.

---

## 2. Input JSON structure (`elements_with_prod.json`)

You can assume the input file has this structure (already enriched by previous tools):

```json
{
  "project_id": "Ejemplo Mokara",
  "elements": [
    {
      "project_id": "Ejemplo Mokara",
      "floor_id": "PISO 2",
      "zone_id": null,
      "element_id": "V-3",
      "element_type": "beam",
      "geometry": null,
      "reinforcement": {
        "w_long_kgf": 528.1,
        "w_trans_kgf": 177.2,
        "w_total_kgf": 705.3,
        "longitudinal_rows": [ ... ],
        "transverse_rows": [ ... ]
      },
      "ci": 1.42,
      "ci_features": {
        "w_total_ton": 0.7053,
        "n_shapes_long": 2,
        "n_diams_long": 2,
        "bar_count_long": 61,
        "n_shapes_trans": 2,
        "n_diams_trans": 1,
        "bar_count_trans": 218
      },
      "prod_pred_ton_per_crew_hour": 0.083,
      "crew_hours_pred": 8.5
    }
  ]
}
```

The script must **not** remove or rename existing keys in this file. It will read from this structure and produce a **separate** aggregated JSON.

---

## 3. Output JSON structure (`work_packages.json`)

The output of `build_work_packages` must be a dict with this top-level structure:

```json
{
  "project_id": "Ejemplo Mokara",
  "work_packages": [ /* list of aggregated work packages */ ]
}
```

Each **work package** is a JSON object representing the total workload for a given:

* `floor_id`
* `zone_id`
* `work_type`  (e.g. “rebar_beams”)

### 3.1. Work package schema

Each work package must have at least:

```json
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
```

Field definitions:

* `floor_id`

  * Copied from `element["floor_id"]` for all elements in this group.

* `zone_id`

  * Copied from `element["zone_id"]`.
  * Elements are grouped by exact `zone_id` value (including `null`).
  * For now, most `zone_id` will be `null`, which is fine; it means “no zoning yet”.

* `work_type`

  * A string describing the type of work, derived by `map_element_to_work_type(element)`.
  * For this first version, you will implement a simple mapping (see §4).

* `element_type`

  * The common `element_type` of all elements in the package (e.g. `"beam"`).
  * For this version, we assume a work package only groups elements with the same `element_type`.

* `element_ids`

  * List of all `element["element_id"]` included in this package.

* `n_elements`

  * Integer count of elements in `element_ids`.

* `w_total_ton`

  * Sum of `w_total_ton` for all elements in this package.
  * For each element, get `w_total_ton` from `ci_features["w_total_ton"]` if available; if missing, compute from `reinforcement["w_total_kgf"] / 1000.0`.

* `crew_hours_total`

  * Sum of `crew_hours_pred` for all elements in this package.
  * For each element, read `element["crew_hours_pred"]`; if missing, treat as `0.0`.

You may include additional fields if useful, but these are the **required minimum**.

---

## 4. `work_type` mapping logic

Implement the helper function:

```python
def map_element_to_work_type(element: dict) -> str:
    ...
```

For this first iteration, use the following rules:

1. Read `element_type = element.get("element_type", "").lower()`.

2. Mapping:

   * If `element_type == "beam"`:

     * return `"rebar_beams"`
   * If `element_type == "column"`:

     * return `"rebar_columns"`
   * If `element_type == "wall"`:

     * return `"rebar_walls"`
   * If `element_type == "slab"`:

     * return `"rebar_slabs"`

3. For any other or missing element_type:

   * return `"rebar_unknown"`

> Note: even if currently most elements are beams, this mapping prepares the structure for future types without changing the interface.

This `work_type` string will be one of the grouping keys.

---

## 5. Grouping / aggregation logic

Inside `build_work_packages(data: dict)`, you must:

1. Read:

   ```python
   project_id = data.get("project_id")
   elements = data.get("elements", [])
   ```

2. Initialize an internal aggregation structure keyed by:

   ```python
   (floor_id, zone_id, work_type)
   ```

   A reasonable approach is to use a dict:

   ```python
   packages = {}
   # key: (floor_id, zone_id, work_type)
   # value: aggregation dict
   ```

3. For each `element` in `elements`:

   * Extract:

     * `floor_id = element.get("floor_id")`
     * `zone_id = element.get("zone_id")`  (may be `None`)
     * `element_id = element.get("element_id")`
     * `element_type = element.get("element_type")`
   * Compute:

     * `work_type = map_element_to_work_type(element)`
   * Extract `w_total_ton`:

     * Prefer `element.get("ci_features", {}).get("w_total_ton")`
     * If missing or `None`, fall back to:

       ```python
       w_total_kgf = element.get("reinforcement", {}).get("w_total_kgf", 0.0) or 0.0
       w_total_ton = w_total_kgf / 1000.0
       ```
   * Extract `crew_hours_pred`:

     ```python
     crew_hours = element.get("crew_hours_pred", 0.0) or 0.0
     ```

4. Use the tuple key:

   ```python
   key = (floor_id, zone_id, work_type)
   ```

   * If `key` is not yet in `packages`, create a new entry:

     ```python
     packages[key] = {
         "floor_id": floor_id,
         "zone_id": zone_id,
         "work_type": work_type,
         "element_type": element_type,
         "element_ids": [],
         "n_elements": 0,
         "w_total_ton": 0.0,
         "crew_hours_total": 0.0,
     }
     ```

   * Append and accumulate:

     ```python
     pkg = packages[key]
     pkg["element_ids"].append(element_id)
     pkg["n_elements"] += 1
     pkg["w_total_ton"] += w_total_ton
     pkg["crew_hours_total"] += crew_hours
     ```

5. After processing all elements, build the final list:

   ```python
   work_packages_list = list(packages.values())
   ```

6. The function `build_work_packages(data)` must then return:

   ```python
   {
       "project_id": project_id,
       "work_packages": work_packages_list
   }
   ```

---

## 6. Function behaviors

### 6.1. `build_work_packages(data: dict) -> dict`

Requirements:

* Must **not** mutate the input `data`.
* Must handle missing or malformed input gracefully:

  * If `"elements"` is missing or not a list, treat it as an empty list.
* Must aggregate only based on:

  * `floor_id`
  * `zone_id` (including `None`)
  * `work_type` (from `map_element_to_work_type`).
* Must always return a dict with keys:

  * `"project_id"` (copied from input),
  * `"work_packages"` (list, possibly empty).

### 6.2. `map_element_to_work_type(element: dict) -> str`

* Must be a pure function.
* Must not mutate `element`.
* Must implement the mapping in §4.

---

## 7. CLI entrypoint

At the bottom of the module, implement:

```python
if __name__ == "__main__":
    ...
```

Behavior:

1. Use `argparse` to support:

   * `--input` (or `-i`): path to input JSON file. Default: `"elements_with_prod.json"`.
   * `--output` (or `-o`): path to output JSON file. Default: `"work_packages.json"`.

2. Steps:

   * Load the input JSON from the given path.
   * Call `build_work_packages(data)`.
   * Write the resulting dict as JSON to the output path:

     * UTF-8 encoding.
     * `indent=2`.

3. On errors (file not found, invalid JSON), print a clear error message and exit with non-zero code.

---

## 8. Output of the coding run

When responding to this prompt, **only** output the complete Python module code (in a single file), with no surrounding explanations, no markdown fences, and no extra text.

The module must be self-contained and runnable as-is (assuming the Python standard library is available).
