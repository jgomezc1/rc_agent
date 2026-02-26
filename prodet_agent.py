#!/usr/bin/env python3
"""
ProDet Agent - Orchestrates ProDet execution, output transfer, and data pipeline.

This module provides an LLM agent that automates the workflow:
  1. List/inspect ProDet projects
  2. Run ProDet to generate reinforcement output
  3. Copy the output .xlsx into rc_agent/data/
  4. Run the rebar data pipeline to produce JSON artifacts

Usage:
    from prodet_agent import ProDetAgent

    agent = ProDetAgent()
    response = agent.run("What projects are available?")
"""

import os
import sys
import shutil
import logging
import subprocess
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
# Path normalisation — allow the same .env to work on both WSL and native Win
# =============================================================================

def _normalize_path(path: str) -> str:
    """Convert between WSL (/mnt/c/...) and Windows (C:\\...) paths as needed."""
    if sys.platform == "win32":
        # Running on native Windows (e.g. Anaconda Prompt)
        # Convert WSL-style /mnt/X/... to X:\...
        if path.startswith("/mnt/") and len(path) > 5 and path[5] == "/":
            drive = path[5 - 1].upper()
            return drive + ":\\" + path[6:].replace("/", "\\")
    else:
        # Running on Linux / WSL
        # Convert Windows-style  X:\... to /mnt/x/...
        if len(path) >= 3 and path[1] == ":" and path[2] in ("\\", "/"):
            drive = path[0].lower()
            return "/mnt/" + drive + "/" + path[3:].replace("\\", "/")
    return path


# =============================================================================
# Configuration (from .env with defaults)
# =============================================================================

PRODET_ROOT = _normalize_path(os.environ.get(
    "PRODET_ROOT",
    r"C:\Users\jgomez\Dropbox\ProDes-Core",
))
PRODET_PROJECTS = _normalize_path(os.environ.get(
    "PRODET_PROJECTS",
    r"C:\Users\jgomez\Dropbox\prodet_locales",
))
PRODET_CONDA_ENV = os.environ.get("PRODET_CONDA_ENV", "ProDet-py39")

RC_AGENT_ROOT = os.path.dirname(os.path.abspath(__file__))
RC_AGENT_DATA = os.path.join(RC_AGENT_ROOT, "data")

# ProDet output filename produced by core/main.py for vigas
PRODET_OUTPUT_FILENAME = "Cantidades_Refuerzo_V.xlsx"

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
            has_output = os.path.isfile(os.path.join(project_path, PRODET_OUTPUT_FILENAME))

            projects.append({
                "name": entry,
                "path": project_path,
                "has_prodes": has_prodes,
                "has_output": has_output,
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
        has_output = os.path.isfile(os.path.join(project_path, PRODET_OUTPUT_FILENAME))

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


@tool
def run_prodet(
    project_name: str,
    element_type: str = "vigas",
    timeout_seconds: int = 900,
) -> Dict[str, Any]:
    """
    Run ProDet (ProDes-Core) for a given project.

    Invokes `python core/main.py "<project_path>/" <element_type>` from the
    PRODET_ROOT directory. Captures stdout/stderr and checks for the expected
    output file (Cantidades_Refuerzo_V.xlsx).

    ProDet runs can take several minutes for large projects. The default
    timeout is 900 seconds (15 minutes). Even if the process times out,
    the tool checks whether the output file was produced successfully.

    Args:
        project_name: Name of the project folder inside PRODET_PROJECTS.
        element_type: Element type to process (default: "vigas").
                      Options: vigas, columnas, muros, losas.
        timeout_seconds: Maximum time to wait for ProDet to finish (default: 900).

    Returns:
        Dictionary with success flag, stdout, stderr, output file path,
        and elapsed time.
    """
    cmd = []
    try:
        project_path = os.path.join(PRODET_PROJECTS, project_name)
        if not os.path.isdir(project_path):
            return {"error": f"Project folder not found: {project_path}"}

        if not os.path.isfile(os.path.join(project_path, "project.prodes")):
            return {"error": f"No project.prodes found in {project_path}. Project not ready."}

        if not os.path.isdir(PRODET_ROOT):
            return {"error": f"ProDet root not found: {PRODET_ROOT}"}

        main_script = os.path.join(PRODET_ROOT, "core", "main.py")
        if not os.path.isfile(main_script):
            return {"error": f"ProDet main.py not found: {main_script}"}

        # ProDet expects a trailing slash on the project path
        project_arg = project_path.rstrip("/\\") + os.sep

        # Use conda run to invoke ProDet in its own environment
        cmd = [
            "conda", "run", "-n", PRODET_CONDA_ENV,
            "python", "core/main.py", project_arg, element_type,
        ]
        logger.info(f"Running ProDet: {' '.join(cmd)} (cwd={PRODET_ROOT})")

        # Record mtime of any existing output so we can detect fresh writes
        output_path = os.path.join(project_path, PRODET_OUTPUT_FILENAME)
        old_mtime = os.path.getmtime(output_path) if os.path.isfile(output_path) else None

        start_time = datetime.now()
        timed_out = False
        try:
            result = subprocess.run(
                cmd,
                cwd=PRODET_ROOT,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            return_code = result.returncode
            stdout = result.stdout
            stderr = result.stderr
        except subprocess.TimeoutExpired as te:
            timed_out = True
            return_code = None
            stdout = te.stdout or ""
            stderr = te.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")

        elapsed = (datetime.now() - start_time).total_seconds()

        # Check if output file exists and is freshly written
        has_output = os.path.isfile(output_path)
        output_is_fresh = False
        if has_output:
            new_mtime = os.path.getmtime(output_path)
            output_is_fresh = (old_mtime is None) or (new_mtime > old_mtime)

        success = has_output and output_is_fresh and (return_code == 0 or timed_out)

        resp = {
            "success": success,
            "return_code": return_code,
            "timed_out": timed_out,
            "stdout": stdout[-2000:] if len(stdout) > 2000 else stdout,
            "stderr": stderr[-2000:] if len(stderr) > 2000 else stderr,
            "output_file": output_path if has_output else None,
            "output_exists": has_output,
            "output_is_fresh": output_is_fresh,
            "elapsed_seconds": round(elapsed, 1),
            "command": " ".join(cmd),
        }

        if timed_out and success:
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
def copy_output_to_rc_agent(
    project_name: str,
    output_filename: str = "reinforcement_solution.xlsx",
) -> Dict[str, Any]:
    """
    Copy ProDet output file to rc_agent's data directory.

    Copies Cantidades_Refuerzo_V.xlsx from the project folder to
    data/<output_filename>. If a file already exists at the destination,
    it is backed up with a timestamp suffix before overwriting.

    Args:
        project_name: Name of the project folder inside PRODET_PROJECTS.
        output_filename: Target filename in data/ (default: "reinforcement_solution.xlsx").

    Returns:
        Dictionary with source, destination, backup path (if any), and success flag.
    """
    try:
        project_path = os.path.join(PRODET_PROJECTS, project_name)
        source = os.path.join(project_path, PRODET_OUTPUT_FILENAME)

        if not os.path.isfile(source):
            return {
                "error": f"Output file not found: {source}. Run ProDet first.",
                "expected_file": source,
            }

        os.makedirs(RC_AGENT_DATA, exist_ok=True)
        destination = os.path.join(RC_AGENT_DATA, output_filename)

        # Back up existing file
        backup_path = None
        if os.path.isfile(destination):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name, ext = os.path.splitext(output_filename)
            backup_name = f"{name}_{timestamp}{ext}"
            backup_path = os.path.join(RC_AGENT_DATA, backup_name)
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
    timeout_seconds: int = 120,
) -> Dict[str, Any]:
    """
    Run the rc_agent rebar data pipeline on an xlsx file.

    Invokes run_rebar_pipeline.py to generate all 5 JSON artifacts:
    elements.json, elements_with_ci.json, elements_with_prod.json,
    work_packages.json, floor_schedule.json.

    Args:
        xlsx_path: Path to the input .xlsx file. Defaults to
                   data/reinforcement_solution.xlsx.
        timeout_seconds: Maximum time to wait for the pipeline (default: 120).

    Returns:
        Dictionary with success flag, stdout/stderr, and list of generated artifacts.
    """
    try:
        if xlsx_path is None:
            xlsx_path = os.path.join(RC_AGENT_DATA, "reinforcement_solution.xlsx")

        if not os.path.isfile(xlsx_path):
            return {"error": f"Input xlsx not found: {xlsx_path}"}

        pipeline_script = os.path.join(RC_AGENT_ROOT, "run_rebar_pipeline.py")
        if not os.path.isfile(pipeline_script):
            return {"error": f"Pipeline script not found: {pipeline_script}"}

        cmd = [sys.executable, pipeline_script, "-x", xlsx_path]
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
            artifact_path = os.path.join(RC_AGENT_DATA, artifact_name)
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
        }

    except subprocess.TimeoutExpired:
        return {"error": f"Pipeline timed out after {timeout_seconds} seconds"}
    except Exception as e:
        logger.error(f"Error running pipeline: {e}")
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
   input files, existing outputs, config summary, readiness status.

3. **run_prodet** — Execute ProDet for a project. Runs core/main.py with the
   specified element type (default: vigas). Captures output and checks for
   the expected Cantidades_Refuerzo_V.xlsx file.

4. **copy_output_to_rc_agent** — Copy the ProDet output xlsx into rc_agent's
   data/ folder. Automatically backs up any existing file before overwriting.

5. **run_data_pipeline** — Run the full rebar pipeline (reinforcement_parser ->
   complexity_index -> productivity -> work_packages -> floor_schedule) to
   generate the 5 JSON artifacts used by the other agents.

== USAGE GUIDELINES ==

- When a user asks to "run ProDet" or "process a project", follow the full workflow:
  1. First inspect the project to verify readiness
  2. Run ProDet
  3. If successful, copy the output
  4. Then run the data pipeline
  5. Report the results of each step

- If a user just asks "what projects are available", use list_projects only.

- If ProDet fails, show the stderr output and suggest checking the project files.

- If the pipeline fails, report which artifacts were generated and which failed.

- Always report file sizes and elapsed times so the user knows what happened.

== OUTPUT FORMAT ==

Present results clearly:

PROJECT STATUS
- Name: [project_name]
- Ready: Yes/No
- Input files: [list with status]

PRODET RUN
- Status: Success/Failed
- Output: [filename, size]
- Time: [elapsed seconds]

PIPELINE
- Status: Success/Failed
- Artifacts: [list with sizes]
- Time: [elapsed seconds]

NEXT STEPS
- What the user can do next (e.g., "Use the Procurement Agent to review the data")

== IMPORTANT ==

- Use tools for all operations — don't try to run commands manually
- Report errors clearly with actionable suggestions
- The default element_type is "vigas" (beams) — mention this to the user
- After a successful full run, remind the user they can now use the other agents
  (Procurement, Scheduling, Grouping) to analyze the processed data
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
        Run the ProDet agent on a user query.

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
