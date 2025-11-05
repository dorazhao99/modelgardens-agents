# scratchpad/projects_config.py
"""
Project configuration loader.

Reads `config/projects.yaml` and exposes helpers to:
- list all projects
- list only agent-enabled projects
- get description for a project
- validate project names
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


DEFAULT_PROJECTS_PATH = Path("config/projects.yaml")


def load_projects_config(path: Path | str = DEFAULT_PROJECTS_PATH) -> List[Dict[str, Any]]:
    """
    Load the projects configuration file.

    Parameters
    ----------
    path : Path | str
        Path to the YAML file. Defaults to config/projects.yaml.

    Returns
    -------
    list[dict]
        A list of project dictionaries with keys:
          - name (str)
          - description (str, optional)
          - agent_enabled (bool, optional)
    """
    p = Path(path)
    if not p.exists():
        # it's OK to return empty; upstream code can decide how strict to be
        return []
    with p.open("r") as f:
        data = yaml.safe_load(f) or {}
    return data.get("projects", [])


def list_all_project_names() -> List[str]:
    """
    Return all project names defined in the config (enabled or not).
    """
    return [p["name"] for p in load_projects_config()]


def list_agent_enabled_project_names() -> List[str]:
    """
    Return only those project names for which agent_enabled is True
    (or missing, which we treat as True).
    """
    names: List[str] = []
    for proj in load_projects_config():
        enabled = proj.get("agent_enabled", True)
        if enabled:
            names.append(proj["name"])
    return names


def get_project_description(project_name: str) -> Optional[str]:
    """
    Return the description for a project if present.
    """
    for proj in load_projects_config():
        if proj["name"] == project_name:
            return proj.get("description")
    return None


def is_valid_project(project_name: str) -> bool:
    """
    Check whether a project name is defined in the config at all.
    """
    return project_name in list_all_project_names()


def is_agent_enabled(project_name: str) -> bool:
    """
    Check whether agents should operate on this project.

    Returns
    -------
    bool
        True if the project is defined and either has agent_enabled=True
        or omits the field. False if agent_enabled=False or project missing.
    """
    for proj in load_projects_config():
        if proj["name"] == project_name:
            return proj.get("agent_enabled", True)
    return False