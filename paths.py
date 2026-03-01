"""Shared path constants for the RC Agent platform."""
import os
import sys

RC_AGENT_ROOT = os.path.dirname(os.path.abspath(__file__))
RC_AGENT_PROJECTS = os.path.join(RC_AGENT_ROOT, "projects")


def project_dir(project_name: str = None) -> str:
    """Return projects/<project_name>/, creating it if needed."""
    path = os.path.join(RC_AGENT_PROJECTS, project_name) if project_name else RC_AGENT_PROJECTS
    os.makedirs(path, exist_ok=True)
    return path


def normalize_path(path: str) -> str:
    """Convert between WSL (/mnt/c/...) and Windows (C:\\...) paths."""
    if sys.platform == "win32":
        if path.startswith("/mnt/") and len(path) > 5 and path[5] == "/":
            drive = path[5 - 1].upper()
            return drive + ":\\" + path[6:].replace("/", "\\")
    else:
        if len(path) >= 3 and path[1] == ":" and path[2] in ("\\", "/"):
            drive = path[0].lower()
            return "/mnt/" + drive + "/" + path[3:].replace("\\", "/")
    return path
