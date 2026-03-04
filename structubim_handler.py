#!/usr/bin/env python3
"""
StructuBim Handler — processes ProDet's cantidades.json into processedAnalysis.json.

processedAnalysis.json is the input file for StructuBim (structu-bim.com), a 3D
reinforcement visualizer. This module consolidates the standalone handler logic
(element_processor, complexity_scores, result_processor) into a single file and
adds cantidades.json merge functions to handle the overwrite problem (ProDet
deletes cantidades.json at the start of each element-type run).

Usage from code:
    from structubim_handler import find_cantidades, generate_structubim_json

    # Single project
    result = generate_structubim_json(
        project_paths={"mokara": "projects/mokara/"},
        output_path="projects/mokara/processedAnalysis.json",
        element_types=["vigas", "nervios"],
    )

    # Compare two variants (baseline vs variant)
    result = generate_structubim_json(
        project_paths={
            "mokara": "projects/mokara/",
            "mokara_speed": "projects/mokara_speed/",
        },
        output_path="projects/mokara_speed/processedAnalysis.json",
        element_types=["vigas", "nervios"],
    )
"""

import copy
import json
import os
import shutil
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# cantidades.json copy & merge
# =============================================================================

CANTIDADES_TYPE_SUFFIX = {"vigas": "_V", "nervios": "_N", "columnas": "_C"}


def copy_cantidades_after_run(project_path: str, element_type: str) -> Optional[str]:
    """Copy cantidades.json -> cantidades_V.json (or _N, _C) after a ProDet run.

    ProDet's despiezador.py deletes cantidades.json at the start of each
    element-type run. This preserves a type-specific copy before the next run
    overwrites it — same pattern used for xlsx files.

    Returns destination path or None if source not found.
    """
    src = os.path.join(project_path, "cantidades.json")
    if not os.path.isfile(src):
        return None
    suffix = CANTIDADES_TYPE_SUFFIX.get(element_type, "")
    dest = os.path.join(project_path, f"cantidades{suffix}.json")
    shutil.copy2(src, dest)
    logger.info(f"Copied cantidades.json -> cantidades{suffix}.json in {project_path}")
    return dest


def merge_cantidades_files(project_path: str, element_types: List[str]) -> Optional[Dict]:
    """Merge type-specific cantidades files into one dataset.

    Metadata (calibres, pisos, nombres_planos, grupos_niveles) comes from the
    first file found. Elements are concatenated from all files.

    Returns merged dict or None if no files found.
    """
    merged = None
    for etype in element_types:
        suffix = CANTIDADES_TYPE_SUFFIX.get(etype, "")
        path = os.path.join(project_path, f"cantidades{suffix}.json")
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if merged is None:
            merged = data
        else:
            merged["elements"].extend(data["elements"])
    return merged


def find_cantidades(project_path: str, element_types: List[str] = None) -> Optional[Dict]:
    """Find and load cantidades data for a project.

    Tries type-specific files first (cantidades_V.json, cantidades_N.json),
    merging if multiple exist. Falls back to plain cantidades.json.

    Returns loaded dict or None if nothing found.
    """
    if element_types:
        merged = merge_cantidades_files(project_path, element_types)
        if merged:
            return merged
    single = os.path.join(project_path, "cantidades.json")
    if os.path.isfile(single):
        with open(single, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


# =============================================================================
# Element processing (ported from element_processor.py)
# =============================================================================

def calcular_volumen_concreto(restrains: list, seccion: list) -> float:
    """Compute concrete volume from spans + supports.

    Args:
        restrains: List of dicts with 'inicio' and 'fin' (support positions in cm).
        seccion: List of [ancho, alto] per span (in cm).

    Returns:
        Volume in m³ (original inputs in cm, divides by 10000).
    """
    volumen_total = 0.0

    for i in range(len(seccion)):
        inicio_actual = restrains[i]["inicio"]
        fin_actual = restrains[i]["fin"]
        inicio_siguiente = restrains[i + 1]["inicio"]
        fin_siguiente = restrains[i + 1]["fin"]

        longitud_vano = inicio_siguiente - fin_actual
        ancho, alto = seccion[i]
        area_seccion = ancho * alto

        volumen_vano = area_seccion * longitud_vano
        volumen_total += volumen_vano

        if i < len(seccion) - 1:
            ancho_siguiente, alto_siguiente = seccion[i + 1]
            alto_max = max(alto, alto_siguiente)
            ancho_max = max(ancho, ancho_siguiente)
        else:
            alto_max = alto
            ancho_max = ancho

        longitud_apoyo = fin_actual - inicio_actual
        volumen_apoyo = ancho_max * alto_max * longitud_apoyo
        volumen_total += volumen_apoyo

    longitud_ultimo_apoyo = fin_siguiente - inicio_siguiente
    ancho_ultimo, alto_ultimo = seccion[-1]
    volumen_ultimo_apoyo = ancho_ultimo * alto_ultimo * longitud_ultimo_apoyo
    volumen_total += volumen_ultimo_apoyo

    return volumen_total / 10000


def calcular_peso_y_numero_estribos(estribos: list, calibres: list) -> Tuple[float, int, dict]:
    """Compute stirrup weight, count, and per-diameter breakdown.

    Handles 1-leg, 2-leg, and multi-leg stirrups with different formulas
    involving gancho135 (135° hook length) and pesoLineal (linear weight).

    Returns:
        (total_weight, total_count, by_diameter_dict)
    """
    peso_total = 0
    numero_total = 0
    por_calibre = {calibre["name"]: {"w": 0, "n": 0} for calibre in calibres}

    for estribo in estribos:
        calibre_ext = calibres[estribo["calibre_ext"]]
        calibre_int = (
            calibres[estribo["calibre_int"]]
            if estribo["calibre_int"] is not None
            else None
        )

        n_estribos = estribo["n_estribos"]
        n_ramas = estribo["n_ramas"]
        base = estribo["base"] / 100
        altura = estribo["altura"] / 100

        if n_ramas == 1:
            peso_estribo = (altura + 2 * calibre_ext["gancho135"]) * calibre_ext["pesoLineal"]
            por_calibre[calibre_ext["name"]]["w"] += peso_estribo * n_estribos
            por_calibre[calibre_ext["name"]]["n"] += n_estribos

        elif n_ramas == 2:
            peso_estribo = (
                2 * (base + altura + calibre_ext["gancho135"]) * calibre_ext["pesoLineal"]
            )
            por_calibre[calibre_ext["name"]]["w"] += peso_estribo * n_estribos
            por_calibre[calibre_ext["name"]]["n"] += n_estribos

        else:
            peso_ext = (
                2 * (base + altura + calibre_ext["gancho135"]) * calibre_ext["pesoLineal"]
            )
            peso_int = (altura + 2 * calibre_ext["gancho135"]) * calibre_ext["pesoLineal"]
            peso_estribo = peso_ext + peso_int

            por_calibre[calibre_ext["name"]]["w"] += peso_ext * n_estribos
            por_calibre[calibre_ext["name"]]["n"] += n_estribos
            por_calibre[calibre_int["name"]]["w"] += peso_int * n_estribos
            por_calibre[calibre_int["name"]]["n"] += n_estribos

            n_estribos = (1 + n_ramas - 2) * n_estribos

        peso_total += peso_estribo * estribo["n_estribos"]
        numero_total += n_estribos

    return peso_total, numero_total, por_calibre


def encontrar_figura_barra(barra: dict) -> str:
    """Generate a unique bar figure string from calibre, length, and hooks.

    The figure string encodes the bar's identity for counting unique bar types.
    Format: calibre_length_hookLeft_hookRight
    """
    calibre = str(barra["calibre"])
    longitud = str(round(barra["length"], 2))

    ganchoI = ""
    ganchoD = ""

    if "gancho_izq" in barra and not barra["gancho_izq"]["longitud"] < 1e-3:
        if "gancho_der" not in barra:
            ganchoI = "G90"
        else:
            ganchoI = "GI90" if barra["gancho_izq"]["tipo"] == "90" else "GI180"
        ganchoI += "_" + str(round(barra["gancho_izq"]["longitud"] * 100, 0))

    if "gancho_izq" in barra and barra["gancho_izq"]["longitud"] < 1e-3:
        ganchoI = "C" if "gancho_der" not in barra else "CI"

    if "gancho_der" in barra and not barra["gancho_der"]["longitud"] < 1e-3:
        if "gancho_izq" not in barra:
            ganchoD = "G90"
        else:
            ganchoD = "GD90" if barra["gancho_der"]["tipo"] == "90" else "GD180"
        ganchoD += "_" + str(round(barra["gancho_der"]["longitud"] * 100, 0))

    if "gancho_der" in barra and barra["gancho_der"]["longitud"] < 1e-3:
        ganchoD = "C" if "gancho_izq" not in barra else "CD"

    return calibre + "_" + longitud + "_" + ganchoI + ganchoD


def calcular_peso_y_numero_barras(despiece: list, calibres: list) -> tuple:
    """Compute longitudinal bar weight, count, heads, connectors, figures.

    Returns:
        (weight, bar_count, heads_count, connectors_count,
         bars_by_diameter, heads_by_diameter, connectors_by_diameter, figures_list)
    """
    peso_total = 0
    barras_total = 0
    cabezas_total = 0
    conectores_total = 0

    dict_aux = {calibre["name"]: {"w": 0, "n": 0} for calibre in calibres}
    bars_por_calibre = copy.deepcopy(dict_aux)
    heads_por_calibre = copy.deepcopy(dict_aux)
    connectors_por_calibre = copy.deepcopy(dict_aux)
    figuras = []

    for barra in despiece:
        calibre = calibres[barra["calibre"]]

        n_barras = barra["factor"]
        longitud = barra["length"]

        peso_barras = n_barras * longitud * calibre["pesoLineal"]

        bars_por_calibre[calibre["name"]]["w"] += peso_barras
        bars_por_calibre[calibre["name"]]["n"] += n_barras

        if "empalme" in barra and "empalme_izq" in barra and barra["empalme"]:
            conectores_total += n_barras
            connectors_por_calibre[calibre["name"]]["n"] += n_barras

        if "gancho_izq" in barra and barra["gancho_izq"]["longitud"] < 1e-3:
            cabezas_total += n_barras
            heads_por_calibre[calibre["name"]]["n"] += n_barras

        if "gancho_der" in barra and barra["gancho_der"]["longitud"] < 1e-3:
            cabezas_total += n_barras
            heads_por_calibre[calibre["name"]]["n"] += n_barras

        peso_total += peso_barras
        barras_total += n_barras

        figuras.append(encontrar_figura_barra(barra))

    return (
        peso_total,
        barras_total,
        cabezas_total,
        conectores_total,
        bars_por_calibre,
        heads_por_calibre,
        connectors_por_calibre,
        figuras,
    )


# =============================================================================
# Complexity scoring (ported from complexity_scores.py)
# =============================================================================

def compute_score(value: float, max_value: float, scale_min: float, scale_max: float) -> float:
    """Compute normalized score within a scale range."""
    if max_value == 0:
        return scale_min
    return scale_min + ((value / max_value) * (scale_max - scale_min))


def add_complexity_scores(analysis_results: dict) -> None:
    """Add complexity_score and labor_hours_modifier to each element in-place.

    Weighted factors:
        vol_concreto (10%), total_rebar_weight (30%), bar_types (30%),
        bars_total (20%), surface_area (10%)
    """
    weights = {
        "vol_concreto": 0.10,
        "total_rebar_weight": 0.30,
        "bar_types": 0.30,
        "bars_total": 0.20,
        "surface_area": 0.10,
    }

    scales = {
        "vol_concreto": (1, 2),
        "total_rebar_weight": (1, 3),
        "bar_types": (1, 5),
        "bars_total": (1, 5),
        "surface_area": (1, 2),
    }

    max_values = {key: 0 for key in weights}

    for story_info in analysis_results["by_element"].values():
        for ele_info in story_info.values():
            for key in max_values:
                max_values[key] = max(max_values[key], ele_info[key])

    element_counter = 0
    complexity_sum = 0

    for story_info in analysis_results["by_element"].values():
        element_counter += len(story_info)
        for ele_info in story_info.values():
            complexity = (
                sum(
                    weights[key]
                    * compute_score(
                        ele_info[key], max_values[key], scales[key][0], scales[key][1]
                    )
                    for key in weights
                )
                * ele_info["complexity_modifier"]
            )
            ele_info["complexity_score"] = complexity
            complexity_sum += complexity

    complexity_average = complexity_sum / element_counter if element_counter > 0 else 0
    dispersion_factor = 0.5

    for story_info in analysis_results["by_element"].values():
        for ele_info in story_info.values():
            ele_info["labor_hours_modifier"] = (
                ele_info["complexity_score"] - complexity_average
            ) / dispersion_factor


# =============================================================================
# Result processing (ported from result_processor.py)
# =============================================================================

def _obtener_cantidad_pisos(grupos_niveles: list, piso: str) -> Tuple[int, list]:
    """Look up floor count for grouped floors.

    Returns (floor_count, sorted_floor_ids). If not grouped, returns (1, []).
    """
    for grupo in grupos_niveles:
        if grupo["id"] == piso:
            return grupo["cantidad_pisos"], sorted(grupo["niveles"])
    return 1, []


def _asignar_valores_por_diametro(by_element: dict, by_type: dict, cantidad_elementos: int) -> None:
    """Accumulate per-diameter values from element-level into aggregate-level."""
    for calibre, datos in by_type.items():
        datos["w"] += int(by_element[calibre]["w"] * cantidad_elementos)
        datos["n"] += by_element[calibre]["n"] * cantidad_elementos


def _asignar_resultados_en_objeto(
    obj: dict,
    element_quantity: float,
    bar_figures: list,
    element: dict,
) -> None:
    """Accumulate element results into a building-level or story-level object."""
    obj["stirrups"]["number_of_stirrups"] += element["stirrups_total"] * element_quantity
    obj["stirrups"]["total_stirrups_weight"] += int(element["stirrups_weight"] * element_quantity)

    _asignar_valores_por_diametro(
        element["stirrups_by_diameter"],
        obj["stirrups"]["by_diameter"],
        element_quantity,
    )

    obj["longitudinal_bars"]["number_of_bars"] += element["longitudinal_bars_total"] * element_quantity
    obj["longitudinal_bars"]["total_bar_weight"] += int(element["longitudinal_bars_weight"] * element_quantity)
    obj["longitudinal_bars"]["total_mechanical_connectors"] += element["connectors_total"] * element_quantity
    obj["longitudinal_bars"]["total_mechanical_heads"] += element["heads_total"] * element_quantity

    obj["bar_types"] = [*obj["bar_types"], *bar_figures]

    _asignar_valores_por_diametro(
        element["bars_by_diameter"],
        obj["longitudinal_bars"]["bars_by_diameter"],
        element_quantity,
    )

    _asignar_valores_por_diametro(
        element["heads_by_diameter"],
        obj["longitudinal_bars"]["heads_by_diameter"],
        element_quantity,
    )

    _asignar_valores_por_diametro(
        element["connectors_by_diameter"],
        obj["longitudinal_bars"]["connectors_by_diameter"],
        element_quantity,
    )


def process_single_cantidades(cantidades_data: dict, calibres_template: dict) -> dict:
    """Process a single cantidades.json dataset.

    This is the main processing loop: for each element, compute volume, stirrups,
    bars, figures, aggregate by story + globally, then add complexity scores.

    Args:
        cantidades_data: Loaded cantidades.json dict.
        calibres_template: Pre-built {name: {w:0, n:0}} template from calibres.

    Returns:
        Processed results dict with by_element, by_story, and building-level totals.
    """
    processed = {
        "longitudinal_bars": {
            "number_of_bars": 0,
            "total_bar_weight": 0,
            "total_mechanical_heads": 0,
            "total_mechanical_connectors": 0,
            "bars_by_diameter": copy.deepcopy(calibres_template),
            "heads_by_diameter": copy.deepcopy(calibres_template),
            "connectors_by_diameter": copy.deepcopy(calibres_template),
        },
        "stirrups": {
            "number_of_stirrups": 0,
            "total_stirrups_weight": 0,
            "by_diameter": copy.deepcopy(calibres_template),
        },
        "concrete_volume": 0,
        "detailed_elements": 0,
        "bar_types": [],
    }

    analysis = {"by_element": {}, "by_story": {}}

    calibres = cantidades_data["calibres"]

    for element in cantidades_data.get("elements", []):
        nombre = element.get("info", {}).get("nombre")
        if not nombre:
            continue

        cantidad_pisos, pisos_en_grupo = _obtener_cantidad_pisos(
            cantidades_data["grupos_niveles"], element.get("info", {}).get("piso")
        )

        processed["detailed_elements"] += 1

        for p in range(cantidad_pisos):
            if cantidad_pisos < 2:
                piso = element.get("info", {}).get("piso")
            else:
                piso = cantidades_data["nombres_planos"][pisos_en_grupo[p]]

            if piso not in analysis["by_element"]:
                analysis["by_element"][piso] = {}
                analysis["by_story"][piso] = {
                    "longitudinal_bars": {
                        "number_of_bars": 0,
                        "total_bar_weight": 0,
                        "total_mechanical_heads": 0,
                        "total_mechanical_connectors": 0,
                        "bars_by_diameter": copy.deepcopy(calibres_template),
                        "heads_by_diameter": copy.deepcopy(calibres_template),
                        "connectors_by_diameter": copy.deepcopy(calibres_template),
                    },
                    "stirrups": {
                        "number_of_stirrups": 0,
                        "total_stirrups_weight": 0,
                        "by_diameter": copy.deepcopy(calibres_template),
                    },
                    "concrete_volume": 0,
                    "bar_types": [],
                }

            analysis["by_element"][piso][nombre] = {}
            elem_results = analysis["by_element"][piso][nombre]

            # Concrete volume
            elem_volume = calcular_volumen_concreto(
                element.get("restrains", []), element["info"].get("seccion", [])
            )
            elem_results["vol_concreto"] = elem_volume

            # Complexity modifier: -12.5% per grouped floor, min 50%
            elem_results["complexity_modifier"] = max(1 - p * 0.125, 0.5)

            processed["concrete_volume"] += elem_volume
            analysis["by_story"][piso]["concrete_volume"] += elem_volume

            # Stirrups
            peso_est, num_est, est_por_calibre = calcular_peso_y_numero_estribos(
                element.get("estribos", []), calibres
            )
            elem_results["stirrups_weight"] = peso_est
            elem_results["stirrups_total"] = num_est
            elem_results["stirrups_by_diameter"] = est_por_calibre

            # Longitudinal bars
            (
                peso_barras, barras_total, cabezas_total, conectores_total,
                bars_por_cal, heads_por_cal, conn_por_cal, figuras,
            ) = calcular_peso_y_numero_barras(element.get("despiece", []), calibres)

            elem_results["longitudinal_bars_weight"] = peso_barras
            elem_results["longitudinal_bars_total"] = barras_total
            elem_results["heads_total"] = cabezas_total
            elem_results["connectors_total"] = conectores_total
            elem_results["bars_by_diameter"] = bars_por_cal
            elem_results["heads_by_diameter"] = heads_por_cal
            elem_results["connectors_by_diameter"] = conn_por_cal
            elem_results["bar_types"] = len(set(figuras))
            elem_results["surface_area"] = elem_volume * 4

            elem_results["total_rebar_weight"] = (
                elem_results["longitudinal_bars_weight"] + elem_results["stirrups_weight"]
            )
            elem_results["bars_total"] = (
                elem_results["longitudinal_bars_total"] + elem_results["stirrups_total"]
            )

            # Accumulate into building-level
            _asignar_resultados_en_objeto(
                processed, element["info"]["cantidad"], figuras, elem_results
            )

            # Accumulate into story-level
            _asignar_resultados_en_objeto(
                analysis["by_story"][piso],
                element["info"]["cantidad"],
                figuras,
                elem_results,
            )

    # Complexity scores
    add_complexity_scores(analysis)

    # Finalize story-level data
    for story_name, story_info in analysis["by_story"].items():
        story_info["concrete_volume"] = round(story_info["concrete_volume"], 1)
        story_info["bar_types"] = len(set(story_info["bar_types"]))
        story_info["story_height"] = cantidades_data["pisos"].get(story_name, 0)

    processed["concrete_volume"] = round(processed["concrete_volume"], 1)
    processed["by_element"] = analysis["by_element"]
    processed["by_story"] = analysis["by_story"]
    processed["bar_types"] = len(set(processed["bar_types"]))

    return processed


def process_multiple_cantidades(variants: Dict[str, dict]) -> Dict[str, dict]:
    """Process multiple cantidades datasets (one per variant).

    Args:
        variants: {variant_name: cantidades_data_dict}

    Returns:
        {variant_name: processed_results_dict}
    """
    results = {}
    for name, data in variants.items():
        calibres_template = {
            calibre["name"]: {"w": 0, "n": 0} for calibre in data["calibres"]
        }
        results[name] = process_single_cantidades(data, calibres_template)
    return results


# =============================================================================
# High-level API
# =============================================================================

def generate_structubim_json(
    project_paths: Dict[str, str],
    output_path: str,
    element_types: List[str] = None,
) -> Dict[str, Any]:
    """Generate processedAnalysis.json for StructuBim.

    Finds cantidades.json files for the given projects, processes reinforcement
    data (volumes, weights, complexity scores), and writes processedAnalysis.json.

    Args:
        project_paths: {variant_name: project_folder_path}
        output_path: Where to write processedAnalysis.json.
        element_types: e.g. ["vigas", "nervios"]. If None, tries to load
            whatever cantidades files exist.

    Returns:
        {success, output_path, variants: {name: {elements, bar_types, concrete_volume}},
         error (if any)}
    """
    variants_data = {}
    missing = []

    for name, path in project_paths.items():
        data = find_cantidades(path, element_types)
        if data is None:
            missing.append(name)
            continue
        variants_data[name] = data

    if not variants_data:
        return {
            "success": False,
            "error": f"No cantidades.json found for any project. Missing: {missing}",
        }

    processed = process_multiple_cantidades(variants_data)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(processed, f, ensure_ascii=False, sort_keys=True)

    summary = {}
    for name, data in processed.items():
        summary[name] = {
            "detailed_elements": data.get("detailed_elements", 0),
            "bar_types": data.get("bar_types", 0),
            "concrete_volume": data.get("concrete_volume", 0),
            "stories": list(data.get("by_story", {}).keys()),
        }

    result = {
        "success": True,
        "output_path": output_path,
        "variants": summary,
    }
    if missing:
        result["missing_projects"] = missing

    logger.info(f"Generated StructuBim JSON: {output_path} ({len(processed)} variant(s))")
    return result
