Your task is to write a **Python module** that:

1. Exposes reusable functions to compute:

   * **Predicted productivity** (`prod_pred_ton_per_crew_hour`), and
   * **Predicted crew-hours per element** (`crew_hours_pred`),
     starting from the CI-enriched `elements_with_ci.json` file, and
2. Provides a simple **CLI entrypoint** so the module can be run as a script.

Do **not** generate explanations or commentary in the output of the script — only the code itself. All explanations belong here in this prompt, not in the generated `.py` file.

---

## 1. Overall design

The module must:

1. Define at least two functions:

   ```python
   def compute_productivity_for_element(element: dict) -> dict:
       """
       Takes a single CI-enriched element dict and returns
       a NEW element dict with added productivity fields:
       - 'prod_pred_ton_per_crew_hour'
       - 'crew_hours_pred'
       The input element must not be mutated.
       """
   ```

   ```python
   def add_productivity_to_elements(data: dict) -> dict:
       """
       Takes the full data dict loaded from elements_with_ci.json:
           { "project_id": ..., "elements": [...] }
       and returns a NEW dict with the same structure, but with
       each element enriched with productivity-related fields.
       """
   ```

2. Provide a CLI interface so that when the module is executed as a script:

   * It reads an input JSON file (CI-enriched, default: `elements_with_ci.json`),
   * Uses `add_productivity_to_elements(...)` to enrich all elements,
   * Writes the enriched data to an output JSON file (default: `elements_with_prod.json`).

This structure is important because later `compute_productivity_for_element` or `add_productivity_to_elements` will be wrapped directly as a **LangChain tool**.

---

## 2. Input JSON structure (`elements_with_ci.json`)

You can assume the input file has this structure (already enriched by the CI tool):

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
      }
    }
  ]
}
```

The script must **not** remove or rename existing keys. It must only add new fields.

---

## 3. Output JSON structure (`elements_with_prod.json`)

The output of `add_productivity_to_elements` must have the same top-level structure:

```json
{
  "project_id": "Ejemplo Mokara",
  "elements": [ /* enriched elements */ ]
}
```

Each element must preserve all existing keys and be enriched with:

* `"prod_pred_ton_per_crew_hour"`: float – predicted productivity in **tons per crew-hour** for the **standard rebar crew**,
* `"crew_hours_pred"`: float – predicted **crew-hours** required to install the total reinforcement in that element.

### 3.1. Enriched element schema

For each element:

```json
{
  "project_id": "Ejemplo Mokara",
  "floor_id": "PISO 2",
  "zone_id": null,
  "element_id": "V-3",
  "element_type": "beam",
  "geometry": null,
  "reinforcement": { ... },
  "ci": 1.42,
  "ci_features": { ... },
  "prod_pred_ton_per_crew_hour": 0.083,
  "crew_hours_pred": 8.5
}
```

Implementation constraints:

* `compute_productivity_for_element` must return a **new element dict**. It must not modify the input element in-place.
* `add_productivity_to_elements` must return a **new data dict**, not mutate the input.

---

## 4. Productivity model

At this stage, productivity will be computed using a **simple deterministic formula** based on the element’s **CI** and **total weight**.

All productivities are expressed in **tons per crew-hour**, where:

* A **crew-hour** is 1 hour of work by a standard rebar crew (crew size is not modeled in this script; that will be handled later when converting to man-hours or calendar time).

### 4.1. Input values inside `compute_productivity_for_element`

From the element dict:

* `ci`:

  * `ci = element.get("ci", 0.0)`

* `w_total_ton`:

  * Prefer `ci_features["w_total_ton"]` if present:

    ```python
    ci_features = element.get("ci_features", {})
    w_total_ton = ci_features.get("w_total_ton")
    ```
  * If `w_total_ton` is missing or `None`, compute from `reinforcement["w_total_kgf"]`:

    ```python
    reinforcement = element.get("reinforcement", {})
    w_total_kgf = reinforcement.get("w_total_kgf", 0.0) or 0.0
    w_total_ton = w_total_kgf / 1000.0
    ```

* `element_type`:

  ```python
  element_type = element.get("element_type", "unknown")
  ```

If `w_total_ton` is `None` or negative, treat it as `0.0`.

### 4.2. Base productivities per element_type

At module level, define base productivities for a **“CI = 1”** element, per type:

```python
BASE_PRODUCTIVITIES = {
    "beam":   0.10,  # tons per crew-hour (example value)
    "column": 0.08,  # placeholder for future extension
    "wall":   0.07,  # placeholder
    "slab":   0.12,  # placeholder
}
```

These are **initial engineering guesses** and can be tuned later. For this script:

* Use these values as-is.
* If `element_type` is not found in `BASE_PRODUCTIVITIES`, use a conservative default, e.g.:

  ```python
  DEFAULT_BASE_PRODUCTIVITY = 0.08  # tons per crew-hour
  ```

### 4.3. Sensitivity to CI (`k` coefficients)

Define a sensitivity coefficient per element type, controlling how much productivity changes with CI:

```python
K_VALUES = {
    "beam":   0.5,
    "column": 0.5,
    "wall":   0.5,
    "slab":   0.5,
}
```

If `element_type` is not in `K_VALUES`, use a default, e.g.:

```python
DEFAULT_K_VALUE = 0.5
```

### 4.4. Productivity formula

For each element:

1. Get `base_prod` and `k`:

   ```python
   base_prod = BASE_PRODUCTIVITIES.get(element_type, DEFAULT_BASE_PRODUCTIVITY)
   k = K_VALUES.get(element_type, DEFAULT_K_VALUE)
   ```

2. If `w_total_ton <= 0.0`:

   * Set:

     ```python
     prod_pred = 0.0
     crew_hours_pred = 0.0
     ```
   * Return the enriched element with these values.

3. If `ci <= 0.0`:

   * Treat as `ci = 1.0` (no complexity adjustment), i.e.:

     ```python
     ci_effective = 1.0
     ```

4. For `ci > 0.0`, define:

   ```python
   ci_effective = ci
   ```

5. Compute predicted productivity:

   ```python
   denom = 1.0 + k * (ci_effective - 1.0)
   if denom <= 0.0:
       # safety clamp: avoid division by zero or negative productivity
       denom = 0.1
   prod_pred = base_prod / denom  # tons per crew-hour
   ```

6. Compute predicted crew-hours for that element:

   ```python
   crew_hours_pred = w_total_ton / prod_pred
   ```

7. Optionally, you may round `prod_pred` and `crew_hours_pred` to a reasonable number of decimals (e.g. 4); this is not strictly required.

---

## 5. Function behaviors

### 5.1. `compute_productivity_for_element(element: dict) -> dict`

Requirements:

* Must read:

  * `element["ci"]` (default 0.0 if missing),
  * `element["ci_features"]["w_total_ton"]` if present,
  * otherwise compute `w_total_ton` from `reinforcement["w_total_kgf"]`.
* Must determine `element_type` from `element["element_type"]`.
* Must compute:

  * `prod_pred_ton_per_crew_hour` (float),
  * `crew_hours_pred` (float).
* Must **not** mutate the input `element`.
* Must return a **new dict** with all original keys and the two new keys added at the top level:

  ```python
  enriched = {
      **element,
      "prod_pred_ton_per_crew_hour": prod_pred,
      "crew_hours_pred": crew_hours_pred,
  }
  ```

### 5.2. `add_productivity_to_elements(data: dict) -> dict`

Requirements:

* `data` has keys `"project_id"` and `"elements"` (list).

* Must not mutate the input `data`.

* Must return a **new dict**:

  ```python
  {
      "project_id": data.get("project_id"),
      "elements": [ compute_productivity_for_element(e) for e in data.get("elements", []) ]
  }
  ```

* If `"elements"` is missing or not a list, treat it as an empty list.

---

## 6. CLI entrypoint

At the bottom of the module, implement:

```python
if __name__ == "__main__":
    ...
```

Behavior:

1. Use `argparse` to support:

   * `--input` (or `-i`): path to input JSON file. Default: `"elements_with_ci.json"`.
   * `--output` (or `-o`): path to output JSON file. Default: `"elements_with_prod.json"`.

2. Steps:

   * Load the input JSON from the given path.
   * Call `add_productivity_to_elements(data)`.
   * Write the resulting dict as JSON to the output path:

     * UTF-8 encoding.
     * `indent=2`.

3. On errors (file not found, invalid JSON), print a clear error message and exit with non-zero code.

---

## 7. Output of the coding run

When responding to this prompt, **only** output the complete Python module code (in a single file), with no surrounding explanations, no markdown fences, and no extra text.

The module must be self-contained and runnable as-is (assuming the Python standard library is available).
