#!/usr/bin/env python3
"""
ProDet Agent - Orchestrates ProDet execution, output transfer, and data pipeline.

This module provides an LLM agent that automates the workflow:
  1. List/inspect ProDet projects
  2. Run ProDet to generate reinforcement output
  3. Copy the output .xlsx into rc_agent/projects/
  4. Run the rebar data pipeline to produce JSON artifacts

Usage:
    from prodet_agent import ProDetAgent

    agent = ProDetAgent()
    response = agent.run("What projects are available?")
"""

import json
import os
import sys
import shutil
import logging
import subprocess
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

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
# Path helpers (shared module)
# =============================================================================

from paths import RC_AGENT_ROOT, RC_AGENT_PROJECTS, project_dir, normalize_path

# Config agent helpers — used by _create_variant_config and re-exported as tools
from config_agent import (
    load_config_summary, update_config,
    _resolve_config_path, _get_nested, _set_nested,
    _maybe_convert_calibre, _LONG_HOMOG_MAP,
)

# =============================================================================
# Configuration (from .env with defaults)
# =============================================================================

PRODET_ROOT = normalize_path(os.environ.get(
    "PRODET_ROOT",
    r"C:\Users\jgomez\Dropbox\ProDes-Core",
))
PRODET_PROJECTS = normalize_path(os.environ.get(
    "PRODET_PROJECTS",
    RC_AGENT_PROJECTS,
))
PRODET_CONDA_ENV = os.environ.get("PRODET_CONDA_ENV", "ProDet-py39")

# ProDet output filenames by element type (key char from tipo[0])
PRODET_OUTPUT_FILENAMES = {
    "vigas": "Cantidades_Refuerzo_V.xlsx",
    "nervios": "Cantidades_Refuerzo_N.xlsx",
    "columnas": "Cantidades_Refuerzo_C.xlsx",
}

# Fallback patterns: try both upper and lowercase first letter
def _find_prodet_output(project_path: str, element_type: str) -> Optional[str]:
    """Find the ProDet output xlsx for a given element type, case-insensitive."""
    primary = PRODET_OUTPUT_FILENAMES.get(element_type)
    if primary:
        path = os.path.join(project_path, primary)
        if os.path.isfile(path):
            return path
    # Try opposite case
    letter = element_type[0]
    for case in (letter.upper(), letter.lower()):
        candidate = os.path.join(project_path, f"Cantidades_Refuerzo_{case}.xlsx")
        if os.path.isfile(candidate):
            return candidate
    return None

# Expected JSON artifacts from the rebar pipeline
PIPELINE_ARTIFACTS = [
    "elements.json",
    "elements_with_ci.json",
    "elements_with_prod.json",
    "work_packages.json",
    "floor_schedule.json",
]


# =============================================================================
# LangChain Tools
# =============================================================================

@tool
def list_projects() -> Dict[str, Any]:
    """
    Scan the ProDet projects folder for available projects.

    Lists all project folders inside PRODET_PROJECTS that contain a
    project.prodes file, along with basic status information.

    Returns:
        Dictionary with projects_dir, projects list (name, path, has_prodes,
        has_output, ready), and total count.
    """
    try:
        if not os.path.isdir(PRODET_PROJECTS):
            return {"error": f"Projects directory not found: {PRODET_PROJECTS}"}

        projects = []
        for entry in sorted(os.listdir(PRODET_PROJECTS)):
            project_path = os.path.join(PRODET_PROJECTS, entry)
            if not os.path.isdir(project_path):
                continue

            has_prodes = os.path.isfile(os.path.join(project_path, "project.prodes"))
            existing_outputs = [
                fname for fname in PRODET_OUTPUT_FILENAMES.values()
                if os.path.isfile(os.path.join(project_path, fname))
            ]

            projects.append({
                "name": entry,
                "path": project_path,
                "has_prodes": has_prodes,
                "has_output": len(existing_outputs) > 0,
                "existing_outputs": existing_outputs,
                "ready": has_prodes,
            })

        return {
            "projects_dir": PRODET_PROJECTS,
            "prodet_root": PRODET_ROOT,
            "projects": projects,
            "total": len(projects),
        }

    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        return {"error": str(e)}


@tool
def inspect_project(project_name: str) -> Dict[str, Any]:
    """
    Inspect a ProDet project folder in detail.

    Shows the 4 input files (project.prodes, geometry, loads, config)
    with sizes and modification dates, any existing output files, and
    a readiness assessment.

    Args:
        project_name: Name of the project folder inside PRODET_PROJECTS.

    Returns:
        Dictionary with project details, input files status, outputs,
        and readiness flag.
    """
    try:
        project_path = os.path.join(PRODET_PROJECTS, project_name)
        if not os.path.isdir(project_path):
            return {"error": f"Project folder not found: {project_path}"}

        def file_info(filepath: str) -> Dict[str, Any]:
            if not os.path.isfile(filepath):
                return {"exists": False}
            stat = os.stat(filepath)
            return {
                "exists": True,
                "size_bytes": stat.st_size,
                "size_kb": round(stat.st_size / 1024, 1),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }

        # Expected input files (ProDet naming convention: project.*)
        input_files = {
            "project.prodes": file_info(os.path.join(project_path, "project.prodes")),
            "project.geom": file_info(os.path.join(project_path, "project.geom")),
            "project.cargas": file_info(os.path.join(project_path, "project.cargas")),
            "project.config": file_info(os.path.join(project_path, "project.config")),
        }

        # Check for output files
        output_files = {}
        for fname in os.listdir(project_path):
            if fname.endswith((".xlsx", ".csv", ".json", ".log")):
                fpath = os.path.join(project_path, fname)
                if os.path.isfile(fpath):
                    output_files[fname] = file_info(fpath)

        has_prodes = input_files["project.prodes"].get("exists", False)
        existing_outputs = [
            fname for fname in PRODET_OUTPUT_FILENAMES.values()
            if os.path.isfile(os.path.join(project_path, fname))
        ]
        has_output = len(existing_outputs) > 0

        # Read config summary if available
        config_summary = None
        config_path = os.path.join(project_path, "project.config")
        if os.path.isfile(config_path):
            try:
                import json
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                config_summary = {
                    k: v for k, v in config_data.items()
                    if isinstance(v, (str, int, float, bool))
                }
            except Exception:
                config_summary = {"note": "Could not parse config.json"}

        return {
            "project_name": project_name,
            "project_path": project_path,
            "input_files": input_files,
            "output_files": output_files,
            "has_prodes": has_prodes,
            "has_output": has_output,
            "ready_to_run": has_prodes,
            "config_summary": config_summary,
        }

    except Exception as e:
        logger.error(f"Error inspecting project: {e}")
        return {"error": str(e)}


VALID_ELEMENT_TYPES = ("vigas", "nervios", "columnas")



# How often (seconds) to check for the output xlsx while ProDet runs
_POLL_INTERVAL = 2.0


def _run_prodet_single(
    project_path: str,
    element_type: str,
    timeout_seconds: int,
) -> Dict[str, Any]:
    """Run ProDet for a single element type. Internal helper.

    Launches ProDet as a background process and polls for the output xlsx.
    As soon as a fresh output file is detected the process is terminated
    so we don't wait for drawings/PDFs that aren't needed.
    """
    cmd = []
    try:
        main_script = os.path.join(PRODET_ROOT, "core", "main.py")
        if not os.path.isfile(main_script):
            return {"error": f"ProDet main.py not found: {main_script}"}

        project_arg = project_path.rstrip("/\\") + os.sep

        cmd = [
            "conda", "run", "-n", PRODET_CONDA_ENV,
            "python", "core/main.py", project_arg, element_type,
        ]
        logger.info(f"Running ProDet: {' '.join(cmd)} (cwd={PRODET_ROOT})")

        # Record mtime of any existing output so we can detect fresh writes
        existing_output = _find_prodet_output(project_path, element_type)
        old_mtime = os.path.getmtime(existing_output) if existing_output else None

        start_time = datetime.now()
        timed_out = False
        early_exit = False
        return_code = None

        proc = subprocess.Popen(
            cmd,
            cwd=PRODET_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            # Poll until the output file appears or we time out
            while True:
                elapsed = (datetime.now() - start_time).total_seconds()

                # Check if process finished on its own
                ret = proc.poll()
                if ret is not None:
                    return_code = ret
                    break

                # Check if a fresh output file has appeared
                output_path = _find_prodet_output(project_path, element_type)
                if output_path is not None:
                    new_mtime = os.path.getmtime(output_path)
                    if (old_mtime is None) or (new_mtime > old_mtime):
                        # Excel is ready — kill the process, we're done
                        early_exit = True
                        logger.info(
                            f"Output file detected after {elapsed:.1f}s, "
                            f"terminating ProDet process."
                        )
                        proc.terminate()
                        try:
                            proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait(timeout=5)
                        break

                # Check timeout
                if elapsed >= timeout_seconds:
                    timed_out = True
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
                    break

                time.sleep(_POLL_INTERVAL)

        except Exception:
            # Ensure cleanup on unexpected errors
            proc.kill()
            proc.wait()
            raise

        elapsed = (datetime.now() - start_time).total_seconds()

        # Collect whatever stdout/stderr was produced
        stdout = ""
        stderr = ""
        try:
            out, err = proc.communicate(timeout=5)
            stdout = out or ""
            stderr = err or ""
        except Exception:
            pass

        # Final check for output file
        output_path = _find_prodet_output(project_path, element_type)
        has_output = output_path is not None
        output_is_fresh = False
        if has_output:
            new_mtime = os.path.getmtime(output_path)
            output_is_fresh = (old_mtime is None) or (new_mtime > old_mtime)

        success = has_output and output_is_fresh

        resp = {
            "element_type": element_type,
            "success": success,
            "return_code": return_code,
            "timed_out": timed_out,
            "early_exit": early_exit,
            "stdout": stdout[-2000:] if len(stdout) > 2000 else stdout,
            "stderr": stderr[-2000:] if len(stderr) > 2000 else stderr,
            "output_file": output_path if has_output else None,
            "output_exists": has_output,
            "output_is_fresh": output_is_fresh,
            "elapsed_seconds": round(elapsed, 1),
            "command": " ".join(cmd),
        }

        if early_exit:
            resp["note"] = (
                f"Output xlsx detected after {elapsed:.1f}s — ProDet process "
                f"was terminated early (no need to wait for drawings/PDFs)."
            )
        elif timed_out and success:
            resp["note"] = (
                f"Process exceeded {timeout_seconds}s timeout but the output "
                f"file was produced successfully."
            )
        elif timed_out and not success:
            resp["error"] = (
                f"Process exceeded {timeout_seconds}s timeout and no fresh "
                f"output file was found. Consider increasing timeout_seconds."
            )

        return resp

    except Exception as e:
        logger.error(f"Error running ProDet: {e}")
        return {"error": str(e), "command": " ".join(cmd) if cmd else None}


@tool
def run_prodet(
    project_name: str,
    element_type: str = "vigas",
    timeout_seconds: int = 900,
) -> Dict[str, Any]:
    """
    Run ProDet (ProDes-Core) for a given project.

    Invokes `python core/main.py "<project_path>/" <element_type>` from the
    PRODET_ROOT directory using the ProDet conda environment.

    Each element type produces its own Excel output:
      - vigas   -> Cantidades_Refuerzo_V.xlsx
      - nervios -> Cantidades_Refuerzo_N.xlsx
      - columnas -> Cantidades_Refuerzo_C.xlsx

    ProDet runs can take several minutes for large projects. The default
    timeout is 900 seconds (15 minutes). Even if the process times out,
    the tool checks whether the output file was produced successfully.

    Note: Output types (drawings/PDFs vs Excel-only) are controlled by the
    gen_informe flag inside the project's project.config file, not by this tool.

    Args:
        project_name: Name of the project folder inside PRODET_PROJECTS.
        element_type: Element type to process. Options:
                      "vigas" (beams, default), "nervios" (joists),
                      "columnas" (columns), or "ambos" (runs vigas then nervios).
        timeout_seconds: Maximum time per run (default: 900). For "ambos",
                         this timeout applies to each run independently.

    Returns:
        Dictionary with success flag, stdout, stderr, output file path,
        and elapsed time. For "ambos", returns results for each run.
    """
    try:
        project_path = os.path.join(PRODET_PROJECTS, project_name)
        if not os.path.isdir(project_path):
            return {"error": f"Project folder not found: {project_path}"}

        if not os.path.isfile(os.path.join(project_path, "project.prodes")):
            return {"error": f"No project.prodes found in {project_path}. Project not ready."}

        if not os.path.isdir(PRODET_ROOT):
            return {"error": f"ProDet root not found: {PRODET_ROOT}"}

        # Handle "ambos" — run vigas then nervios sequentially
        if element_type == "ambos":
            from structubim_handler import copy_cantidades_after_run, generate_structubim_json
            results = {}
            all_success = True
            for etype in ("vigas", "nervios"):
                res = _run_prodet_single(project_path, etype, timeout_seconds)
                results[etype] = res
                if res.get("success"):
                    copy_cantidades_after_run(project_path, etype)
                else:
                    all_success = False
            ret = {
                "element_type": "ambos",
                "all_success": all_success,
                "runs": results,
            }
            # Auto-generate processedAnalysis.json for successful element types
            etypes_ok = [et for et, r in results.items() if r.get("success")]
            if etypes_ok:
                try:
                    ret["structubim"] = _auto_generate_structubim(project_name, etypes_ok)
                except Exception as sb_err:
                    logger.warning(f"StructuBim auto-generation failed: {sb_err}")
                    ret["structubim"] = {"success": False, "error": str(sb_err)}
            return ret

        if element_type not in VALID_ELEMENT_TYPES:
            return {
                "error": f"Invalid element_type '{element_type}'. "
                         f"Valid options: {', '.join(VALID_ELEMENT_TYPES)}, ambos."
            }

        result = _run_prodet_single(project_path, element_type, timeout_seconds)
        if result.get("success"):
            from structubim_handler import copy_cantidades_after_run
            copy_cantidades_after_run(project_path, element_type)
            try:
                result["structubim"] = _auto_generate_structubim(project_name, [element_type])
            except Exception as sb_err:
                logger.warning(f"StructuBim auto-generation failed: {sb_err}")
                result["structubim"] = {"success": False, "error": str(sb_err)}
        return result

    except Exception as e:
        logger.error(f"Error running ProDet: {e}")
        return {"error": str(e)}


@tool
def copy_output_to_rc_agent(
    project_name: str,
    element_type: str = "vigas",
    output_filename: str = "reinforcement_solution.xlsx",
) -> Dict[str, Any]:
    """
    Copy ProDet output file to rc_agent's projects directory.

    Finds the output xlsx for the given element type and copies it to
    projects/<project_name>/<output_filename>. If a file already exists at the destination,
    it is backed up with a timestamp suffix before overwriting.

    Args:
        project_name: Name of the project folder inside PRODET_PROJECTS.
        element_type: Which element type output to copy (default: "vigas").
                      Options: vigas, nervios, columnas.
        output_filename: Target filename in projects/<project_name>/ (default: "reinforcement_solution.xlsx").

    Returns:
        Dictionary with source, destination, backup path (if any), and success flag.
    """
    try:
        project_path = os.path.join(PRODET_PROJECTS, project_name)
        source = _find_prodet_output(project_path, element_type)

        if source is None:
            expected = PRODET_OUTPUT_FILENAMES.get(element_type, f"Cantidades_Refuerzo_?.xlsx")
            return {
                "error": f"Output file not found for element_type='{element_type}' "
                         f"in {project_path}. Expected: {expected}. Run ProDet first.",
            }

        data_dir = project_dir(project_name)
        destination = os.path.join(data_dir, output_filename)

        # Back up existing file
        backup_path = None
        if os.path.isfile(destination):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name, ext = os.path.splitext(output_filename)
            backup_name = f"{name}_{timestamp}{ext}"
            backup_path = os.path.join(data_dir, backup_name)
            shutil.copy2(destination, backup_path)
            logger.info(f"Backed up existing file to: {backup_path}")

        shutil.copy2(source, destination)
        logger.info(f"Copied {source} -> {destination}")

        dest_size = os.path.getsize(destination)

        return {
            "success": True,
            "source": source,
            "destination": destination,
            "backup": backup_path,
            "size_bytes": dest_size,
            "size_kb": round(dest_size / 1024, 1),
        }

    except Exception as e:
        logger.error(f"Error copying output: {e}")
        return {"error": str(e)}


@tool
def run_data_pipeline(
    xlsx_path: str = None,
    project_name: str = None,
    timeout_seconds: int = 120,
) -> Dict[str, Any]:
    """
    Run the rc_agent rebar data pipeline on an xlsx file.

    Invokes run_rebar_pipeline.py to generate all 5 JSON artifacts:
    elements.json, elements_with_ci.json, elements_with_prod.json,
    work_packages.json, floor_schedule.json.

    When project_name is given, artifacts are written to projects/<project_name>/
    instead of the default projects/ directory.

    Args:
        xlsx_path: Path to the input .xlsx file. Defaults to
                   projects/<project_name>/reinforcement_solution.xlsx (or
                   projects/reinforcement_solution.xlsx if no project).
        project_name: Optional project name. When set, the pipeline outputs
                      go to projects/<project_name>/.
        timeout_seconds: Maximum time to wait for the pipeline (default: 120).

    Returns:
        Dictionary with success flag, stdout/stderr, and list of generated artifacts.
    """
    try:
        data_dir = project_dir(project_name)

        if xlsx_path is None:
            xlsx_path = os.path.join(data_dir, "reinforcement_solution.xlsx")

        if not os.path.isfile(xlsx_path):
            return {"error": f"Input xlsx not found: {xlsx_path}"}

        pipeline_script = os.path.join(RC_AGENT_ROOT, "run_rebar_pipeline.py")
        if not os.path.isfile(pipeline_script):
            return {"error": f"Pipeline script not found: {pipeline_script}"}

        cmd = [sys.executable, pipeline_script, "-x", xlsx_path, "-d", data_dir]
        logger.info(f"Running pipeline: {' '.join(cmd)}")

        start_time = datetime.now()
        result = subprocess.run(
            cmd,
            cwd=RC_AGENT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        elapsed = (datetime.now() - start_time).total_seconds()

        # Check which artifacts were generated
        artifacts = {}
        for artifact_name in PIPELINE_ARTIFACTS:
            artifact_path = os.path.join(data_dir, artifact_name)
            if os.path.isfile(artifact_path):
                stat = os.stat(artifact_path)
                artifacts[artifact_name] = {
                    "exists": True,
                    "size_kb": round(stat.st_size / 1024, 1),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            else:
                artifacts[artifact_name] = {"exists": False}

        all_generated = all(a["exists"] for a in artifacts.values())

        return {
            "success": result.returncode == 0 and all_generated,
            "return_code": result.returncode,
            "stdout": result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
            "stderr": result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr,
            "elapsed_seconds": round(elapsed, 1),
            "artifacts": artifacts,
            "all_artifacts_generated": all_generated,
            "xlsx_path": xlsx_path,
            "data_dir": data_dir,
        }

    except subprocess.TimeoutExpired:
        return {"error": f"Pipeline timed out after {timeout_seconds} seconds"}
    except Exception as e:
        logger.error(f"Error running pipeline: {e}")
        return {"error": str(e)}


@tool
def generate_structubim_json_tool(
    project_names: str,
    output_dir: str = "",
    element_types: str = "vigas,nervios",
) -> Dict[str, Any]:
    """Generate processedAnalysis.json for StructuBim 3D visualizer.

    Finds cantidades.json files for the given projects, processes reinforcement
    data (volumes, weights, complexity scores), and produces processedAnalysis.json.
    Handles vigas+nervios merge automatically when type-specific files exist.

    Args:
        project_names: Comma-separated project names (e.g., "mokara,mokara_speed").
                       Each must be a subfolder under projects/.
        output_dir: Output directory (default: first project's folder).
        element_types: Element types to look for (default: "vigas,nervios").
                       Comma-separated.

    Returns:
        Dictionary with success flag, output file path, and per-variant summary
        (element count, bar types, concrete volume, story list).
    """
    from structubim_handler import generate_structubim_json

    try:
        names = [n.strip() for n in project_names.split(",") if n.strip()]
        if not names:
            return {"error": "No project names provided."}

        etypes = [t.strip() for t in element_types.split(",") if t.strip()]

        project_paths = {}
        for name in names:
            pdir = project_dir(name)
            if not os.path.isdir(pdir):
                return {"error": f"Project folder not found: {pdir}"}
            project_paths[name] = pdir

        out_dir = output_dir.strip() if output_dir.strip() else project_dir(names[0])
        out_path = os.path.join(out_dir, "processedAnalysis.json")

        return generate_structubim_json(project_paths, out_path, etypes)

    except Exception as e:
        logger.error(f"Error generating StructuBim JSON: {e}")
        return {"error": str(e)}


# =============================================================================
# Parametric Study Helpers
# =============================================================================

_COMPANION_FILES = ["project.prodes", "project.geom", "project.cargas"]


def _find_source_project(project_name: str) -> Optional[str]:
    """Detect the source project for a variant (e.g. 'supernovaA' for 'supernovaA_eco1').

    Tries progressively stripping '_suffix' segments from the right and checks
    whether the candidate is an existing project with a project.config file.
    Returns None if the project is itself a source (no parent found).
    """
    parts = project_name.split("_")
    for i in range(len(parts) - 1, 0, -1):
        candidate = "_".join(parts[:i])
        cdir = project_dir(candidate)
        if (
            candidate != project_name
            and os.path.isdir(cdir)
            and os.path.isfile(os.path.join(cdir, "project.config"))
        ):
            return candidate
    return None


def _collect_variant_family(
    source_name: str, element_types: List[str]
) -> Dict[str, str]:
    """Collect source + all variant project paths that have cantidades data.

    Scans for folders named ``{source_name}_*`` next to the source project.
    Returns ``{project_name: project_folder_path}`` for every project that
    has at least one cantidades file for the given element types.
    """
    from structubim_handler import find_cantidades

    family: Dict[str, str] = {}
    source_dir_path = project_dir(source_name)
    if find_cantidades(source_dir_path, element_types):
        family[source_name] = source_dir_path

    projects_root = os.path.dirname(source_dir_path)
    prefix = source_name + "_"
    try:
        entries = os.listdir(projects_root)
    except OSError:
        entries = []
    for entry in sorted(entries):
        if entry.startswith(prefix) and os.path.isdir(os.path.join(projects_root, entry)):
            vdir = project_dir(entry)
            if find_cantidades(vdir, element_types):
                family[entry] = vdir
    return family


def _auto_generate_structubim(
    project_name: str, element_types: List[str]
) -> Dict[str, Any]:
    """Generate a combined processedAnalysis.json for a project and all its variants.

    Always writes to the **source** project folder so there is a single file
    per project family, not one per variant.
    """
    from structubim_handler import generate_structubim_json

    source_name = _find_source_project(project_name) or project_name
    family = _collect_variant_family(source_name, element_types)
    if not family:
        return {"success": False, "error": "No cantidades data found for any variant"}
    source_dir_path = project_dir(source_name)
    return generate_structubim_json(
        family,
        os.path.join(source_dir_path, "processedAnalysis.json"),
        element_types,
    )


def _create_variant_config(
    source_project: str,
    suffix: str,
    changes: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a variant project folder with a modified config.

    Reads the source project's project.config, applies dot-path changes,
    writes the result to projects/<source>_<suffix>/project.config, and
    copies companion files (prodes, geom, cargas) if not already present.

    Returns a dict with success flag, variant_project name, and details.
    """
    try:
        source_config_path = _resolve_config_path(source_project)
        if not os.path.isfile(source_config_path):
            return {"error": f"Source config not found for project '{source_project}'"}

        with open(source_config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Apply changes
        applied = []
        errors = []
        for dot_path, new_value in changes.items():
            try:
                old_value = _get_nested(config, dot_path)
                new_value = _maybe_convert_calibre(new_value, dot_path)
                _set_nested(config, dot_path, new_value)
                applied.append({"path": dot_path, "old": old_value, "new": new_value})
            except KeyError as e:
                errors.append({"path": dot_path, "error": str(e)})

        if errors and not applied:
            return {"error": "No changes applied — all paths invalid", "invalid_paths": errors}

        # Create variant project folder
        variant_name = f"{source_project}_{suffix}"
        variant_dir = project_dir(variant_name)
        variant_config_path = os.path.join(variant_dir, "project.config")

        with open(variant_config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        # Copy companion files from source directory
        src_dir = os.path.dirname(source_config_path)
        copied = []
        for fname in _COMPANION_FILES:
            src_file = os.path.join(src_dir, fname)
            dst_file = os.path.join(variant_dir, fname)
            if os.path.isfile(src_file) and not os.path.isfile(dst_file):
                shutil.copy2(src_file, dst_file)
                copied.append(fname)

        result = {
            "success": True,
            "variant_project": variant_name,
            "variant_dir": variant_dir,
            "config_path": variant_config_path,
            "changes_applied": applied,
            "companion_files_copied": copied,
        }
        if errors:
            result["warnings"] = errors
        return result

    except Exception as e:
        logger.error(f"Error creating variant config: {e}")
        return {"error": str(e)}


@tool
def run_parametric_study(
    source_project: str,
    variants_json: str,
    element_type: str = "vigas",
    run_prodet_flag: bool = True,
    run_pipeline_flag: bool = True,
    timeout_per_run: int = 900,
) -> Dict[str, Any]:
    """
    Run a parametric study: create config variants and execute ProDet for each.

    Takes a source project, creates multiple variant projects with modified
    configs, and optionally runs ProDet + the data pipeline for each variant.
    This is a batch operation — one tool call handles the entire loop.

    Use this when the user wants to compare multiple config variations, e.g.
    different cutting lengths, calibre ranges, or detailing parameters.

    The variants_json parameter is a JSON list of objects, each with:
      - "suffix": short label appended to source project name (e.g. "lh10cm")
      - "changes": dict of dot-path keys to new values

    Example variants_json:
      [
        {"suffix": "lh10cm",  "changes": {"vigas.param_despiece.long_homog": 0}},
        {"suffix": "lh50cm",  "changes": {"vigas.param_despiece.long_homog": 1}},
        {"suffix": "lh100cm", "changes": {"vigas.param_despiece.long_homog": 2}}
      ]

    This creates projects/mokara_lh10cm/, projects/mokara_lh50cm/, etc.
    Each variant folder gets a modified project.config plus companion files.

    Error handling: continue-on-failure. If variant N fails, the error is
    logged and the study continues with variant N+1.

    Args:
        source_project: Name of the source project (e.g. "mokara").
        variants_json: JSON list of {suffix, changes} objects.
        element_type: Element type for ProDet runs (default: "vigas").
        run_prodet_flag: Whether to run ProDet for each variant (default: True).
        run_pipeline_flag: Whether to run the data pipeline after ProDet (default: True).
        timeout_per_run: Max seconds per ProDet run (default: 900).

    Returns:
        Dictionary with overall summary and per-variant status.
    """
    try:
        # Parse variants
        try:
            variants = json.loads(variants_json)
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON in variants_json: {e}"}

        if not isinstance(variants, list) or len(variants) == 0:
            return {"error": "variants_json must be a non-empty JSON list"}

        results = []
        total = len(variants)
        succeeded = 0
        failed = 0

        for i, variant in enumerate(variants, 1):
            suffix = variant.get("suffix", f"v{i}")
            changes = variant.get("changes", {})
            variant_name = f"{source_project}_{suffix}"

            logger.info(f"[Parametric {i}/{total}] Creating variant: {variant_name}")
            variant_result = {"suffix": suffix, "variant_project": variant_name, "steps": {}}

            # Step 1: Create variant config
            config_res = _create_variant_config(source_project, suffix, changes)
            variant_result["steps"]["create_config"] = config_res

            if not config_res.get("success"):
                variant_result["success"] = False
                variant_result["error"] = config_res.get("error", "Config creation failed")
                failed += 1
                results.append(variant_result)
                continue

            variant_dir = config_res["variant_dir"]

            # Step 2: Run ProDet
            if run_prodet_flag:
                logger.info(f"[Parametric {i}/{total}] Running ProDet for {variant_name}...")
                prodet_res = _run_prodet_single(variant_dir, element_type, timeout_per_run)
                variant_result["steps"]["run_prodet"] = prodet_res

                if not prodet_res.get("success"):
                    variant_result["success"] = False
                    variant_result["error"] = prodet_res.get("error", "ProDet run failed")
                    failed += 1
                    results.append(variant_result)
                    continue

                # Copy cantidades.json to type-specific file
                from structubim_handler import copy_cantidades_after_run
                copy_cantidades_after_run(variant_dir, element_type)

                # Step 3: Copy output (rename to reinforcement_solution.xlsx)
                output_path = prodet_res.get("output_file")
                if output_path and os.path.isfile(output_path):
                    dest = os.path.join(variant_dir, "reinforcement_solution.xlsx")
                    if os.path.abspath(output_path) != os.path.abspath(dest):
                        shutil.copy2(output_path, dest)
                    variant_result["steps"]["copy_output"] = {
                        "success": True,
                        "source": output_path,
                        "destination": dest,
                    }

            # Step 4: Run data pipeline
            if run_pipeline_flag and run_prodet_flag:
                xlsx_path = os.path.join(variant_dir, "reinforcement_solution.xlsx")
                if os.path.isfile(xlsx_path):
                    logger.info(f"[Parametric {i}/{total}] Running pipeline for {variant_name}...")
                    pipeline_script = os.path.join(RC_AGENT_ROOT, "run_rebar_pipeline.py")
                    try:
                        pipe_result = subprocess.run(
                            [sys.executable, pipeline_script, "-x", xlsx_path, "-d", variant_dir],
                            cwd=RC_AGENT_ROOT,
                            capture_output=True,
                            text=True,
                            timeout=120,
                        )
                        # Check artifacts
                        artifacts = {}
                        for artifact_name in PIPELINE_ARTIFACTS:
                            artifact_path = os.path.join(variant_dir, artifact_name)
                            artifacts[artifact_name] = os.path.isfile(artifact_path)

                        # Ensure dashboard was generated (pipeline wraps it
                        # in try/except so it can fail silently)
                        dashboard_path = os.path.join(variant_dir, "dashboard.html")
                        if not os.path.isfile(dashboard_path):
                            try:
                                from visualization import generate_dashboard
                                generate_dashboard(project_path=variant_dir, auto_open=False)
                            except Exception as dash_err:
                                logger.warning(f"Dashboard generation failed for {variant_name}: {dash_err}")
                        artifacts["dashboard.html"] = os.path.isfile(dashboard_path)

                        variant_result["steps"]["pipeline"] = {
                            "success": pipe_result.returncode == 0,
                            "return_code": pipe_result.returncode,
                            "artifacts": artifacts,
                            "stderr": pipe_result.stderr[-500:] if pipe_result.stderr else "",
                        }
                    except subprocess.TimeoutExpired:
                        variant_result["steps"]["pipeline"] = {
                            "success": False,
                            "error": "Pipeline timed out after 120s",
                        }

            # Determine overall variant success
            steps = variant_result["steps"]
            variant_result["success"] = all(
                s.get("success", False) for s in steps.values()
            )
            if variant_result["success"]:
                succeeded += 1
            else:
                failed += 1

            results.append(variant_result)

        # Auto-generate combined processedAnalysis.json for source + all successful variants
        ret = {
            "source_project": source_project,
            "element_type": element_type,
            "total_variants": total,
            "succeeded": succeeded,
            "failed": failed,
            "variants": results,
        }

        if run_prodet_flag:
            try:
                ret["structubim"] = _auto_generate_structubim(source_project, [element_type])
            except Exception as sb_err:
                logger.warning(f"StructuBim auto-generation failed: {sb_err}")
                ret["structubim"] = {"success": False, "error": str(sb_err)}

        return ret

    except Exception as e:
        logger.error(f"Error in parametric study: {e}")
        return {"error": str(e)}


# =============================================================================
# ProDet Agent
# =============================================================================

class ProDetAgent:
    """
    LLM agent that orchestrates ProDet execution and data pipeline processing.

    Automates the workflow: list projects -> inspect -> run ProDet ->
    copy output -> run data pipeline.
    """

    SYSTEM_PROMPT = """You are a construction engineering assistant that manages ProDet reinforcement design runs.

== WHAT YOU DO ==

You help users run ProDet (a reinforced concrete design tool) on project files and process the output through the rc_agent data pipeline. The typical workflow is:

1. **List projects** to see what's available
2. **Inspect a project** to verify input files are present
3. **Run ProDet** to generate the reinforcement output (.xlsx)
4. **Copy the output** to rc_agent's data directory
5. **Run the data pipeline** to produce JSON artifacts for the other agents

== AVAILABLE TOOLS ==

1. **list_projects** — Scan the projects folder for available ProDet projects.
   Shows which projects have a project.prodes file and are ready to run.

2. **inspect_project** — Get detailed info about a specific project:
   input files (project.prodes, project.geom, project.cargas, project.config),
   existing outputs, config summary, readiness status.

3. **run_prodet** — Execute ProDet for a project. Supports element types:
   - "vigas" (beams) — produces Cantidades_Refuerzo_V.xlsx
   - "nervios" (joists) — produces Cantidades_Refuerzo_N.xlsx
   - "columnas" (columns) — produces Cantidades_Refuerzo_C.xlsx
   - "ambos" — runs vigas then nervios sequentially
   Runs can take several minutes. If the process times out but the output
   file was produced, it still counts as success.

4. **copy_output_to_rc_agent** — Copy the ProDet output xlsx into rc_agent's
   projects/ folder. Specify element_type to pick the right file.
   Automatically backs up any existing file before overwriting.

5. **run_data_pipeline** — Run the full rebar pipeline (reinforcement_parser ->
   complexity_index -> productivity -> work_packages -> floor_schedule) to
   generate the 5 JSON artifacts used by the other agents.

6. **load_config_summary** — Read a project.config and return a curated
   summary of the ~30 engineering-relevant parameters. Pass either a full
   path or just the project name (e.g. "mokara").

7. **update_config** — Apply dot-path keyed changes to an existing config
   file. Automatically copies companion files when writing to a new folder.
   Example changes_json: {"vigas.param_despiece.long_homog": 1}

8. **run_parametric_study** — Batch tool: create multiple config variants
   and run ProDet + pipeline for each. ONE tool call handles the entire loop.
   Pass variants_json as a JSON list of {suffix, changes} objects.

9. **generate_structubim_json_tool** — Generate processedAnalysis.json for
   StructuBim 3D visualizer. Pass comma-separated project names and element
   types. Processes cantidades.json files (volumes, weights, bar types,
   complexity scores) and writes the output file. Upload the result to
   structu-bim.com for 3D reinforcement visualization.

== PARAMETRIC STUDY WORKFLOW ==

When a user asks to compare multiple configurations (e.g. different cutting
lengths, calibre ranges, or detailing parameters):

1. Decompose the request into a list of variants, each with a suffix and
   dot-path changes.
2. Call **run_parametric_study** ONCE with all variants.
3. Report per-variant results (config created, ProDet success, pipeline
   artifacts).

Example: "Create configs for mokara with cutting lengths 0.10m, 0.50m, 1.0m
and run ProDet for each for vigas" →

  run_parametric_study(
    source_project="mokara",
    variants_json='[
      {"suffix": "lh10cm",  "changes": {"vigas.param_despiece.long_homog": 0}},
      {"suffix": "lh50cm",  "changes": {"vigas.param_despiece.long_homog": 1}},
      {"suffix": "lh100cm", "changes": {"vigas.param_despiece.long_homog": 2}}
    ]',
    element_type="vigas"
  )

== LONG_HOMOG PARAMETER MAPPING ==

The long_homog parameter controls bar cutting length multiples:
  0 → 0.10 m (10 cm multiples)
  1 → 0.50 m (50 cm multiples)
  2 → 1.00 m (100 cm multiples)

This applies per element type: vigas.param_despiece.long_homog,
nervios.param_despiece.long_homog, columnas.param_despiece.long_homog.

== ELEMENT TYPES ==

Always ask the user what they want to solve if not specified:
- **vigas** (beams): Most common, default choice
- **nervios** (joists/ribs): For ribbed slabs
- **columnas** (columns): Column design
- **ambos** (both): Runs vigas + nervios sequentially

== OUTPUT TYPES ==

ProDet can generate different outputs (drawings, PDFs, Excel) depending on
the gen_informe setting in the project's project.config file. This agent
does not modify that setting — it runs ProDet with whatever config the
project already has. If the user wants to change output types, they should
edit project.config directly.

== USAGE GUIDELINES ==

- When a user asks to "run ProDet" or "process a project", ASK which
  element type they want (vigas, nervios, columnas, or ambos) unless
  they already specified.

- Follow the full workflow:
  1. First inspect the project to verify readiness
  2. Run ProDet with the requested element type
  3. If successful, copy the output (specify element_type)
  4. Then run the data pipeline
  5. Report the results of each step

- If a user just asks "what projects are available", use list_projects only.

- If ProDet fails, show the stderr output and diagnose the cause correctly:
  - **For variant/parametric projects** (names like mokara_eco1, supernovaA_lh50cm):
    The companion files (project.geom, project.cargas, project.prodes) are IMMUTABLE
    COPIES of the source project's seed files — they are never modified. Therefore
    geometry/loads/design data is always valid. Failures in variant runs are ALWAYS
    caused by the config changes being incompatible with the project's geometry.
    Diagnose which specific config parameter change caused the issue (e.g., a
    calibre range that doesn't include a beam's required diameter, or a parameter
    combination that ProDet cannot resolve for the given geometry).
    NEVER suggest "verify the project.geom file" for variant projects.
  - **For source/original projects**: Check project readiness (files present, valid).

- If the pipeline fails, report which artifacts were generated and which failed.

- Always report file sizes and elapsed times so the user knows what happened.

== OUTPUT FORMAT ==

Present results clearly:

PROJECT STATUS
- Name: [project_name]
- Ready: Yes/No
- Input files: [list with status]

PRODET RUN
- Element type: [vigas/nervios/columnas/ambos]
- Status: Success/Failed
- Output: [filename, size]
- Time: [elapsed seconds]

PIPELINE
- Status: Success/Failed
- Artifacts: [list with sizes]
- Time: [elapsed seconds]

NEXT STEPS
- What the user can do next (e.g., "Use the Procurement Agent to review the data")
- If cantidades.json exists, suggest generating StructuBim JSON for 3D visualization

== PROJECT-SPECIFIC DATA ==

All project outputs are stored in **projects/<project_name>/** subfolders.
For example, running ProDet for project "mokara" stores files in projects/mokara/.

- Always pass **project_name** to `copy_output_to_rc_agent` (this routes the
  xlsx to the right subfolder automatically).
- Always pass **project_name** to `run_data_pipeline` so JSON artifacts land
  in the same subfolder.
- After a successful run, remind the user that other agents (Procurement,
  Scheduling) should use project-specific paths, e.g.:
  - `projects/mokara/reinforcement_solution.xlsx`
  - `projects/mokara/work_packages.json`
  - `projects/mokara/floor_schedule.json`
- If the user sets an active project with `/project <name>` in the CLI, those
  paths are injected automatically.

== IMPORTANT ==

- Use tools for all operations — don't try to run commands manually
- Report errors clearly with actionable suggestions
- After a successful full run, remind the user they can now use the other agents
  (Procurement, Scheduling, Grouping) to analyze the processed data, pointing
  them to the project subfolder path (e.g. projects/mokara/)
"""

    def __init__(self, model_name: str = "claude-sonnet-4-6", temperature: float = 0.0):
        """Initialize the ProDet agent."""
        self.llm = ChatAnthropic(
            model=model_name,
            temperature=temperature,
        )
        self.tools = [
            list_projects,
            inspect_project,
            run_prodet,
            copy_output_to_rc_agent,
            run_data_pipeline,
            load_config_summary,
            update_config,
            run_parametric_study,
            generate_structubim_json_tool,
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
        max_iterations: int = 80,
    ) -> str:
        """
        Run the ProDet agent on a user query.

        Args:
            user_input: The user's question or request.
            chat_history: Optional list of previous messages for context.
            max_iterations: Maximum number of agent iterations (default: 80).
                           Higher than other agents because parametric studies
                           require many reasoning + tool-call turns
                           (config inspection, variant creation, ProDet runs,
                           result loading and comparison across variants).

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
    print("ProDet Agent - Direct Test")
    print("=" * 40)

    # Quick test: list projects without LLM
    result = list_projects.invoke({})
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Projects directory: {result['projects_dir']}")
        print(f"Total projects: {result['total']}")
        for p in result.get("projects", []):
            status = "READY" if p["ready"] else "NOT READY"
            output = " (has output)" if p["has_output"] else ""
            print(f"  - {p['name']}: {status}{output}")
