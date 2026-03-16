"""Shared path constants for the RC Agent platform."""
import os
import re
import sys
from typing import Dict, List

RC_AGENT_ROOT = os.path.dirname(os.path.abspath(__file__))
RC_AGENT_PROJECTS = os.path.join(RC_AGENT_ROOT, "projects")

def project_dir(project_name: str = None) -> str:
    """Return projects/<project_name>/, creating it if needed."""
    path = os.path.join(RC_AGENT_PROJECTS, project_name) if project_name else RC_AGENT_PROJECTS
    os.makedirs(path, exist_ok=True)
    return path


def base_project_name(folder_name: str, projects_dir: str = None) -> str:
    """Extract the base project name by progressively stripping _suffix segments.

    Tries stripping trailing underscore-separated segments and checks whether
    the candidate is an existing project folder. Falls back to regex patterns
    for known suffixes (_v\\d+, _sol_*) if no folder match is found.

    Examples (assuming mokara/ exists):
        mokara           -> mokara
        mokara_v1        -> mokara
        mokara_lh50cm    -> mokara
        mokara_sol_balanced -> mokara
        supernovaA       -> supernovaA
    """
    pdir = projects_dir or RC_AGENT_PROJECTS

    # Progressive stripping: try removing trailing _segments until we find an
    # existing project folder that contains project.config (i.e. a source project)
    parts = folder_name.split("_")
    if len(parts) > 1 and os.path.isdir(pdir):
        for i in range(len(parts) - 1, 0, -1):
            candidate = "_".join(parts[:i])
            candidate_dir = os.path.join(pdir, candidate)
            if os.path.isdir(candidate_dir) and os.path.isfile(
                os.path.join(candidate_dir, "project.config")
            ):
                return candidate

    # Fallback: regex for known variant patterns
    stripped = re.sub(r"(_v\d+|_sol_.+)$", "", folder_name)
    return stripped


def list_project_families(projects_dir: str = None) -> Dict[str, List[str]]:
    """Group project folders by their base name.

    Returns a dict mapping base_name -> sorted list of folder names.
    E.g. {"mokara": ["mokara", "mokara_v1", "mokara_v2", "mokara_sol_balanced"],
          "supernovaA": ["supernovaA"]}
    """
    pdir = projects_dir or RC_AGENT_PROJECTS
    if not os.path.isdir(pdir):
        return {}
    families: Dict[str, List[str]] = {}
    for entry in sorted(os.listdir(pdir)):
        if os.path.isdir(os.path.join(pdir, entry)):
            base = base_project_name(entry, pdir)
            families.setdefault(base, []).append(entry)
    return families


def resolve_project_family(name: str, projects_dir: str = None) -> List[str]:
    """Given a name, return all project folders that belong to the same family.

    If *name* matches an exact folder, returns that folder's family.
    If *name* matches a base name (no exact folder), returns all variants.
    Returns empty list if nothing matches.
    """
    pdir = projects_dir or RC_AGENT_PROJECTS
    if not os.path.isdir(pdir):
        return []

    families = list_project_families(pdir)
    base = base_project_name(name, pdir)

    if base in families:
        return families[base]

    return []


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
