---


Your task is to write a **Python module** that:

1. Exposes **reusable functions** to compute a Complexity Index (CI) and features for elements loaded from `elements.json` (so it can later be used as a LangChain tool), and
2. Provides a simple **CLI entrypoint** so the module can be run as a script to read `elements.json` and write `elements_with_ci.json`.

Do **not** generate explanations or commentary in the output of the script — only the code itself. All explanations belong here in this prompt, not in the generated `.py` file.

---

## 1. Overall design

The module must:

1. Define at least two functions:

   ```python
   def compute_ci_for_element(element: dict) -> dict:
       """
       Takes a single element dict (as in elements.json) and returns
       a NEW element dict with added 'ci' and 'ci_features'.
       The input element must not be mutated.
       """
   ```

   ```python
   def add_ci_to_elements(data: dict) -> dict:
       """
       Takes the full data dict loaded from elements.json:
           { "project_id": ..., "elements": [...] }
       and returns a NEW dict with the same structure, but with
       each element enriched with 'ci' and 'ci_features'.
       """
   ```

2. Provide a CLI interface so that when the module is executed as a script:

   * It reads an input JSON file (`elements.json` by default).
   * Uses `add_ci_to_elements(...)` to enrich all elements.
   * Writes the enriched data to `elements_with_ci.json` (or a given output path).

This structure is important because later `compute_ci_for_element` or `add_ci_to_elements` will be wrapped directly as a **LangChain tool**.

---

## 2. Input JSON structure (`elements.json`)

You can assume an existing file with this structure:

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
        "longitudinal_rows": [
          {
            "piso": "PISO 2",
            "elemento": "V-3",
            "figura": "L",
            "calibre": "5/8\"",
            "l_recta_m": 1.25,
            "l_gancho_izq_m": 0.25,
            "l_gancho_der_m": null,
            "l_total_m": 1.5,
            "cantidad": 2,
            "peso_kgf": 15.2
          }
        ],
        "transverse_rows": [
          {
            "piso": "PISO 2",
            "elemento": "V-3",
            "figura": "[",
            "calibre": "3/8\"",
            "base_m": null,
            "altura_m": 0.44,
            "cantidad": 80,
            "peso_kgf": 29.3
          }
        ]
      }
    }
  ]
}
```

You must **not** remove or rename existing keys; only add new ones.

---

## 3. Output JSON structure (`elements_with_ci.json`)

The output of `add_ci_to_elements` must have the same top-level structure:

```json
{
  "project_id": "Ejemplo Mokara",
  "elements": [ /* enriched elements */ ]
}
```

Each element must preserve all existing keys and be enriched with:

* `"ci"`: a float (Complexity Index, unitless),
* `"ci_features"`: an object with the intermediate feature values.

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
```

Implementation constraints:

* `compute_ci_for_element` must return a **new element dict**. It should not modify the input element in-place.
* `add_ci_to_elements` must return a **new data dict**, not modify the input.

---

## 4. Feature definitions

Inside `compute_ci_for_element`, you must compute the following features from `element["reinforcement"]`:

Let:

* `reinforcement = element.get("reinforcement", {})`
* `L = reinforcement.get("longitudinal_rows", [])` (list)
* `T = reinforcement.get("transverse_rows", [])` (list)

### 4.1. Total weight in tons

```text
w_total_ton = reinforcement.get("w_total_kgf", 0.0) / 1000.0
```

If `w_total_kgf` is missing or null, treat it as 0.0.

### 4.2. Longitudinal features

From `L`:

* `n_shapes_long`
  = number of **distinct** `"figura"` values (ignoring null/empty).

* `n_diams_long`
  = number of **distinct** `"calibre"` values (ignoring null/empty).

* `bar_count_long`
  = sum of `"cantidad"` across all longitudinal rows.
  Treat missing or null `"cantidad"` as 0.

### 4.3. Transverse features

From `T`:

* `n_shapes_trans`
  = number of **distinct** `"figura"` values.

* `n_diams_trans`
  = number of **distinct** `"calibre"` values.

* `bar_count_trans`
  = sum of `"cantidad"` across all transverse rows.

### 4.4. Edge cases

* If `L` is empty:

  * `n_shapes_long = 0`
  * `n_diams_long = 0`
  * `bar_count_long = 0`
* If `T` is empty:

  * `n_shapes_trans = 0`
  * `n_diams_trans = 0`
  * `bar_count_trans = 0`

All these values must be stored under `ci_features` in the enriched element.

---

## 5. Complexity Index formula

Use a deterministic, rule-based CI as a weighted combination of ratios against reference values.

### 5.1. Reference constants

At module level, define:

```python
REF_W_TON = 0.50          # reference total steel weight per element (tons)
REF_BAR_COUNT_LONG = 40   # reference longitudinal bar count
REF_BAR_COUNT_TRANS = 150 # reference transverse bar/stirrup count
REF_SHAPES = 2            # reference number of shapes
REF_DIAMS = 2             # reference number of bar diameters

W_W  = 0.30   # weight for total weight ratio
W_BL = 0.30   # weight for longitudinal bar count ratio
W_BT = 0.30   # weight for transverse bar count ratio
W_SH = 0.05   # weight for number of longitudinal shapes
W_D  = 0.05   # weight for number of longitudinal diameters
```

### 5.2. Ratios

Inside `compute_ci_for_element`, compute:

```text
r_w  = w_total_ton      / REF_W_TON          (if REF_W_TON > 0 else 0.0)
r_bl = bar_count_long   / REF_BAR_COUNT_LONG (if REF_BAR_COUNT_LONG > 0 else 0.0)
r_bt = bar_count_trans  / REF_BAR_COUNT_TRANS(if REF_BAR_COUNT_TRANS > 0 else 0.0)
r_sh = n_shapes_long    / REF_SHAPES         (if REF_SHAPES > 0 else 0.0)
r_d  = n_diams_long     / REF_DIAMS          (if REF_DIAMS > 0 else 0.0)
```

* If `w_total_ton == 0.0` (no reinforcement), you may set all ratios to 0.0.
* You may clamp ratios to a minimum of 0.0 (no negatives).

### 5.3. CI computation

Compute:

```text
ci_raw = W_W * r_w + W_BL * r_bl + W_BT * r_bt + W_SH * r_sh + W_D * r_d
```

Then:

* If `w_total_ton == 0.0`, set `ci = 0.0`.
* Otherwise, set `ci = ci_raw`.

You may optionally round `ci` to a reasonable number of decimals (e.g. 4).

---

## 6. Function behaviors

### 6.1. `compute_ci_for_element(element: dict) -> dict`

Requirements:

* Must **not** mutate the input `element` dict.
* Must safely handle missing keys: if `"reinforcement"` or subkeys are missing, treat them as empty / zero.
* Must compute `ci_features` and `ci` as described.
* Must return a **new dict** with:

  * All original top-level keys from `element`.
  * Plus:

    * `"ci": <float>`
    * `"ci_features": { ... }`

### 6.2. `add_ci_to_elements(data: dict) -> dict`

Requirements:

* `data` has keys `"project_id"` and `"elements"` (list).

* Must not mutate the input `data`.

* Must return a **new dict**:

  ```python
  {
      "project_id": <same as input>,
      "elements": [ enriched_element_1, enriched_element_2, ... ]
  }
  ```

* Each `enriched_element_*` is the result of `compute_ci_for_element(element)`.

---

## 7. CLI entrypoint

At the bottom of the module, implement:

```python
if __name__ == "__main__":
    ...
```

Behavior:

1. Use `argparse` to support:

   * `--input` (or `-i`): path to input JSON file. Default: `"elements.json"`.
   * `--output` (or `-o`): path to output JSON file. Default: `"elements_with_ci.json"`.

2. Steps:

   * Load the input JSON from the given path.
   * Call `add_ci_to_elements(data)`.
   * Write the resulting dict as JSON to the output path:

     * UTF-8 encoding.
     * `indent=2`.

3. On errors (file not found, invalid JSON), print a clear error message and exit with non-zero code.

---

## 8. Output of the coding run

When responding to this prompt, **only** output the complete Python module code (in a single file), with no surrounding explanations, no markdown fences, and no extra text.

The module must be self-contained and runnable as-is (assuming Python standard library is available).
