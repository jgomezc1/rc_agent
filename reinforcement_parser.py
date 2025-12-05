#!/usr/bin/env python3
"""
Reinforcement Parser - Converts ProDet reinforcement .xlsx files to canonical JSON.

This script reads a ProDet reinforcement solution Excel file and transforms it into
a structured JSON representation per element, suitable for downstream scheduling
and analytics.

Usage:
    python reinforcement_parser.py [input_file] [output_file]

    Defaults:
        input_file:  data/reinforcement_solution.xlsx
        output_file: data/elements.json
"""

import sys
import json
from typing import Dict, List, Any, Optional
from pathlib import Path

import pandas as pd


# =============================================================================
# Helper Functions
# =============================================================================

def infer_element_type(element_name: str) -> str:
    """
    Infer the element type from its name.

    For this first iteration:
    - If the element name starts with "V" or "V-", return "beam".
    - Otherwise, return "unknown".

    This logic will be refined later.
    """
    if element_name is None:
        return "unknown"

    name = str(element_name).strip().upper()

    if name.startswith("V-") or name == "V" or (name.startswith("V") and len(name) > 1 and not name[1].isalpha()):
        return "beam"

    return "unknown"


def clean_value(value: Any) -> Any:
    """
    Clean a cell value:
    - Convert "-", " - ", empty strings, and NaN to None
    - Strip whitespace from strings
    - Return numbers as-is
    """
    if pd.isna(value):
        return None

    if isinstance(value, str):
        stripped = value.strip()
        if stripped in ["-", "", " - "]:
            return None
        return stripped

    return value


def clean_numeric(value: Any) -> Optional[float]:
    """
    Clean and convert a value to float.
    Returns None for invalid/missing values.
    """
    cleaned = clean_value(value)
    if cleaned is None:
        return None

    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def clean_integer(value: Any) -> int:
    """
    Clean and convert a value to integer.
    Returns 0 for invalid/missing values.
    """
    cleaned = clean_value(value)
    if cleaned is None:
        return 0

    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return 0


# =============================================================================
# Sheet Parsers
# =============================================================================

def extract_project_id(xlsx: pd.ExcelFile) -> str:
    """
    Extract project_id from the Resumen_Refuerzo sheet.

    The sheet structure is:
    - Row 0: Title ("CANTIDADES TOTALES POR NIVEL")
    - Row 1: Project name ("PROYECTO: Ejemplo Mokara")
    - Row 2: Column headers
    - Row 3: Units
    - Row 4+: Data
    """
    sheet_name = "Resumen_Refuerzo"

    if sheet_name not in xlsx.sheet_names:
        raise ValueError(f"Required sheet '{sheet_name}' not found in workbook")

    # Read first few rows without header to get raw cell values
    df = pd.read_excel(xlsx, sheet_name=sheet_name, header=None, nrows=3)

    # Project name is in row 1, column 0
    raw_value = df.iloc[1, 0]

    if pd.isna(raw_value):
        return "Unknown Project"

    project_str = str(raw_value).strip()

    # Strip "PROYECTO:" prefix if present
    if project_str.upper().startswith("PROYECTO:"):
        project_str = project_str[len("PROYECTO:"):].strip()

    return project_str if project_str else "Unknown Project"


def parse_longitudinal_sheet(xlsx: pd.ExcelFile) -> List[Dict[str, Any]]:
    """
    Parse the RefLong_PorElemento sheet.

    Sheet structure:
    - Row 0: Title ("DESPIECE DE REFUERZO LONGITUDINAL POR ELEMENTO")
    - Row 1: Column headers (Piso, Elemento, Figura, etc.)
    - Row 2: Units (#, Nombre, -, #, m, m, m, m, -, Kgf)
    - Row 3+: Data rows

    Returns a list of cleaned longitudinal bar dictionaries.
    """
    sheet_name = "RefLong_PorElemento"

    if sheet_name not in xlsx.sheet_names:
        raise ValueError(f"Required sheet '{sheet_name}' not found in workbook")

    # Read with header=None to handle the unusual column names
    df = pd.read_excel(xlsx, sheet_name=sheet_name, header=None)

    rows = []

    # Iterate from row 3 onwards (skip title, header, and units rows)
    for idx in range(3, len(df)):
        row = df.iloc[idx]

        # Skip empty rows
        piso = clean_value(row.iloc[0])
        elemento = clean_value(row.iloc[1])

        if piso is None or elemento is None:
            continue

        # Skip unit/header-like rows that might have slipped through
        if str(piso).strip() in ["#", "-", "Piso"]:
            continue

        record = {
            "piso": piso,
            "elemento": elemento,
            "figura": clean_value(row.iloc[2]),
            "calibre": clean_value(row.iloc[3]),
            "l_recta_m": clean_numeric(row.iloc[4]),
            "l_gancho_izq_m": clean_numeric(row.iloc[5]),
            "l_gancho_der_m": clean_numeric(row.iloc[6]),
            "l_total_m": clean_numeric(row.iloc[7]),
            "cantidad": clean_integer(row.iloc[8]),
            "peso_kgf": clean_numeric(row.iloc[9]) or 0.0
        }

        rows.append(record)

    return rows


def parse_transverse_sheet(xlsx: pd.ExcelFile) -> List[Dict[str, Any]]:
    """
    Parse the RefTrans_PorElemento sheet.

    Sheet structure:
    - Row 0: Title ("DESPIECE DE REFUERZO TRANSVERSAL POR ELEMENTO")
    - Row 1: Column headers (Piso, Elemento, Figura, Calibre, Base, Altura, Cantidad, Peso)
    - Row 2: Units (-, Nombre, -, #, m, m, -, Kgf)
    - Row 3+: Data rows

    Returns a list of cleaned transverse bar (stirrup) dictionaries.
    """
    sheet_name = "RefTrans_PorElemento"

    if sheet_name not in xlsx.sheet_names:
        raise ValueError(f"Required sheet '{sheet_name}' not found in workbook")

    # Read with header=None to handle the unusual column names
    df = pd.read_excel(xlsx, sheet_name=sheet_name, header=None)

    rows = []

    # Iterate from row 3 onwards (skip title, header, and units rows)
    for idx in range(3, len(df)):
        row = df.iloc[idx]

        # Skip empty rows
        piso = clean_value(row.iloc[0])
        elemento = clean_value(row.iloc[1])

        if piso is None or elemento is None:
            continue

        # Skip unit/header-like rows that might have slipped through
        if str(piso).strip() in ["-", "#", "Piso"]:
            continue

        record = {
            "piso": piso,
            "elemento": elemento,
            "figura": clean_value(row.iloc[2]),
            "calibre": clean_value(row.iloc[3]),
            "base_m": clean_numeric(row.iloc[4]),
            "altura_m": clean_numeric(row.iloc[5]),
            "cantidad": clean_integer(row.iloc[6]),
            "peso_kgf": clean_numeric(row.iloc[7]) or 0.0
        }

        rows.append(record)

    return rows


# =============================================================================
# Element Builder
# =============================================================================

def build_elements(
    project_id: str,
    longitudinal_rows: List[Dict[str, Any]],
    transverse_rows: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Build canonical element objects from parsed reinforcement data.

    Each element is identified by a unique (piso, elemento) pair.
    """
    # Collect all unique (piso, elemento) pairs
    element_keys = set()

    for row in longitudinal_rows:
        key = (row["piso"], row["elemento"])
        element_keys.add(key)

    for row in transverse_rows:
        key = (row["piso"], row["elemento"])
        element_keys.add(key)

    # Group rows by element key
    long_by_element: Dict[tuple, List[Dict]] = {}
    trans_by_element: Dict[tuple, List[Dict]] = {}

    for row in longitudinal_rows:
        key = (row["piso"], row["elemento"])
        if key not in long_by_element:
            long_by_element[key] = []
        long_by_element[key].append(row)

    for row in transverse_rows:
        key = (row["piso"], row["elemento"])
        if key not in trans_by_element:
            trans_by_element[key] = []
        trans_by_element[key].append(row)

    # Build element objects
    elements = []

    for (piso, elemento) in sorted(element_keys):
        long_rows = long_by_element.get((piso, elemento), [])
        trans_rows = trans_by_element.get((piso, elemento), [])

        # Calculate weight totals
        w_long_kgf = sum(row["peso_kgf"] for row in long_rows)
        w_trans_kgf = sum(row["peso_kgf"] for row in trans_rows)
        w_total_kgf = w_long_kgf + w_trans_kgf

        element = {
            "project_id": project_id,
            "floor_id": piso,
            "zone_id": None,
            "element_id": elemento,
            "element_type": infer_element_type(elemento),
            "geometry": None,
            "reinforcement": {
                "w_long_kgf": round(w_long_kgf, 2),
                "w_trans_kgf": round(w_trans_kgf, 2),
                "w_total_kgf": round(w_total_kgf, 2),
                "longitudinal_rows": long_rows,
                "transverse_rows": trans_rows
            }
        }

        elements.append(element)

    return elements


# =============================================================================
# Main Parser Function
# =============================================================================

def parse_reinforcement_file(input_path: str) -> Dict[str, Any]:
    """
    Parse a ProDet reinforcement Excel file and return canonical JSON structure.

    Args:
        input_path: Path to the input .xlsx file

    Returns:
        Dictionary with project_id and elements list
    """
    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if not input_path.suffix.lower() in [".xlsx", ".xls"]:
        raise ValueError(f"Input file must be an Excel file (.xlsx or .xls): {input_path}")

    # Load the workbook
    xlsx = pd.ExcelFile(input_path)

    # Verify required sheets exist
    required_sheets = ["Resumen_Refuerzo", "RefLong_PorElemento", "RefTrans_PorElemento"]
    missing_sheets = [s for s in required_sheets if s not in xlsx.sheet_names]

    if missing_sheets:
        raise ValueError(f"Missing required sheets: {missing_sheets}. "
                        f"Found sheets: {xlsx.sheet_names}")

    # Extract project ID
    project_id = extract_project_id(xlsx)

    # Parse reinforcement sheets
    longitudinal_rows = parse_longitudinal_sheet(xlsx)
    transverse_rows = parse_transverse_sheet(xlsx)

    # Build element objects
    elements = build_elements(project_id, longitudinal_rows, transverse_rows)

    # Build output structure
    output = {
        "project_id": project_id,
        "elements": elements
    }

    return output


def write_json_output(data: Dict[str, Any], output_path: str) -> None:
    """
    Write the parsed data to a JSON file.
    """
    output_path = Path(output_path)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point for the script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse ProDet reinforcement Excel files to canonical JSON."
    )
    parser.add_argument(
        "-i", "--input",
        default="data/reinforcement_solution.xlsx",
        help="Path to input Excel file (default: data/reinforcement_solution.xlsx)"
    )
    parser.add_argument(
        "-o", "--output",
        default="data/elements.json",
        help="Path to output JSON file (default: data/elements.json)"
    )

    args = parser.parse_args()
    input_path = args.input
    output_path = args.output

    print(f"Reinforcement Parser")
    print(f"=" * 40)
    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    print()

    try:
        # Parse the file
        print("Parsing reinforcement file...")
        data = parse_reinforcement_file(input_path)

        # Write output
        print("Writing JSON output...")
        write_json_output(data, output_path)

        # Summary
        print()
        print(f"Successfully parsed reinforcement data:")
        print(f"  Project ID: {data['project_id']}")
        print(f"  Total elements: {len(data['elements'])}")

        # Count by floor
        floors = {}
        for elem in data["elements"]:
            floor = elem["floor_id"]
            floors[floor] = floors.get(floor, 0) + 1

        print(f"  Floors: {len(floors)}")
        for floor in sorted(floors.keys(), key=lambda x: (int(''.join(filter(str.isdigit, x)) or 0), x)):
            print(f"    {floor}: {floors[floor]} elements")

        # Count by element type
        types = {}
        for elem in data["elements"]:
            etype = elem["element_type"]
            types[etype] = types.get(etype, 0) + 1

        print(f"  Element types:")
        for etype, count in sorted(types.items()):
            print(f"    {etype}: {count}")

        print()
        print(f"Output written to: {output_path}")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
