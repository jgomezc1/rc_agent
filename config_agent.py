#!/usr/bin/env python3
"""
Config Agent — NL ↔ project.config Translation

This module implements an AI agent that reads and modifies ProDet project.config
files using natural language. It provides two tools:

  - load_config_summary: reads a project.config and returns a curated summary
    of the ~30 engineering-relevant "design decision" parameters, excluding the
    bulky NSR-10 lookup tables that never change between configurations.

  - update_config: applies dot-path keyed changes to an existing config file,
    preserving all lookup tables and standard library data.

Usage:
    from config_agent import ConfigAgent

    agent = ConfigAgent()
    response = agent.run("Describe the mokara config")
"""

import json
import os
import shutil
import logging
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

CALIBRE_NAMES = {
    0: '1/4"', 1: '3/8"', 2: '1/2"', 3: '5/8"',
    4: '3/4"', 5: '7/8"', 6: '1"', 7: '1-1/4"',
}

CALIBRE_FROM_NAME = {v: k for k, v in CALIBRE_NAMES.items()}

# long_homog is an integer enum, NOT a length in meters
_LONG_HOMOG_MAP = {0: "10cm multiples", 1: "50cm multiples", 2: "100cm multiples"}

# Keys inside norma/param_despiece that hold bulky lookup tables (never vary)
_LOOKUP_TABLE_KEYS = {"lon_tras", "Ld", "Ldh_concreto", "long_ganchos"}

# Element types that can appear in a config
_ELEMENT_TYPES = ("vigas", "nervios", "columnas")


# =============================================================================
# Helpers
# =============================================================================

def _get_nested(obj: dict, dot_path: str) -> Any:
    """Read a value from a nested dict using a dot-separated path.

    Example: _get_nested(config, "vigas.param_despiece.calibre_max")
    """
    keys = dot_path.split(".")
    current = obj
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            raise KeyError(f"Path '{dot_path}' not found (failed at '{key}')")
    return current


def _set_nested(obj: dict, dot_path: str, value: Any) -> None:
    """Set a value in a nested dict using a dot-separated path.

    Example: _set_nested(config, "vigas.param_despiece.calibre_max", 7)
    """
    keys = dot_path.split(".")
    current = obj
    for key in keys[:-1]:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            raise KeyError(f"Path '{dot_path}' not found (failed at '{key}')")
    if keys[-1] not in current:
        raise KeyError(f"Path '{dot_path}' not found (key '{keys[-1]}' does not exist)")
    current[keys[-1]] = value


def _calibre_name(idx) -> str:
    """Convert a calibre index to its human-readable name."""
    if isinstance(idx, int) and idx in CALIBRE_NAMES:
        return CALIBRE_NAMES[idx]
    return str(idx)


def _maybe_convert_calibre(value: Any, field_name: str) -> Any:
    """If a value looks like a calibre name string and the field is a calibre field,
    convert it to the corresponding integer index."""
    calibre_fields = {
        "calibre_max", "calibre_min", "calibre_max_on_error",
        "calibre_est_int_min", "calibre_est_int_max",
        "calibre_est_ext_min", "calibre_est_ext_max",
        "cal_max_pf", "calibre", "calibre_ref_constr",
        "cal_bast",
    }
    # Extract the last segment of the dot path
    leaf = field_name.split(".")[-1] if "." in field_name else field_name
    if leaf in calibre_fields and isinstance(value, str) and value in CALIBRE_FROM_NAME:
        return CALIBRE_FROM_NAME[value]
    return value


def _resolve_config_path(config_path: str) -> str:
    """Resolve a config path — checks projects/ first, then PRODET_PROJECTS env."""
    if os.path.isfile(config_path):
        return config_path

    from paths import RC_AGENT_PROJECTS, normalize_path

    # Primary: projects/<name>/project.config
    candidate = os.path.join(RC_AGENT_PROJECTS, config_path, "project.config")
    if os.path.isfile(candidate):
        return candidate

    # Fallback: PRODET_PROJECTS env var (for override scenarios)
    prodet_projects = os.environ.get("PRODET_PROJECTS", "")
    if prodet_projects:
        prodet_projects = normalize_path(prodet_projects)
        candidate = os.path.join(prodet_projects, config_path, "project.config")
        if os.path.isfile(candidate):
            return candidate

    # Try as relative path
    abs_path = os.path.join(os.getcwd(), config_path)
    if os.path.isfile(abs_path):
        return abs_path

    return config_path


def _summarize_element(config: dict, element_key: str) -> Optional[dict]:
    """Extract a curated summary for one element type (vigas/nervios/columnas)."""
    elem = config.get(element_key)
    if not elem or not isinstance(elem, dict):
        return None

    summary = {}

    # --- Materials ---
    mat = elem.get("materiales", {})
    fc_data = mat.get("fc", {})
    fc_per_floor = bool(fc_data.get("filtro_por_nivel", 0))
    # Check if all per-floor values are the same
    por_nivel = fc_data.get("por_nivel", {})
    fc_values = set()
    if isinstance(por_nivel, list):
        for entry in por_nivel:
            if isinstance(entry, dict):
                fc_values.update(entry.values())
    elif isinstance(por_nivel, dict):
        fc_values = set(por_nivel.values())

    summary["materials"] = {
        "fy": mat.get("fy"),
        "fc_default": fc_data.get("default") if isinstance(fc_data, dict) else fc_data,
        "fc_per_floor": fc_per_floor,
        "E": mat.get("E"),
    }
    if fc_per_floor and len(fc_values) > 1:
        summary["materials"]["fc_distinct_values"] = sorted(fc_values)

    # --- Covers (from norma) ---
    norma = elem.get("norma", {})
    summary["covers"] = {
        "rec_traccion": norma.get("rec_traccion"),
        "rec_compresion": norma.get("rec_compresion"),
        "rec_lat": norma.get("rec_lat"),
        "rec_ap": norma.get("rec_ap"),
        "centroide_as": norma.get("centroide_as"),
    }

    # --- Seismic demand (from norma, vigas only) ---
    if "demanda" in norma:
        summary["seismic_demand"] = norma["demanda"]

    # --- Rebar range and detailing (from param_despiece) ---
    pd = elem.get("param_despiece", {})
    if pd:
        cal_min = pd.get("calibre_min")
        cal_max = pd.get("calibre_max")
        summary["rebar_range"] = {
            "min": _calibre_name(cal_min),
            "max": _calibre_name(cal_max),
            "min_idx": cal_min,
            "max_idx": cal_max,
        }

        barra_alta = pd.get("barra_alta", {})
        ref_pf = pd.get("ref_primera_fila", {})
        forzar = pd.get("forzar_ref_ppal", {})
        forzar_default = forzar.get("default", {}) if isinstance(forzar, dict) else {}

        summary["detailing"] = {
            "max_bar_length_m": pd.get("maxva"),
            "cutting_length_rounding": (
                {"value": lh, "description": _LONG_HOMOG_MAP.get(lh, f"unknown ({lh})")}
                if (lh := pd.get("long_homog")) is not None else None
            ),
            "max_caliber_jump": pd.get("dif_max_cal"),
            "top_bar_penalty": {
                "active": bool(barra_alta.get("castigo", 0)),
                "factor": barra_alta.get("factor"),
            },
            "moment_redistribution": {
                "active": bool(pd.get("redi_mom", False)),
                "max_pct": round((pd.get("val_redi", 0.2)) * 100) if pd.get("val_redi") else 20,
            },
            "two_line_principal": bool(pd.get("ppal_2_lineas", False)),
            "headed_bars": bool(pd.get("cabezas_ganchos", False)),
            "always_splice": bool(pd.get("empalmar_siempre", False)),
            "splice_zones": pd.get("zonas_empalme"),
            "first_row": {
                "option": ref_pf.get("opcion"),
                "max_calibre": _calibre_name(ref_pf.get("cal_max_pf")),
            } if ref_pf else None,
            "forced_principal": {
                "active": bool(forzar_default.get("valor", False)),
                "count": forzar_default.get("cantidad"),
                "calibre": _calibre_name(forzar_default.get("calibre")),
            } if forzar_default else None,
            "splice_factor_CRA": pd.get("factor_tras_cra"),
        }

    # --- Stirrups ---
    est = elem.get("estribos", {})
    if est:
        summary["stirrups"] = {
            "min_count": est.get("n_estribos_min"),
            "min_branches": est.get("ramas_minimas_globales"),
            "calibre_range_interior": [
                _calibre_name(est.get("calibre_est_int_min")),
                _calibre_name(est.get("calibre_est_int_max")),
            ],
            "calibre_range_exterior": [
                _calibre_name(est.get("calibre_est_ext_min")),
                _calibre_name(est.get("calibre_est_ext_max")),
            ],
            "min_spacing_cm": est.get("sep_min"),
        }

    return summary


def _extract_floor_names(config: dict, config_dir: str = "") -> List[str]:
    """Extract the ordered list of floor names from a parsed config dict.

    Searches vigas.param_despiece.forzar_ref_ppal.por_nivel first (most
    reliable source), then falls back to nervios, then columnas.
    If por_nivel is empty in all element types (no per-level overrides),
    falls back to project.geom floorsOrdered (requires config_dir).
    Returns floor names in top-to-bottom order.
    """
    for element_key in ("vigas", "nervios", "columnas"):
        elem = config.get(element_key, {})
        por_nivel = (
            elem
            .get("param_despiece", {})
            .get("forzar_ref_ppal", {})
            .get("por_nivel", {})
        )
        if isinstance(por_nivel, dict) and por_nivel:
            return list(por_nivel.keys())

    # Fallback: read floor IDs from project.geom
    if config_dir:
        geom_path = os.path.join(config_dir, "project.geom")
        if os.path.isfile(geom_path):
            try:
                with open(geom_path, "r", encoding="utf-8") as f:
                    geom = json.load(f)
                floors_ordered = geom.get("floorsOrdered", [])
                if floors_ordered:
                    return [
                        entry[0] if isinstance(entry, list) else entry
                        for entry in floors_ordered
                    ]
            except Exception as e:
                logger.warning(f"Could not read floorsOrdered from project.geom: {e}")

    return []


def _build_floor_id_map(config_dir: str, display_names: List[str]) -> Dict[str, str]:
    """Build a mapping from por_nivel display names to project.geom internal IDs.

    Uses positional correspondence: por_nivel keys and floorsOrdered in
    project.geom are both top-to-bottom ordered and have the same length.

    Returns {display_name: internal_id}. Falls back to identity mapping
    (display_name → display_name) if project.geom is unavailable or the
    lists don't match in length.
    """
    geom_path = os.path.join(config_dir, "project.geom")
    if not os.path.isfile(geom_path):
        return {n: n for n in display_names}

    try:
        with open(geom_path, "r", encoding="utf-8") as f:
            geom = json.load(f)
        floors_ordered = geom.get("floorsOrdered", [])
        if len(floors_ordered) != len(display_names):
            logger.warning(
                f"floorsOrdered ({len(floors_ordered)}) and por_nivel "
                f"({len(display_names)}) have different lengths — "
                f"falling back to identity mapping"
            )
            return {n: n for n in display_names}

        return {
            display: entry[0] if isinstance(entry, list) else entry
            for display, entry in zip(display_names, floors_ordered)
        }
    except Exception as e:
        logger.warning(f"Could not load project.geom for floor ID mapping: {e}")
        return {n: n for n in display_names}


# =============================================================================
# LangChain Tools
# =============================================================================

@tool
def load_config_summary(config_path: str) -> Dict[str, Any]:
    """
    Read a ProDet project.config file and return a curated summary of
    engineering-relevant parameters.

    Extracts the ~30 "design decision" parameters that actually vary between
    configurations, organized by element type. Excludes the bulky NSR-10
    lookup tables (lon_tras, Ld, Ldh_concreto, long_ganchos), the planos
    drawing config, and the calibres/materiales standard libraries.

    Args:
        config_path: Path to the project.config file, OR just the project
                     name (e.g. "mokara") which resolves to
                     projects/mokara/project.config.

    Returns:
        Dictionary with project_name, seismic_demand, postensado flag, and
        per-element-type summaries (materials, covers, rebar_range, detailing,
        stirrups).
    """
    try:
        resolved = _resolve_config_path(config_path)
        if not os.path.isfile(resolved):
            return {"error": f"Config file not found: {config_path} (tried {resolved})"}

        with open(resolved, "r", encoding="utf-8") as f:
            config = json.load(f)

        result = {
            "config_path": resolved,
            "project_name": config.get("nombre_inf", config.get("name", "Unknown")),
            "config_name": config.get("name"),
            "postensado": bool(config.get("postensado", False)),
            "modo": config.get("modo"),
        }

        # Extract seismic demand from vigas.norma.demanda (primary location)
        vigas_norma = config.get("vigas", {}).get("norma", {})
        result["seismic_demand"] = vigas_norma.get("demanda", "Unknown")

        # Per-element summaries
        result["element_types"] = {}
        for etype in _ELEMENT_TYPES:
            summary = _summarize_element(config, etype)
            if summary:
                result["element_types"][etype] = summary

        # Floor names (ordered as stored in config — top-to-bottom)
        result["floors"] = _extract_floor_names(config, os.path.dirname(resolved))

        # Floor groups (grupos_niveles)
        raw_groups = config.get("grupos_niveles", [])
        if raw_groups:
            result["floor_groups"] = [
                {
                    "id": g.get("id", ""),
                    "floors": g.get("niveles", []),
                    "mode": g.get("modoAgrupacion", "envolvente"),
                }
                for g in raw_groups
            ]
        else:
            result["floor_groups"] = []
            result["floor_groups_note"] = (
                "No floor grouping defined. Use set_floor_groups to create "
                "groups of geometrically identical floors."
            )

        return result

    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in config file: {e}"}
    except Exception as e:
        logger.error(f"Error loading config summary: {e}")
        return {"error": str(e)}


@tool
def update_config(
    config_path: str,
    changes_json: str,
    output_path: str = "",
) -> Dict[str, Any]:
    """
    Apply changes to a ProDet project.config file using dot-path keys.

    Reads the existing config as a template, validates that each dot-path
    resolves to an existing key, applies the changes, and writes the result.
    Lookup tables and standard libraries are preserved verbatim.

    If a change value for a calibre field is a string like '3/4"', it is
    auto-converted to the corresponding integer index (4).

    When the output directory differs from the source directory, the three
    immutable ProDet project files (project.cargas, project.geom,
    project.prodes) are automatically copied from the source folder into
    the new folder so that the new project is complete and runnable by ProDet.

    Args:
        config_path: Path to the existing project.config (template), OR just
                     the project name (e.g. "mokara").
        changes_json: JSON string with dot-path keys mapping to new values.
                      Example: {"vigas.param_despiece.calibre_max": 7,
                                "vigas.materiales.fc.default": 280}
        output_path: Where to save the modified config. If empty, overwrites
                     the original config_path. Can be a project name (saves
                     to projects/<name>/project.config) or a full path.
                     IMPORTANT: Always use a NEW project name to avoid
                     overwriting the seed config.

    Returns:
        Dictionary with success flag, changes applied, output path, and
        list of copied companion files (if any).
    """
    try:
        resolved_input = _resolve_config_path(config_path)
        if not os.path.isfile(resolved_input):
            return {"error": f"Config file not found: {config_path} (tried {resolved_input})"}

        with open(resolved_input, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Parse changes
        try:
            changes = json.loads(changes_json)
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON in changes_json: {e}"}

        if not isinstance(changes, dict):
            return {"error": "changes_json must be a JSON object (dict)"}

        # Validate and apply changes
        applied = []
        errors = []
        for dot_path, new_value in changes.items():
            try:
                old_value = _get_nested(config, dot_path)
                # Auto-convert calibre name strings to indices
                new_value = _maybe_convert_calibre(new_value, dot_path)
                _set_nested(config, dot_path, new_value)
                applied.append({
                    "path": dot_path,
                    "old": old_value,
                    "new": new_value,
                })
            except KeyError as e:
                errors.append({"path": dot_path, "error": str(e)})

        if errors and not applied:
            return {"error": "No changes applied — all paths invalid", "invalid_paths": errors}

        # Post-apply: ensure dependent parameters are consistent.
        for etype in ("vigas", "nervios", "columnas"):
            esection = config.get(etype, {})

            # Guard 1: lim_max_barras_capa=true requires max_barras_capa dict.
            pd = esection.get("param_despiece", {})
            if pd.get("lim_max_barras_capa") and "max_barras_capa" not in pd:
                sections = pd.get("forzar_ref_ppal", {}).get("por_seccion", {})
                widths = set()
                for key in sections:
                    widths.add(key.split(",")[0])
                if widths:
                    mbc = {w: 1 if float(w) <= 0.2 else 2 for w in sorted(widths)}
                    config[etype]["param_despiece"]["max_barras_capa"] = mbc
                    applied.append({
                        "path": f"{etype}.param_despiece.max_barras_capa",
                        "old": None,
                        "new": mbc,
                        "note": "auto-generated (required when lim_max_barras_capa=true)",
                    })

            # Guard 2: filtro_por_nivel=1 with empty por_nivel → reset to 0.
            # Applies to materiales.fc and estribos.est_min (any section with
            # this pattern). ProDet crashes with KeyError if por_nivel is empty
            # but the filter flag tells it to use per-level values.
            for subpath, subsection in [
                ("materiales.fc", esection.get("materiales", {}).get("fc", {})),
                ("estribos.est_min", esection.get("estribos", {}).get("est_min", {})),
            ]:
                if not isinstance(subsection, dict):
                    continue
                filtro = subsection.get("filtro_por_nivel")
                por_nivel = subsection.get("por_nivel", {})
                if filtro and (not por_nivel or not isinstance(por_nivel, dict)
                               or len(por_nivel) == 0):
                    subsection["filtro_por_nivel"] = 0
                    applied.append({
                        "path": f"{etype}.{subpath}.filtro_por_nivel",
                        "old": filtro,
                        "new": 0,
                        "note": "auto-reset (por_nivel is empty, filtro_por_nivel=1 would crash ProDet)",
                    })

        # Determine output path
        if output_path:
            resolved_output = _resolve_config_path(output_path)
            # If it resolved to the same as input and doesn't look like a file,
            # treat as a new project name → projects/<name>/project.config
            if resolved_output == output_path and not output_path.endswith(".config"):
                from paths import project_dir
                out_dir = project_dir(output_path)
                resolved_output = os.path.join(out_dir, "project.config")
        else:
            resolved_output = resolved_input

        # Write
        with open(resolved_output, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        # Copy immutable companion files if output is in a different directory
        _COMPANION_FILES = ["project.cargas", "project.geom", "project.prodes"]
        copied_files = []
        src_dir = os.path.dirname(resolved_input)
        out_dir = os.path.dirname(resolved_output)
        if os.path.normpath(src_dir) != os.path.normpath(out_dir):
            for fname in _COMPANION_FILES:
                src_file = os.path.join(src_dir, fname)
                dst_file = os.path.join(out_dir, fname)
                if os.path.isfile(src_file) and not os.path.isfile(dst_file):
                    shutil.copy2(src_file, dst_file)
                    copied_files.append(fname)

        result = {
            "success": True,
            "changes_applied": applied,
            "output_path": resolved_output,
            "source_path": resolved_input,
        }
        if copied_files:
            result["copied_companion_files"] = copied_files
        if errors:
            result["warnings"] = errors
            result["note"] = f"{len(applied)} changes applied, {len(errors)} paths invalid"

        return result

    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return {"error": str(e)}


@tool
def set_floor_groups(
    config_path: str,
    groups_json: str,
    identical_range_start: str,
    identical_range_end: str,
    output_path: str = "",
) -> Dict[str, Any]:
    """
    Create or replace floor-level groupings (grupos_niveles) in a project.config.

    IMPORTANT: Before calling this tool you MUST ask the user which floors are
    geometrically identical. Pass their answer as identical_range_start/end.

    Args:
        config_path: Project name or path to project.config (e.g. "supernovaA").
        groups_json: JSON list of groups, each a list of floor names.
                     Example: '[["05_Niv3","06_Niv4"],["07_Niv5","08_Niv6"]]'
        identical_range_start: First floor in the user-declared identical range
                               (e.g. "05_Niv3"). This is the topmost floor in
                               config order that the user confirmed as identical.
        identical_range_end: Last floor in the user-declared identical range
                             (e.g. "08_Niv6"). This is the bottommost floor.
        output_path: New project name for output (e.g. "supernovaA_grouped").
                     If empty, overwrites the source config. IMPORTANT: always
                     use a new name to protect the seed config.

    Returns:
        Dictionary with success flag, generated grupos_niveles, validation
        details, and output path.
    """
    try:
        resolved_input = _resolve_config_path(config_path)
        if not os.path.isfile(resolved_input):
            return {"error": f"Config file not found: {config_path} (tried {resolved_input})"}

        with open(resolved_input, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Parse groups
        try:
            groups = json.loads(groups_json)
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON in groups_json: {e}"}

        if not isinstance(groups, list) or not all(isinstance(g, list) for g in groups):
            return {"error": "groups_json must be a JSON list of lists (e.g. [[\"A\",\"B\"],[\"C\",\"D\"]])"}

        # Extract ordered floor names from config (falls back to project.geom)
        src_dir = os.path.dirname(resolved_input)
        all_floors = _extract_floor_names(config, src_dir)
        if not all_floors:
            return {"error": "Could not extract floor names from config or project.geom."}

        # ── Validation layer 1: All floor names exist ──
        all_floor_set = set(all_floors)
        unknown = []
        for gi, group in enumerate(groups):
            for fname in group:
                if fname not in all_floor_set:
                    unknown.append({"group": gi + 1, "floor": fname})
        if unknown:
            return {
                "error": "Unknown floor names — not found in config",
                "unknown_floors": unknown,
                "available_floors": all_floors,
            }

        # Validate range endpoints exist
        if identical_range_start not in all_floor_set:
            return {"error": f"identical_range_start '{identical_range_start}' not found in config floors", "available_floors": all_floors}
        if identical_range_end not in all_floor_set:
            return {"error": f"identical_range_end '{identical_range_end}' not found in config floors", "available_floors": all_floors}

        # Determine the identical range as a slice of all_floors
        idx_start = all_floors.index(identical_range_start)
        idx_end = all_floors.index(identical_range_end)
        # Ensure start comes before or at end in list order
        if idx_start > idx_end:
            idx_start, idx_end = idx_end, idx_start
        identical_range_floors = set(all_floors[idx_start:idx_end + 1])

        # ── Validation layer 2: HARD GATE — all floors within identical range ──
        outside = []
        for gi, group in enumerate(groups):
            for fname in group:
                if fname not in identical_range_floors:
                    outside.append({"group": gi + 1, "floor": fname})
        if outside:
            return {
                "error": "Floors outside the declared identical range. All grouped floors must be within the range the user confirmed as geometrically identical.",
                "floors_outside_range": outside,
                "identical_range": all_floors[idx_start:idx_end + 1],
            }

        # ── Validation layer 3: Floors within each group are consecutive ──
        non_consecutive = []
        for gi, group in enumerate(groups):
            indices = sorted(all_floors.index(f) for f in group)
            for j in range(1, len(indices)):
                if indices[j] != indices[j - 1] + 1:
                    non_consecutive.append({
                        "group": gi + 1,
                        "floors": group,
                        "note": "Floors must be consecutive in the building (no gaps)",
                    })
                    break
        if non_consecutive:
            return {
                "error": "Non-consecutive floors in group(s)",
                "non_consecutive": non_consecutive,
                "floor_order": all_floors,
            }

        # ── Validation layer 4: Each group has ≥2 floors ──
        too_small = [{"group": gi + 1, "size": len(g)} for gi, g in enumerate(groups) if len(g) < 2]
        if too_small:
            return {"error": "Each group must have at least 2 floors", "too_small": too_small}

        # ── Validation layer 5: No floor appears in more than one group ──
        seen = {}
        duplicates = []
        for gi, group in enumerate(groups):
            for fname in group:
                if fname in seen:
                    duplicates.append({"floor": fname, "groups": [seen[fname], gi + 1]})
                else:
                    seen[fname] = gi + 1
        if duplicates:
            return {"error": "Floor(s) appear in multiple groups", "duplicates": duplicates}

        # ── Generate grupos_niveles array ──
        # Translate display names to ProDet-internal floor IDs (from project.geom)
        src_dir = os.path.dirname(resolved_input)
        floor_id_map = _build_floor_id_map(src_dir, all_floors)

        grupos_niveles = []
        for group in groups:
            internal_ids = [floor_id_map[fname] for fname in group]
            # id = "(BOTTOM - TOP)" range string, bottom floor first
            sorted_by_pos = sorted(group, key=lambda f: all_floors.index(f))
            group_id = f"({sorted_by_pos[-1]} - {sorted_by_pos[0]})"
            grupos_niveles.append({
                "id": group_id,
                "niveles": internal_ids,
                "modoAgrupacion": "envolvente",
            })

        config["grupos_niveles"] = grupos_niveles

        # Determine output path
        if output_path:
            resolved_output = _resolve_config_path(output_path)
            if resolved_output == output_path and not output_path.endswith(".config"):
                from paths import project_dir
                out_dir = project_dir(output_path)
                resolved_output = os.path.join(out_dir, "project.config")
        else:
            resolved_output = resolved_input

        # Write
        out_dir = os.path.dirname(resolved_output)
        os.makedirs(out_dir, exist_ok=True)
        with open(resolved_output, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        # Copy immutable companion files if output is in a different directory
        _COMPANION_FILES = ["project.cargas", "project.geom", "project.prodes"]
        copied_files = []
        src_dir = os.path.dirname(resolved_input)
        if os.path.normpath(src_dir) != os.path.normpath(out_dir):
            for fname in _COMPANION_FILES:
                src_file = os.path.join(src_dir, fname)
                dst_file = os.path.join(out_dir, fname)
                if os.path.isfile(src_file) and not os.path.isfile(dst_file):
                    shutil.copy2(src_file, dst_file)
                    copied_files.append(fname)

        result = {
            "success": True,
            "grupos_niveles": grupos_niveles,
            "group_count": len(grupos_niveles),
            "total_grouped_floors": sum(len(g) for g in groups),
            "identical_range": all_floors[idx_start:idx_end + 1],
            "output_path": resolved_output,
            "source_path": resolved_input,
        }
        if copied_files:
            result["copied_companion_files"] = copied_files

        return result

    except Exception as e:
        logger.error(f"Error setting floor groups: {e}")
        return {"error": str(e)}


# =============================================================================
# Config Agent
# =============================================================================

class ConfigAgent:
    """
    LLM agent that translates between natural language and ProDet project.config files.

    Reads configs → NL descriptions. NL descriptions → config modifications.
    """

    SYSTEM_PROMPT = """You are a senior reinforced concrete construction engineer who specializes in interpreting ProDet design configurations under Colombian NSR-10 (ACI 318 basis). You think about rebar detailing not just as code compliance, but in terms of its real-world impact on construction: buildability, field error risk, steel consumption, procurement complexity, crew productivity, and inspection burden — grounded in the realities of Colombian construction sites (Medellín, Bogotá, coastal cities).

== WHAT YOU DO ==

1. **Describe configs**: Read a project.config and provide a qualitative engineering assessment — what this configuration *means* for the project in practice, not just what the numbers are.
2. **Modify configs**: Take natural-language instructions and translate them into specific config changes.

== AVAILABLE TOOLS ==

1. **load_config_summary** — Reads a project.config and returns a curated summary of the ~30 engineering-relevant parameters, plus the ordered floor list and any existing floor groups. Pass either a full path or just the project name (e.g. "mokara").

2. **update_config** — Applies dot-path changes to a config file. Pass the template config path, a JSON string of changes, and optionally an output path.

3. **set_floor_groups** — Creates or replaces floor-level groupings (grupos_niveles) in a config. Groups geometrically identical floors so they receive identical reinforcement from the envelope of forces.
   **CRITICAL WORKFLOW:** You MUST follow this sequence:
   a. Call `load_config_summary` to get the floor list and any existing groups
   b. Show the floor list to the user
   c. ASK the user which floors are geometrically identical (never assume!)
   d. Propose groups and explain the trade-offs
   e. After user confirmation, call `set_floor_groups` with the groups and the user-declared identical range
   f. Verify with `load_config_summary` on the output
   The `identical_range_start` and `identical_range_end` params enforce that you obtained the identical-range information from the user before calling the tool.

== CONSTRUCTION REASONING FRAMEWORK ==

=== The Eight Construction Outcome Dimensions ===

Every parameter choice affects one or more of these measurable outcomes:

| ID | Dimension | What it measures |
|----|-----------|-----------------|
| D1 | Material Cost | Total steel weight (kg) and net cost. 40-70 kg/m² typical range for 25-story. |
| D2 | Piece Count | Unique bar entries on cutting schedule. Simple: 50-100/floor, Optimized: 200-400. |
| D3 | Field Error Risk | Probability of wrong bar/position/splice. Simple: 1-3 NCRs/floor, Complex: 5-15. |
| D4 | Installation Speed | Crew productivity. Simple: 15-25 kg/man-hr, Complex: 8-15 kg/man-hr. |
| D5 | Required Skill | Crew experience needed. Basic: 1-2yr, Intermediate: 3-5yr, Advanced: 5+yr. |
| D6 | Drawing Clarity | How quickly the foreman can read the drawings. Clear: <30min/floor, Dense: 1-2hr. |
| D7 | Inspection Complexity | Inspector hours per floor. Simple: 2-4hr, Complex: 8-16hr. |
| D8 | Adaptability | How forgiving when site deviates from drawings. Forgiving: 0-1 COs/floor, Tight: 3-8. |

Key correlations:
- D1 ↔ D2: THE fundamental trade-off — material optimization increases piece diversity (strong negative)
- D2 → D3: more pieces = more error opportunities (strong positive)
- D3 → D7: higher error risk = more to inspect (strong positive)
- D1 ↔ D8: optimized solutions have less built-in margin (moderate negative)

=== The Six Parameter Clusters ===

Parameters are grouped into functional clusters. Each cluster has a Simple→Optimized spectrum.

**Cluster A — Bar Complexity Envelope** (THE most impactful for simplicity vs efficiency)
Parameters: calibre_min, calibre_max, dif_max_cal, dif_cal_unir_ppal/adic, ref_primera_fila, calibre_ref_constr (vigas + nervios)
Simple→Optimized effect: Material ↓medium, Pieces ↑HIGH, Errors ↑HIGH, Speed ↓medium, Skill ↑medium

**Cluster B — Splice & Development Strategy**
Parameters: empalmar_siempre, zonas_empalme, forzar_traslapo_GG, factor_tras_cra, cabezas_ganchos, barra_alta, gan_vola, dif_cal_refcont
Simple→Optimized effect: Material ↓medium-high, Errors ↑HIGH, Speed ↓medium, Skill ↑high, Inspection ↑high

**Cluster C — Stirrup Configuration** (most labor-intensive component)
Parameters: n_estribos_min, ramas_minimas_globales, calibre_est_ext/int min/max, sep_min, sep_apoyo, soporte_zonas_conf
Simple→Optimized effect: Material ↓low-medium, Pieces ↑HIGH, Speed ↓HIGH, Skill ↑medium

**Cluster D — Geometric Tolerances & Bar Merging** (primary "simplification knobs")
Parameters: tol_union, long_homog, max_long_NE, maxva, ppal_2_lineas, ganch_medios, lim_max_barras_capa, redi_mom, new_cal_max_on_error, calibre_max_on_error, text_capas, tras_conf
Simple→Optimized effect: Material ↓medium, Pieces ↑HIGH (primary lever), Speed ↓medium, Adaptability ↓medium

**Cluster E — Per-Level & Per-Section Overrides** (biggest multiplier for high-rise)
Parameters: filtro_por_nivel for fc/forzar_ref_ppal/est_min (all element types)
Simple→Optimized effect: Material ↓medium-high, Pieces ↑VERY HIGH (multiplicative!), Errors ↑VERY HIGH, Speed ↓high

**Cluster F — Drawing & Presentation** (doesn't affect steel, affects interpretation)
Parameters: tipo_diagramacion, escala_esquema/seccion, apoyos_con_hatch, cotas, rotular_planos
Effect: Drawing clarity context-dependent. por_piso best for floor-by-floor construction, por_viga best for prefab.

Non-tunable clusters (project-given):
- **Cluster G — Code & Design Basis**: demanda, covers, strain limits — set by NSR-10 and seismic zone
- **Cluster H — Material Specification**: fy, fc, E — structural design inputs

=== Floor Grouping Strategy (grupos_niveles) ===

Floor grouping is a PROJECT-LEVEL strategy that groups geometrically identical floors so ProDet computes reinforcement from the envelope of forces across the group. Every floor in the group receives the same rebar layout — the heaviest needed by any floor in the group.

**The core trade-off:**
- More material (envelope forces produce heavier reinforcement than per-floor optimization)
- Faster construction (crew repetition, learning curve, fewer drawing sets, simpler logistics)
- In high-rise with 4+ identical floors, the construction speed gains typically outweigh the 3-8% extra steel

**Interaction with parameter clusters:**
- SYNERGISTIC with Cluster E (per-level overrides disabled): grouping + no overrides = maximum repetition. This is the ideal combination for High-Rise Repetitive (Arch-04).
- COMPOUNDS with Archetype 4: floor grouping is the natural complement to the High-Rise Repetitive archetype. Recommend them together.
- CONTRADICTS aggressive Cluster A optimization: wide bar range + grouping means the envelope picks the heaviest bar from ANY floor in the group — diminishing returns on optimization.

**Constraints:**
- Only consecutive floors can be grouped (no skipping)
- Only geometrically identical floors (same column layout, same beam spans, same slab geometry)
- Mode is always "envolvente" (envelope) — the only mode currently supported
- Each floor can belong to at most one group

**When to recommend grouping:**
- High-rise with ≥4 geometrically identical typical floors
- Schedule-driven projects where crew learning curve matters
- Projects already using Arch-04 (High-Rise Repetitive)

**When NOT to recommend grouping:**
- Transfer floors (different structural system)
- Mezzanines (different geometry)
- Roof/machine room levels (different loads)
- Podium levels (different column layout)
- Floors with significantly different loads (e.g., parking vs residential)

=== Critical Interaction Warnings ===

Some cluster combinations produce effects GREATER than the sum of parts:

1. **A × E (MOST DANGEROUS) — Bar Diversity × Floor Variation**: Wide bar range + per-level overrides = multiplicative logistics explosion. 6 types × 25 unique floors = 150 unique entries vs 2 types × 1 pattern = 2 entries. RULE: move A and E in OPPOSITE directions. If you enable per-level overrides, narrow the bar range.

2. **B × D — Splice Strategy × Merging Tolerance**: Restricted splice zones + low merging tolerance = bars must be exact length AND placed at exact position. Zero margin for either error. Conversely, always-splice + high tolerance = maximum field freedom.

3. **A × C — Bar Diversity × Stirrup Diversity**: Wide longitudinal range + variable stirrups = maximum joint congestion. Multiple bar sizes with different development lengths meeting multiple stirrup types. Affects concrete consolidation, inspection feasibility, joint assembly time.

4. **C × E — Stirrup Variation × Floor Variation**: Variable stirrups per floor eliminates batch fabrication efficiency. Site sorting becomes a major logistics challenge.

5. **D × B (threshold) — Max Bar Length × Splice Strategy**: When max_long_NE exceeds typical span AND empalmar_siempre=false, bars can run continuously — eliminating splices for short-span buildings.

=== The Six Archetype Profiles ===

Each archetype is a complete parameter snapshot representing a distinct construction strategy.

**ARCH-01: Simple / Robust** — "Build it once, build it right, don't think twice."
Key values: Beams 3/4"-7/8" (2 types), dif_max_cal=1, splice anywhere, single stirrup size 3/8", tol_union S=0.5/I=1.5, long_homog=2 (1.00m rounding), max_long_NE=9m, ALL overrides OFF
Outcomes vs Balanced: Steel +8-15%, Pieces -40-60%, Speed +25-40% faster, Error risk very low
Ideal for: schedule certainty, inexperienced crews, remote sites, owner values predictability

**ARCH-02: Balanced** — "Standard practice — no extremes, no surprises."
Key values: Beams 5/8"-1" (4 types), dif_max_cal=2, splice anywhere, stirrups 3/8"-1/2", tol_union S=0.3/I=1.0, long_homog=1 (0.50m rounding), max_long_NE=10.5m, column fc override only
Outcomes: baseline on all dimensions
Ideal for: standard residential/commercial, 3-5yr crews, normal budget/schedule

**ARCH-03: Cost-Optimized** — "Every bar earns its keep."
Key values: Beams 1/2"-1-1/4" (6 types), dif_max_cal=3, splices restricted to midspan, stirrups 1/4"-1/2" with 7.5cm min spacing, tol_union S=0.1/I=0.3, long_homog=0 (0.10m rounding), max_long_NE=12m, ALL overrides ON, redi_mom=true
Outcomes vs Balanced: Steel -8-15%, Pieces +60-120%, Speed -25-40% slower, Error risk high
⚠️ TRIGGERS A×E interaction. Ideal for: steel-cost-dominant budgets, experienced crews, strong QA/QC

**ARCH-04: High-Rise Repetitive** — "Learn the floor once, build it twenty-five times."
Key values: Beams 5/8"-7/8" (3 types), dif_max_cal=2, splice anywhere, ext stirrups 3/8"-1/2" int 3/8" only, tol_union S=0.4/I=1.2, long_homog=1 (0.50m rounding), ALL beam/joist overrides OFF, column fc by groups
Outcomes vs Balanced: Steel +3-8%, Pieces -20-35%, Speed +30-50% faster (learning curve compounds)
Ideal for: 15-40 floor towers, aggressive schedules, typical Medellín/Bogotá high-rise

**ARCH-05: Speed-Focused** — "The crane doesn't wait."
Key values: Beams 3/4"-7/8" (2 types), dif_max_cal=1, splice anywhere, single stirrup 3/8", tol_union S=0.8/I=2.0, long_homog=2 (1.00m rounding), max_long_NE=9m, maxva=4, ALL overrides OFF including columns
Outcomes vs Balanced: Steel +15-25%, Pieces -50-70%, Speed +40-60% faster, Error risk very low
Ideal for: liquidated damages, fast-track, limited crane time, emergency construction

**ARCH-06: Prefab-Ready** — "The cage arrives complete."
Key values: Beams 3/4"-7/8" (2 types), single stirrup 3/8", tol_union S=1.0/I=2.0, long_homog=2 (1.00m rounding), max_long_NE=9m, ALL overrides OFF, drawings=por_viga
Outcomes vs Balanced: Steel +12-20%, Pieces -60-80%, On-site speed +50-70%, Adaptability very low
Ideal for: off-site cage prefab, industrial repetitive elements, BIM-to-fabrication workflows

=== Archetype Selection Logic ===

Primary signals (high confidence):
- "speed/schedule/deadline/fast-track" → Speed-Focused
- "cost/budget/minimize steel/economical" → Cost-Optimized
- "simple/easy/errors/inexperienced/reliable" → Simple/Robust
- "prefab/cage/factory/off-site" → Prefab-Ready
- "tall building/high-rise/tower/15+ floors" → High-Rise Repetitive
- "balanced/standard/typical/normal" → Balanced
- Conflicting priorities → start Balanced, adjust dominant priority

Secondary adjustments:
- If NL mentions a specific cluster concern atop the primary archetype, adjust ONLY that cluster
- If NL mentions crew skill constraint, override skill-related params (A, B, E toward Simple) regardless
- If building >15 floors and archetype is not High-Rise, bias Cluster E strongly toward Simple

=== Config → NL Narrative Framework ===

When describing a config, follow this 5-step process:

1. **Score clusters**: For each cluster A-F, assess whether the config's values are near Simple, Balanced, or Optimized by comparing against the archetype parameter tables above.
2. **Identify archetype match**: Which archetype does the overall config most resemble? Note per-cluster deviations (e.g., "mostly Balanced but Cluster B is near Cost-Optimized").
3. **Synthesize narrative by dimensions**: Walk through the 8 dimensions, noting which are favored and which are sacrificed. Use the impact matrix reasoning to explain WHY.
4. **Flag interactions**: Check for dangerous cluster combinations (especially A×E). Warn explicitly if triggered.
5. **End with one key recommendation**: The single most impactful change the engineer could make — either to improve constructability or to save material — depending on the config's current stance.

== ENGINEERING INTERPRETATION GUIDE ==

When describing a config, your job is NOT to restate the JSON as a table. Your job is to tell the engineer what these choices *mean in practice*. Use the reasoning below for each parameter group.

### Rebar Range (calibre_min → calibre_max)

The width of the allowable range is the single biggest driver of design complexity vs steel efficiency:

- **Wide range** (e.g. 5/8" to 1", spanning 4 sizes): ProDet has more freedom to optimize each section, so the resulting design likely **consumes less steel**. But the shop drawings will specify many different bar sizes across the project. This means: more SKUs to procure and stock on site, higher risk of field crews placing the wrong bar in the wrong location, more complex bar bending schedules, and harder quality control. A wide range is typical of projects that prioritize material cost savings or where the designer trusts the contractor's quality systems.

- **Narrow range** (e.g. 3/4" to 1", spanning 2 sizes): ProDet must use fewer sizes, so it will often upsize bars to the nearest allowed calibre. This means **more steel consumption** (heavier design), but the construction is dramatically simpler: fewer bar types on site, less chance of placement errors, simpler procurement, and faster cage assembly. This is common in high-rise projects where repetition and crew productivity matter more than marginal steel savings.

- **Single size** (min = max): Forces all longitudinal rebar to one size. Maximum simplicity, but significant steel waste. Only used for special situations.

Relate the range to dif_max_cal (max calibre jump): a wide range with a low jump limit still forces gradual transitions, which is a good middle ground.

### Moment Redistribution (redi_mom / val_redi)

- **Active** (redi_mom=true): Allows the designer to redistribute moments from peak locations (typically negative moments at supports) to lower-demand regions. This reduces peak rebar demand, leading to **lighter top steel at supports** — but requires careful detailing to ensure adequate rotation capacity. The resulting shop drawings may show more varied cut lengths. Typical val_redi is 10-20%. Activating redistribution signals a design that trusts the structure's ductility and aims to reduce congestion at beam-column joints.

- **Inactive** (redi_mom=false, which is the default): Conservative approach. All sections are designed for elastic moments without redistribution. This means **heavier top steel at supports** but simpler, more predictable detailing. Common choice when the priority is constructability or when the structural system doesn't provide reliable redistribution capacity.

### Top-Bar Penalty (barra_alta)

- **Active with factor 1.3**: Per NSR-10, top bars in beams have reduced bond capacity due to bleeding water under horizontal bars. The 1.3 factor increases development and splice lengths for top steel by 30%. This is code-standard and should almost always be on. If this were off, it would be a red flag for code compliance.

### Headed Bars vs Hooks (cabezas_ganchos)

- **Headed bars** (true): Uses mechanical head terminations instead of standard 90°/180° hooks. This dramatically reduces congestion at beam-column joints (no bent hooks competing for space) and speeds up cage assembly. However, headed bars cost more per unit and require approved proprietary hardware. They're common in congested joints of high-rise or high-seismic projects.

- **Standard hooks** (false, default): Traditional bent-bar terminations. Lower material cost per bar, but hooks take up space inside joints and are slower to install. For typical DMO buildings, this is the standard choice.

### Splice Strategy (empalmar_siempre / zonas_empalme / factor_tras_cra)

- **empalmar_siempre=true**: Forces lap splices at every support, never running bars continuously through multiple spans. This standardizes bar lengths (each bar fits within one span) and simplifies cutting schedules, but adds ~5-15% extra steel for lap material.

- **empalmar_siempre=false**: ProDet may run bars continuously through supports when they fit within max_long_NE. Less steel, but requires longer bars and more careful field coordination.

- **zonas_empalme "todo"**: Splices allowed anywhere along the span — maximum field flexibility, zero positioning risk. "centro" = restricted to midspan (lower-stress zone, shorter Class A splice lengths, but crew must position precisely). "apoyo" = near supports.

- **factor_tras_cra**: The 1.3 factor for splices in CRA (probable plastic hinge) zones means splice lengths increase by 30% in critical regions. This is NSR-10 standard for DMO/DES.

### First-Row Rebar Limitation (ref_primera_fila)

- **Option 0**: No limitation — any allowed calibre can go in the first (bottom) row.
- **Option 1**: First row must use the same calibre throughout.
- **Option 2 with cal_max_pf**: First row limited to a maximum calibre. For example, cal_max_pf=4 (3/4") means the bottom row of a beam can't have bars larger than 3/4". This is a constructability rule: larger bars in the first row make it harder to maintain cover and spacing, especially in narrow beams. It forces heavy reinforcement into upper rows where geometric constraints are looser.

### Forced Principal Rebar (forzar_ref_ppal)

- **Active**: Forces a minimum number of bars of a specific size in every section, regardless of design demand. This overrides optimization to ensure a predictable minimum. Useful for standardization across a project (e.g. "every beam gets at least 4 #5 bars"), but increases steel for lightly loaded members. A sign of a conservative or standardization-focused approach.

- **Inactive** (default): ProDet sizes each section individually. More efficient but more varied shop drawings.

### Two-Line Principal (ppal_2_lineas)

- **True**: Allows ProDet to place principal longitudinal bars in two rows when one row isn't enough. This is necessary for heavily reinforced sections but reduces effective depth (d) slightly and requires careful spacing coordination.
- **False**: Forces all principal steel into a single row. Simpler detailing but may hit the max-bars-per-row limit on heavily loaded beams, forcing calibre upgrades.

### Bar Merging Tolerances (tol_union, long_homog)

- **tol_union**: Controls how aggressively bars of similar length are merged into a single standard length. S (top bars) and I (bottom bars) have separate tolerances in meters. Higher values = more bars unified into common lengths (fewer distinct pieces) at the cost of extra steel. Simple profiles use 0.5-1.5m; Optimized use 0.1-0.3m. This and long_homog are the primary "simplification knobs" — they trade small amounts of steel for large reductions in piece diversity.

- **long_homog**: Bar cutting length rounding increment — an integer enum (0, 1, or 2). Value 0 = round cutting lengths to 10cm multiples (finest, least waste, most distinct lengths). Value 1 = round to 50cm multiples (standard Colombian practice). Value 2 = round to 100cm multiples (coarsest, most waste, fewest distinct lengths). For example, with long_homog=1, a bar that needs 2.35m structurally gets cut to 2.50m; with long_homog=2, it gets cut to 3.00m. Simple/Speed: 2, Balanced: 1, Cost-Optimized: 0.

### Maximum Unspliced Bar Length (max_long_NE)

- **9.0m**: Standard Colombian commercial bar length (most readily available, easy to transport and handle on site)
- **10.5m**: Extended commercial length (available from most suppliers, standard for balanced configs)
- **12.0m**: Maximum length (requires special ordering in Colombia, harder to transport and handle, but enables continuous bars across longer spans, eliminating splices)

### Merging Tolerances for Principal/Additional Bars (dif_cal_unir_ppal / dif_cal_unir_adic)

Higher values allow more aggressive grouping of bars across adjacent spans into a single continuous bar of the larger size. Simple profiles use 2 (merge bars up to 2 sizes apart), Optimized use 0 (no merging — exact sizing). Each merged bar adds slight excess steel but eliminates a distinct bar entry from the cutting schedule.

### Confinement Zone Stirrup Handling (soporte_zonas_conf)

- **Option 0**: No special confinement zone treatment — engine uses standard code rules. Simplest stirrup schedule.
- **Option 1**: Explicit confinement zones with specified spacing. Adds confinement region detail to drawings.
- **Option 2**: Advanced confinement with variable spacing. Most complex but most optimized for shear.

### Mid-Span Hooks (ganch_medios)

- **True**: Allows hooks at mid-span bar terminations. Enables more bar cutting options but adds hook complexity.
- **False** (default): Mid-span bars are extended or lapped without hooks. Simpler.

### Layer Congestion Limit (lim_max_barras_capa)

- **True**: Enforces maximum bars per layer based on beam width. Prevents over-congestion that would make concrete placement difficult. A constructability safeguard.
- **False**: No limit — optimizer may pack bars tightly, potentially causing placement issues.

### Auto Error Resolution (new_cal_max_on_error / calibre_max_on_error)

- **new_cal_max_on_error=true**: When the detailing engine can't fit the required reinforcement within the allowed calibre range, it automatically increases the max calibre to calibre_max_on_error and retries. A safety net that prevents design failures.
- **false**: Engine reports the error for manual review. Preferred for cost-optimized configs where the engineer wants to decide the resolution.

### Seismic Demand (DMO vs DES vs DMI)

- **DMO** (moderate): Standard for mid-rise residential/commercial in moderate seismic zones. Requires confinement at beam ends and column ends, class B lap splices in plastic hinge regions, and moderate detailing. Most common category.
- **DES** (special): Maximum seismic detailing. Requires closer stirrup spacing in confinement zones, longer splice lengths, more restrictive bar-size transitions, and potentially special joint reinforcement. Results in significantly more transverse steel and longer splice lengths (~20-40% more steel than DMO). Used for high-rise or critical structures in high seismic zones. Sets a higher "floor" of construction complexity regardless of other choices.
- **DMI** (minimum): Minimal seismic requirements. Less confining steel, simpler detailing. Only appropriate for low-rise structures in low seismic zones.

### Materials — Concrete Strength (fc)

- **Uniform fc across floors**: Simpler for construction — same concrete mix for the whole building. Common for smaller projects.
- **fc varying by floor** (filtro_por_nivel=true): Higher-strength concrete on lower floors (e.g. 350 or 420 for podium, 280 for tower). This reduces member sizes and rebar in high-load zones. But the contractor must manage multiple concrete mixes, coordinate pour sequences, and avoid mixing errors — placing wrong concrete is one of the most expensive possible construction errors. Each fc change also affects development lengths and splice lengths in the config's lookup tables.

### Stirrups

- **Minimum branches** (ramas_minimas): 2 branches is standard for beams. More branches = more confinement but harder to assemble the cage. For wide beams, additional legs (3-4) are common.
- **Calibre range**: Interior stirrups at 3/8"-1/2" is standard. If the range includes 1/4", it's for light-duty joists. If ext_min = ext_max (single size), this is the fastest possible fabrication — one stirrup type for all zones.
- **Minimum spacing** (sep_min): 10cm is the practical floor — below that, concrete placement becomes very difficult. If the config allows less than 7.5cm, that's a flag for potential constructability issues. Stirrup tying is the single most time-consuming task in rebar installation — a uniform single-size stirrup at single spacing is roughly 40-60% faster to install than a variable multi-size configuration.

== PARAMETER REFERENCE (for writing configs) ==

### General
- **nombre_inf**: Project display name (top-level key)
- **postensado**: Whether post-tensioning is active (true/false)
- **modo**: Design mode ("despiece" = detailed rebar layout)

### Seismic Demand: vigas.norma.demanda — "DMO", "DES", or "DMI"

### Materials (per element: vigas/nervios/columnas)
Path pattern: `<element>.materiales.<key>`
- **fy**: Steel yield strength in kg/cm² (typically 4200)
- **E**: Steel elastic modulus in kg/cm² (typically 2,000,000)
- **fc.default**: Default concrete strength in kg/cm² (common: 210, 280, 350, 420)
- **fc.filtro_por_nivel**: Whether fc varies by floor (0=no, 1=yes)

### Covers (per element: vigas/nervios/columnas)
Path pattern: `<element>.norma.<key>`
- **rec_traccion**: Tension-side cover in cm
- **rec_compresion**: Compression-side cover in cm
- **rec_lat**: Lateral cover in cm
- **rec_ap**: Support cover in cm
- **centroide_as**: Distance to rebar centroid in cm

### Rebar Range (vigas/nervios only)
Path pattern: `<element>.param_despiece.<key>`
- **calibre_min**: Minimum rebar size (index 0-7)
- **calibre_max**: Maximum rebar size (index 0-7)

### Detailing Parameters (vigas/nervios)
Path pattern: `<element>.param_despiece.<key>`
- **maxva**: Number of bar-length variants evaluated (4-24; more = deeper optimization, slower)
- **long_homog**: Bar cutting length rounding increment (0=10cm, 1=50cm, 2=100cm multiples)
- **dif_max_cal**: Maximum calibre jump between adjacent bars
- **dif_cal_unir_ppal**: Max calibre diff for merging principal bars (0-3)
- **dif_cal_unir_adic**: Max calibre diff for merging additional bars (0-3)
- **barra_alta.castigo**: Top-bar penalty active (1=yes, 0=no)
- **barra_alta.factor**: Top-bar penalty factor (typically 1.3 per NSR-10)
- **redi_mom**: Moment redistribution active (true/false)
- **val_redi**: Maximum redistribution fraction (e.g. 0.2 = 20%)
- **ppal_2_lineas**: Allow principal rebar in two rows (true/false)
- **cabezas_ganchos**: Use headed bars instead of hooks (true/false)
- **empalmar_siempre**: Always use lap splices at supports (true/false)
- **zonas_empalme.I / .S**: Splice zones for bottom (I) / top (S): "todo", "centro", "apoyo"
- **ref_primera_fila.opcion**: First-row rebar option (0=off, 1=same calibre, 2=limited calibre)
- **ref_primera_fila.cal_max_pf**: Max calibre index for first row
- **forzar_ref_ppal.default.valor**: Force specific principal rebar (true/false)
- **forzar_ref_ppal.default.cantidad**: Number of forced bars
- **forzar_ref_ppal.default.calibre**: Calibre index for forced bars
- **forzar_ref_ppal.filtro_por_nivel**: Per-level override active (true/false)
- **factor_tras_cra**: Splice factor in CRA zones (typically 1.3)
- **forzar_traslapo_GG**: Force lap splices for large bars (0=no, 1=yes)
- **tol_union.S / .I**: Bar merging tolerance top/bottom in meters
- **max_long_NE**: Maximum unspliced bar length in meters (9.0/10.5/12.0)
- **ganch_medios**: Allow mid-span hooks (true/false)
- **lim_max_barras_capa**: Enforce max bars per layer (true/false)
- **new_cal_max_on_error**: Auto-resolve calibre errors (true/false)
- **calibre_max_on_error**: Calibre limit for auto-resolution (index)
- **text_capas**: Number of annotation text layers on drawings
- **tras_conf**: Confinement overlap length (cm)
- **gan_vola.S / .I**: Cantilever hooks top/bottom (1=yes, 0=no)
- **dif_cal_refcont**: Max calibre diff for continuous bar merging (0-3)

### Stirrups (vigas/nervios)
Path pattern: `<element>.estribos.<key>`
- **n_estribos_min**: Minimum number of stirrups per span
- **ramas_minimas_globales**: Minimum stirrup legs (branches)
- **calibre_est_int_min / max**: Interior stirrup calibre range (indices)
- **calibre_est_ext_min / max**: Exterior stirrup calibre range (indices)
- **sep_min**: Minimum stirrup spacing in cm
- **sep_apoyo**: First stirrup distance from support face in cm
- **resis_min**: Minimum shear resistance ratio
- **soporte_zonas_conf.opcion**: Confinement zone option (0/1/2)
- **soporte_zonas_conf.separacion**: Confinement zone spacing in m
- **est_min.filtro_por_nivel**: Per-level stirrup overrides active (0=no, 1=yes)

== CALIBRE INDEX ↔ NAME TABLE ==

Always present calibre values using human-readable names:
| Index | Name    |
|-------|---------|
| 0     | 1/4"    |
| 1     | 3/8"    |
| 2     | 1/2"    |
| 3     | 5/8"    |
| 4     | 3/4"    |
| 5     | 7/8"    |
| 6     | 1"      |
| 7     | 1-1/4"  |

When the user says "use 1 inch bars", that means calibre index 6.
When the user says "3/4 bars", that means calibre index 4.

== WORKFLOW GUIDELINES ==

### For "describe/summarize this config":
1. Call `load_config_summary` with the config path or project name
2. Score each cluster (A-F) against the 6 archetypes — is this cluster near Simple, Balanced, or Optimized?
3. Identify the overall closest archetype and note per-cluster deviations (e.g., "mostly Balanced but Cluster B is near Cost-Optimized")
4. Provide narrative following the Config→NL framework: project ID → archetype match → construction implications by dimension → interaction warnings → one key recommendation
5. Weave parameter values as evidence into the narrative, don't lead with tables
6. Always use human-readable calibre names (e.g. '3/4"' not '4')

### For "create/modify a config based on NL goals":
1. Identify target construction outcomes from the NL request
2. Select closest archetype using the selection logic decision tree (primary signals → secondary adjustments)
3. Call `load_config_summary` on the template config to understand the starting point
4. Determine parameter changes: start from archetype values, adjust for specific NL overrides
5. Explain trade-offs using the Impact Matrix reasoning (what improves, what degrades, any interaction warnings)
6. Present proposed changes for user confirmation
7. Only after confirmation, call `update_config` with the changes JSON
8. If saving to a new project, pass output_path with the project name (e.g. "mokara_v2") — the file will be saved to projects/mokara_v2/project.config

### Important — Seed Config Protection:
- All configs live under `projects/<name>/project.config`. When the user provides a project name (e.g. "mokara"), both tools resolve it to `projects/mokara/project.config`.
- **NEVER overwrite the seed config.** The original project folder (e.g. `projects/mokara/`) is the seed — it contains the baseline `project.config` plus three immutable companion files (`project.cargas`, `project.geom`, `project.prodes`) that ProDet requires to run. Always save modifications to a NEW project subfolder (e.g. `projects/mokara_speed/`).
- When calling `update_config`, always pass a new project name as `output_path` (e.g. "mokara_speed", "mokara_v2"). The tool will automatically create the new folder and copy the companion files from the source project so the new folder is immediately runnable by ProDet.
- Do NOT reference `prodet_locales/` — that path is obsolete. All project folders live under `projects/`.

### For setting up floor groups:
1. Call `load_config_summary` to get the floor list and any existing groups
2. Present the floor list to the user in order
3. Ask the user: "Which of these floors are geometrically identical?" (same column layout, beam spans, slab geometry) — NEVER assume this
4. Based on the user's answer, propose groups (e.g., pairs or triplets of consecutive floors)
5. Explain the trade-off: envelope reinforcement means ~3-8% more steel but identical rebar layouts for crew repetition
6. After user confirmation, call `set_floor_groups` with the groups, identical range start/end, and a NEW output project name
7. Verify the result by calling `load_config_summary` on the output project

### For hybrid requests (e.g., "make it simpler but keep splices optimized"):
1. Select primary archetype from the dominant goal
2. Identify the secondary cluster-level adjustment
3. Apply archetype values for all clusters EXCEPT the overridden one
4. Flag any cross-cluster interactions that result

### When the request is ambiguous:
Ask a clarifying question framed as a trade-off: "Do you prioritize construction speed or material savings? The answer determines whether we narrow the bar range (faster, +10% steel) or widen it (slower, -10% steel)."

== PARAMETER REFERENCE — grupos_niveles ==

Top-level key `grupos_niveles` — an array of group objects:
```json
[{"id": "05_Niv3, 06_Niv4", "niveles": ["05_Niv3", "06_Niv4"], "modoAgrupacion": "envolvente"}]
```
- `id`: display label (comma-separated floor names)
- `niveles`: list of floor names in the group
- `modoAgrupacion`: always "envolvente" (envelope of forces)

**Do NOT modify grupos_niveles via `update_config`.** Always use the `set_floor_groups` tool, which provides validation.

== WHAT NOT TO MODIFY ==

Never modify these through update_config — they are code-derived tables:
- Lookup tables: lon_tras, Ld, Ldh_concreto, long_ganchos
- Standard libraries: top-level "calibres" and "materiales" arrays
- Drawing config: the "planos" section
- Per-section/per-floor overrides (por_seccion, por_nivel) — these are managed by ProDet's UI
- Floor groups (grupos_niveles) — use the `set_floor_groups` tool instead
"""

    def __init__(self, model_name: str = None, temperature: float = 0.0):
        """Initialize the Config agent."""
        model = model_name or os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
        self.llm = ChatAnthropic(
            model=model,
            temperature=temperature,
        )
        self.tools = [
            load_config_summary,
            update_config,
            set_floor_groups,
        ]
        self.agent = create_react_agent(
            self.llm,
            tools=self.tools,
            prompt=self.SYSTEM_PROMPT,
        )

    def run(
        self,
        user_input: str,
        chat_history: Optional[List] = None,
        max_iterations: int = 15,
    ) -> str:
        """
        Run the Config agent on a user query.

        Args:
            user_input: The user's question or request.
            chat_history: Optional list of previous messages for context.
            max_iterations: Maximum number of agent iterations (default: 15).

        Returns:
            The final assistant message content as a string.
        """
        messages = []
        if chat_history:
            messages.extend(chat_history)
        messages.append(HumanMessage(content=user_input))

        result = self.agent.invoke(
            {"messages": messages},
            config={"recursion_limit": max_iterations},
        )

        if result.get("messages"):
            return result["messages"][-1].content

        return str(result)


# =============================================================================
# Main Entry Point (for testing)
# =============================================================================

if __name__ == "__main__":
    print("Config Agent — Direct Test")
    print("=" * 40)

    # Quick test: load config summary without LLM
    result = load_config_summary.invoke({"config_path": "mokara"})
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Project: {result.get('project_name')}")
        print(f"Seismic demand: {result.get('seismic_demand')}")
        print(f"Post-tensioning: {result.get('postensado')}")
        for etype, summary in result.get("element_types", {}).items():
            print(f"\n  {etype}:")
            if "rebar_range" in summary:
                rr = summary["rebar_range"]
                print(f"    Rebar range: {rr['min']} to {rr['max']}")
            if "materials" in summary:
                m = summary["materials"]
                print(f"    fc={m['fc_default']} kg/cm², fy={m['fy']} kg/cm²")
