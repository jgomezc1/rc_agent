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
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

def _variant_suffix(output_dir: str) -> str:
    """Extract the variant suffix from an output directory name.

    Given 'projects/mokara_emp_mecanicos', returns '_emp_mecanicos'.
    Given 'projects/mokara', returns ''.
    """
    from paths import base_project_name
    folder = os.path.basename(output_dir)
    base = base_project_name(folder)
    if folder != base and folder.startswith(base):
        return folder[len(base):]
    return ""


def _stamp_variant_identity(config: dict, output_dir: str, source_dir: str) -> None:
    """Update 'name' and 'nombre_inf' so ProDet can distinguish this variant.

    Only modifies the fields when writing to a different directory than the source.
    Appends the variant suffix (e.g. '_emp_mecanicos') to the existing 'name',
    and adds it in parentheses to 'nombre_inf'.
    """
    if os.path.normpath(output_dir) == os.path.normpath(source_dir):
        return

    suffix = _variant_suffix(output_dir)
    if not suffix:
        return

    # Update 'name' (ProDet internal ID, e.g. "DMO_MOK" → "DMO_MOK_emp_mecanicos")
    old_name = config.get("name", "")
    if old_name and not old_name.endswith(suffix):
        config["name"] = old_name + suffix

    # Update 'nombre_inf' (display name, e.g. "Ejemplo Mokara" → "Ejemplo Mokara (emp_mecanicos)")
    old_inf = config.get("nombre_inf", "")
    tag = suffix.lstrip("_")
    if old_inf and tag not in old_inf:
        config["nombre_inf"] = f"{old_inf} ({tag})"


def _write_config(path: str, config: dict) -> str:
    """Write config to project.config, project.config.json, and a descriptive copy.

    The descriptive copy uses the variant suffix as filename (e.g. emp_mecanicos.json).
    Returns the path of the .json copy.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    json_path = path + ".json"
    shutil.copy2(path, json_path)

    # Descriptive copy named after the variant suffix
    out_dir = os.path.dirname(path)
    suffix = _variant_suffix(out_dir)
    if suffix:
        descriptive_name = suffix.lstrip("_") + ".json"
        descriptive_path = os.path.join(out_dir, descriptive_name)
        shutil.copy2(path, descriptive_path)

    return json_path


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

_REFERENCE_FILES = {
    "archetypes": "archetype_profiles.json",
    "parameter_catalog": "parameter_semantic_catalog.json",
    "impact_matrix": "impact_matrix.json",
    "calibre_table": None,  # inline
}

_CALIBRE_TABLE = {
    "0": '1/4" (ø6.4mm)',
    "1": '3/8" (ø9.5mm)',
    "2": '1/2" (ø12.7mm)',
    "3": '5/8" (ø15.9mm)',
    "4": '3/4" (ø19.1mm)',
    "5": '7/8" (ø22.2mm)',
    "6": '1" (ø25.4mm)',
    "7": '1-1/4" (ø31.9mm)',
}


@tool
def get_reference_material(topic: str) -> Dict[str, Any]:
    """
    Load detailed reference material from the docs/ directory.

    Use this tool when you need archetype parameter snapshots, full parameter
    cluster details, impact matrix reasoning, or the calibre index table.

    Args:
        topic: One of "archetypes", "parameter_catalog", "impact_matrix",
               "calibre_table".

    Returns:
        Dictionary with the reference data, or an error message.
    """
    if topic not in _REFERENCE_FILES:
        return {"error": f"Unknown topic '{topic}'. Valid: {list(_REFERENCE_FILES.keys())}"}

    if topic == "calibre_table":
        return {"calibre_index_to_name": _CALIBRE_TABLE}

    filename = _REFERENCE_FILES[topic]
    docs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
    filepath = os.path.join(docs_dir, filename)

    if not os.path.isfile(filepath):
        return {"error": f"Reference file not found: {filepath}"}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"error": f"Failed to load {filename}: {e}"}


@tool
def load_config_summary(config_path: str, summary_only: bool = False) -> Dict[str, Any]:
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
        summary_only: If True, return only parameter names and current values
                     without descriptions. Reduces token usage.

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

        if summary_only:
            # Strip descriptions, keep only parameter names and values
            for etype, edata in result.get("element_types", {}).items():
                for section_key in ("rebar_range", "detailing", "stirrups", "materials", "covers"):
                    section = edata.get(section_key, {})
                    if isinstance(section, dict):
                        # Remove description-like keys, keep value keys
                        for k in list(section.keys()):
                            if isinstance(section[k], dict) and "description" in section[k]:
                                section[k].pop("description", None)
            result.pop("floor_groups_note", None)

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

        # Stamp variant identity so ProDet distinguishes this config
        src_dir = os.path.dirname(resolved_input)
        out_dir = os.path.dirname(resolved_output)
        _stamp_variant_identity(config, out_dir, src_dir)

        # Write project.config (local ProDet) + project.config.json (cloud)
        json_path = _write_config(resolved_output, config)

        # Copy immutable companion files if output is in a different directory
        _COMPANION_FILES = ["project.cargas", "project.geom", "project.prodes"]
        copied_files = []
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
            "json_path": json_path,
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

        # Stamp variant identity so ProDet distinguishes this config
        out_dir = os.path.dirname(resolved_output)
        src_dir = os.path.dirname(resolved_input)
        os.makedirs(out_dir, exist_ok=True)
        _stamp_variant_identity(config, out_dir, src_dir)

        # Write project.config (local ProDet) + project.config.json (cloud)
        json_path = _write_config(resolved_output, config)

        # Copy immutable companion files if output is in a different directory
        _COMPANION_FILES = ["project.cargas", "project.geom", "project.prodes"]
        copied_files = []
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
            "json_path": json_path,
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

4. **get_reference_material** — Loads detailed reference data from docs/ on demand. Topics: "archetypes" (6 archetype profile snapshots with parameter values), "parameter_catalog" (full parameter cluster details, valid ranges, Simple/Balanced/Optimized values), "impact_matrix" (causal impact of each cluster on 8 dimensions), "calibre_table" (index↔name mapping). **Call this tool whenever you need archetype parameter values, cluster details, or impact reasoning** instead of guessing from memory.

== CONSTRUCTION REASONING FRAMEWORK ==

=== The Eight Construction Outcome Dimensions ===

Every parameter choice affects one or more of these measurable outcomes:

| ID | Dimension | What it measures |
|----|-----------|-----------------|
| D1 | Material Cost | Total steel weight (kg) and net cost |
| D2 | Piece Count | Unique bar entries on cutting schedule |
| D3 | Field Error Risk | Probability of wrong bar/position/splice |
| D4 | Installation Speed | Crew productivity (kg/man-hr) |
| D5 | Required Skill | Crew experience needed |
| D6 | Drawing Clarity | How quickly the foreman can read the drawings |
| D7 | Inspection Complexity | Inspector hours per floor |
| D8 | Adaptability | How forgiving when site deviates from drawings |

Key correlations: D1↔D2 (fundamental trade-off), D2→D3 (more pieces = more errors), D3→D7, D1↔D8.

=== The Six Parameter Clusters (summary) ===

**A — Bar Complexity Envelope**: calibre_min/max, dif_max_cal. THE most impactful for simplicity vs efficiency.
**B — Splice & Development**: empalmar_siempre, zonas_empalme, cabezas_ganchos. Material ↓medium-high, Errors ↑HIGH.
**C — Stirrup Configuration**: n_estribos_min, calibre_est_ext/int, sep_min. Most labor-intensive component.
**D — Geometric Tolerances & Merging**: tol_union, long_homog, max_long_NE, maxva. Primary "simplification knobs".
**E — Per-Level Overrides**: filtro_por_nivel for fc/forzar_ref_ppal/est_min. Biggest multiplier for high-rise.
**F — Drawing & Presentation**: tipo_diagramacion, escala. Doesn't affect steel.
Non-tunable: G (Code/Design Basis), H (Materials).

For full parameter lists, ranges, and Simple/Balanced/Optimized values, call `get_reference_material("parameter_catalog")`.

=== Critical Interaction Warnings ===

1. **A × E (MOST DANGEROUS)**: Wide bar range + per-level overrides = multiplicative logistics explosion. RULE: move A and E in OPPOSITE directions.
2. **B × D**: Restricted splices + low merging tolerance = zero margin for error.
3. **A × C**: Wide longitudinal range + variable stirrups = maximum joint congestion.
4. **C × E**: Variable stirrups per floor eliminates batch fabrication efficiency.
5. **D × B (threshold)**: max_long_NE exceeds span + empalmar_siempre=false → continuous bars.

For detailed impact reasoning, call `get_reference_material("impact_matrix")`.

=== The Six Archetype Profiles (summary) ===

| ID | Name | Steel vs Balanced | Pieces vs Balanced | Ideal for |
|----|------|-------------------|--------------------|-----------|
| ARCH-01 | Simple/Robust | +8-15% | -40-60% | schedule certainty, inexperienced crews |
| ARCH-02 | Balanced | baseline | baseline | standard residential/commercial |
| ARCH-03 | Cost-Optimized | -8-15% | +60-120% | steel-cost-dominant, experienced crews |
| ARCH-04 | High-Rise Repetitive | +3-8% | -20-35% | 15-40 floor towers |
| ARCH-05 | Speed-Focused | +15-25% | -50-70% | fast-track, limited crane time |
| ARCH-06 | Prefab-Ready | +12-20% | -60-80% | off-site cage prefab |

For complete archetype parameter snapshots, call `get_reference_material("archetypes")`.

=== Archetype Selection Logic ===

Primary signals: "speed/schedule/deadline" → Speed-Focused, "cost/budget/minimize steel" → Cost-Optimized, "simple/easy/errors/inexperienced" → Simple/Robust, "prefab/cage/factory" → Prefab-Ready, "high-rise/tower/15+ floors" → High-Rise Repetitive, "balanced/standard" → Balanced.
Secondary: specific cluster concerns adjust ONLY that cluster; crew skill constraints bias A, B, E toward Simple; >15 floors biases E toward Simple.

=== Floor Grouping Strategy (grupos_niveles) ===

Groups geometrically identical floors so ProDet computes reinforcement from the envelope of forces. Core trade-off: ~3-8% more steel vs. significant construction speed gains from crew repetition.

Synergistic with Cluster E (disabled overrides) and Archetype 4. Contradicts aggressive Cluster A optimization.
Constraints: consecutive floors only, geometrically identical, mode always "envolvente".
Recommend for: ≥4 identical typical floors, schedule-driven projects. NOT for: transfer floors, mezzanines, roof, podium.

== CALIBRE INDEX ↔ NAME TABLE ==

0=1/4", 1=3/8", 2=1/2", 3=5/8", 4=3/4", 5=7/8", 6=1", 7=1-1/4".
Always present calibre values using human-readable names. For full table with mm equivalents, call `get_reference_material("calibre_table")`.

== WORKFLOW GUIDELINES ==

### For "describe/summarize this config":
1. Call `load_config_summary` with the config path or project name
2. Call `get_reference_material("archetypes")` to get archetype parameter snapshots for comparison
3. Score each cluster (A-F) — is this cluster near Simple, Balanced, or Optimized?
4. Identify overall closest archetype and note per-cluster deviations
5. Provide narrative: project ID → archetype match → construction implications by dimension → interaction warnings → one key recommendation
6. Always use human-readable calibre names (e.g. '3/4"' not '4')

### For "create/modify a config based on NL goals":
1. Identify target construction outcomes from the NL request
2. Select closest archetype using the selection logic
3. Call `load_config_summary` on the template config
4. Call `get_reference_material("archetypes")` to get target archetype parameter values
5. Determine parameter changes: start from archetype values, adjust for specific NL overrides
6. Explain trade-offs (call `get_reference_material("impact_matrix")` if needed)
7. Present proposed changes for user confirmation
8. Only after confirmation, call `update_config` with the changes JSON
9. If saving to a new project, pass output_path with the project name (e.g. "mokara_v2")

### Important — Seed Config Protection:
- **NEVER overwrite the seed config.** Always save modifications to a NEW project subfolder.
- When calling `update_config`, always pass a new project name as `output_path` (e.g. "mokara_speed").
- The tool auto-copies companion files (project.cargas/geom/prodes) from the source.

### For setting up floor groups:
1. Call `load_config_summary` → present floor list → ASK user which floors are geometrically identical (NEVER assume)
2. Propose groups, explain trade-off (~3-8% more steel vs. crew repetition)
3. After confirmation, call `set_floor_groups` with groups and identical range, using a NEW output project name
4. Verify with `load_config_summary` on the output

### For hybrid requests (e.g., "make it simpler but keep splices optimized"):
Select primary archetype, identify secondary cluster adjustment, apply archetype for all clusters EXCEPT the overridden one, flag cross-cluster interactions.

### When the request is ambiguous:
Ask a clarifying question framed as a trade-off.

== PARAMETER REFERENCE — grupos_niveles ==

Top-level key `grupos_niveles` — array of group objects:
```json
[{"id": "05_Niv3, 06_Niv4", "niveles": ["05_Niv3", "06_Niv4"], "modoAgrupacion": "envolvente"}]
```
**Do NOT modify grupos_niveles via `update_config`.** Always use the `set_floor_groups` tool.

== PROJECT FAMILIES ==

Projects often have multiple variants sharing a base name (e.g. mokara, mokara_v1,
mokara_v2, mokara_sol_balanced). When the user references a project by its base
name (e.g. "describe the mokara configs"), use **list_project_family** to discover
all related variants. Then:
- If the request is about a single config, use the exact folder named.
- If the request implies multiple configs (e.g. "compare mokara configs" or
  "what are the differences between the mokara variants"), list all family
  members and load/compare their configs.

== WHAT NOT TO MODIFY ==

Never modify via update_config: lookup tables (lon_tras, Ld, Ldh_concreto, long_ganchos), standard libraries ("calibres", "materiales"), drawing config ("planos"), per-section/per-floor overrides (por_seccion, por_nivel), floor groups (use set_floor_groups instead).
"""

    def __init__(self, model_name: str = None, temperature: float = 0.0):
        """Initialize the Config agent."""
        model = model_name or os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
        self.llm = ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=4096,
        )
        from prodet_agent import list_project_family
        self.tools = [
            load_config_summary,
            update_config,
            set_floor_groups,
            get_reference_material,
            list_project_family,
        ]
        self.system_message = SystemMessage(
            content=self.SYSTEM_PROMPT,
            additional_kwargs={"cache_control": {"type": "ephemeral"}},
        )
        self.agent = create_react_agent(
            self.llm,
            tools=self.tools,
            prompt=self.system_message,
        )

    def run(
        self,
        user_input: str,
        chat_history: Optional[List] = None,
        max_iterations: int = 15,
        token_callback=None,
    ) -> str:
        """
        Run the Config agent on a user query.

        Args:
            user_input: The user's question or request.
            chat_history: Optional list of previous messages for context.
            max_iterations: Maximum number of agent iterations (default: 15).
            token_callback: Optional shared TokenCounterCallback for session tracking.

        Returns:
            The final assistant message content as a string.
        """
        messages = []
        if chat_history:
            messages.extend(chat_history)
        messages.append(HumanMessage(content=user_input))

        if token_callback:
            token_callback.set_current_agent("config", model=self.llm.model)
            token_cb = token_callback
        else:
            from utils.token_logger import TokenCounterCallback
            token_cb = TokenCounterCallback(agent_name="config")

        result = self.agent.invoke(
            {"messages": messages},
            config={"recursion_limit": max_iterations, "callbacks": [token_cb]},
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
