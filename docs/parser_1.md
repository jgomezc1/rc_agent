
1. Goal
Given an input Excel file with the same structure as reinforcement_solution.xlsx, you must:
Read the workbook and parse the relevant sheets.


For each unique element (identified by Piso + Elemento), build a canonical element object.


Aggregate longitudinal and transverse reinforcement data per element.


Serialize all elements into a single JSON file (elements.json).


At this stage, you are only responsible for this transformation. No scheduling, no CI calculation, no productivity models.

2. Input file structure (ProDet workbook)
The workbook contains exactly these sheets:
Resumen_Refuerzo


RefLong_PorElemento


RefLong_Total


RefTrans_PorElemento


RefTrans_Total


For this first step, you will use:
Resumen_Refuerzo (only to extract project_id).


RefLong_PorElemento (longitudinal reinforcement per element).


RefTrans_PorElemento (transverse reinforcement per element).


You may ignore the *_Total sheets for now.
2.1. Resumen_Refuerzo
Structure (as read by pandas with default options):
Column names:


CANTIDADES TOTALES POR NIVEL


Unnamed: 1


Unnamed: 2


Unnamed: 3


Row 0:


Cell (0,0) contains the project string, e.g.
 PROYECTO: Ejemplo Mokara


Rows 1–2:


Header row and units, e.g.:


Row 1: Nivel, Ref.Longitudinal, Ref.Transversal, Total por nivel


Row 2: -, tonf, tonf, tonf


Rows 3+:


Per-level quantities (you do not need them for this step).


Requirement:
Extract project_id by reading cell (0,0) and stripping the "PROYECTO:" prefix and whitespace.


Example:
 "PROYECTO: Ejemplo Mokara" → project_id = "Ejemplo Mokara".


2.2. RefLong_PorElemento – Longitudinal per element
Column names (as read by pandas):

 'DESPIECE DE REFUERZO LONGITUDINAL POR ELEMENTO',
'Unnamed: 1', 'Unnamed: 2', 'Unnamed: 3', 'Unnamed: 4',
'Unnamed: 5', 'Unnamed: 6', 'Unnamed: 7', 'Unnamed: 8',
'Unnamed: 9', 'Unnamed: 10', 'Unnamed: 11', 'Unnamed: 12'


Row 0: header row with human-readable names:


Col 0: "Piso"


Col 1: "Elemento"


Col 2: "Figura"


Col 3: "Calibre"


Col 4: "L_recta"


Col 5: "L_gancho_izq"


Col 6: "L_gancho_der"


Col 7: "L_total"


Col 8: "Cantidad"


Col 9: "Peso"


Col 10–12: legend for bar figure conventions.


Row 1: units row (to be ignored), e.g.:


"#", "Nombre", "-", "m", "m", "m", "m", "-", "Kgf", …


Rows 2+ are data rows with longitudinal bar records.


Interpretation of relevant columns:
Piso (string): floor identifier (e.g. "PISO 2").


Elemento (string): element identifier (e.g. "V-3").


Figura (string): bar shape symbol (e.g. "L", "|", "├", etc.).


Calibre (string): bar diameter (e.g. 5/8", 3/4").


L_recta (float, in meters).


L_gancho_izq (float or "-").


L_gancho_der (float or "-").


L_total (float, in meters).


Cantidad (integer or float but should be treated as integer).


Peso (float, in kgf) → this will be used to aggregate longitudinal weight.


You must:
Use row 0 as the true logical header.


Ignore row 1 (units) when building records.


Convert " - " or "-" entries for hook lengths to null (or Python None).


Represent each longitudinal row as a clean dictionary with normalized keys, e.g.:

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


2.3. RefTrans_PorElemento – Transverse per element
Column names (as read by pandas):

 'DESPIECE DE REFUERZO TRANSVERSAL POR ELEMENTO',
'Unnamed: 1', 'Unnamed: 2', 'Unnamed: 3',
'Unnamed: 4', 'Unnamed: 5', 'Unnamed: 6',
'Unnamed: 7', 'Unnamed: 8', 'Unnamed: 9', 'Unnamed: 10'


Row 0: header row:


Col 0: "Piso"


Col 1: "Elemento"


Col 2: "Figura"


Col 3: "Calibre"


Col 4: "Base"


Col 5: "Altura"


Col 6: "Cantidad"


Col 7: "Peso"


Col 8–10: legend for figure conventions ([], [) etc.


Row 1: units row (to be ignored):


"-", "Nombre", "-", "#", "m", "m", "-", "Kgf", …


Rows 2+ are data rows with transverse bar records.


Interpretation of relevant columns:
Piso (string).


Elemento (string).


Figura (string, e.g. "[]", "[").


Calibre (string).


Base (float, in meters, may be "-").


Altura (float, in meters).


Cantidad (integer).


Peso (float, in kgf) → used to aggregate transverse weight.


You must:
Use row 0 as logical header.


Ignore row 1 (units).


Convert " - " or "-" for Base to null.


Represent each transverse row as a dictionary, e.g.:

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



3. Canonical JSON output schema
The script must output one JSON file with the following top-level structure:
{
  "project_id": "Ejemplo Mokara",
  "elements": [ /* list of element objects */ ]
}

3.1. Element object schema
Each element in "elements" corresponds to a unique (Piso, Elemento) pair present in the ProDet data and must have this structure:
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
    "longitudinal_rows": [ /* list of longitudinal row dicts */ ],
    "transverse_rows":   [ /* list of transverse row dicts */ ]
  }
}

Notes and requirements:
project_id


Same for all elements, taken from Resumen_Refuerzo.


floor_id


Equal to the Piso string from the ProDet sheets (e.g. "PISO 2").


zone_id


For now, set to null (or omit) — zoning will be defined later.


element_id


Equal to the Elemento string (e.g. "V-3").


element_type


Implement a simple helper infer_element_type(element_name: str) -> str.


For this first iteration:


If the element name starts with "V" or "V-", set "beam".


Otherwise, set "unknown".


This is a placeholder; the logic will be refined later.


geometry


For now, set to null (or omit). Geometry will be added from other sources later.


reinforcement


w_long_kgf: sum of peso_kgf from all longitudinal rows for this element.


w_trans_kgf: sum of peso_kgf from all transverse rows for this element.


w_total_kgf: w_long_kgf + w_trans_kgf.


longitudinal_rows: list of cleaned dictionaries as described in §2.2, but only those rows whose piso and elemento match this element.


transverse_rows: list of cleaned dictionaries as described in §2.3, similarly filtered.


All numeric values in JSON should be standard JSON numbers (not strings). null should be used where appropriate.

4. Script requirements
Write a Python script with the following characteristics:
Accepts an input .xlsx file path, e.g. via:


a command-line argument, or


a hard-coded constant for now (you can assume reinforcement_solution.xlsx in the current directory).


Produces an output file named elements.json in the current directory (or takes an optional output path argument).


Uses pandas (or another standard library for reading Excel) for parsing the workbook.


Handles:


skipping the units rows (row index 1 in RefLong_PorElemento and RefTrans_PorElemento),


trimming whitespace from strings,


converting "-" and empty strings to null in numeric fields.


Ensures that each (Piso, Elemento) pair appears exactly once in "elements" and aggregates all corresponding reinforcement rows.


You should also implement minimal validation:
If an element appears in RefTrans_PorElemento but not in RefLong_PorElemento (or vice versa), still create an element object with whichever data is available and use 0.0 for missing weights.


If a sheet is missing, raise a clear exception.



5. Output of the coding run
When responding to this prompt, only output the complete Python script code (in a single file), with no surrounding explanations, no markdown fences, and no additional comments beyond those inside the code if really necessary.
The script must be self-contained and runnable as-is (assuming the necessary Python dependencies are installed).
