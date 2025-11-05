# src/precursor/scratchpad/utils.py
"""
Utility functions for the scratchpad package.

Includes helpers for:
- Project validation and metadata (via config/projects.yaml)
- Safe YAML loading for scratchpad context
"""

from __future__ import annotations

from typing import List, Dict
from precursor.config.loader import load_projects_yaml


def get_project_names(*, only_enabled: bool = True) -> List[str]:
    """
    Return the list of project names declared in config/projects.yaml.

    Parameters
    ----------
    only_enabled : bool
        If True, filter out projects with `enabled: false`.
    """
    cfg = load_projects_yaml()
    projects = cfg.get("projects", [])
    names: List[str] = []
    for proj in projects:
        name = proj.get("name")
        if not name:
            continue
        if only_enabled:
            if proj.get("enabled", True):
                names.append(name)
        else:
            names.append(name)
    return names


def is_valid_project(project_name: str) -> bool:
    """
    True iff the given project name appears in config/projects.yaml
    (regardless of enabled/disabled).
    """
    return project_name in get_project_names(only_enabled=False)


def is_project_enabled(project_name: str) -> bool:
    """
    True iff the project exists AND is not explicitly disabled.
    """
    cfg = load_projects_yaml()
    for proj in cfg.get("projects", []):
        if proj.get("name") == project_name:
            return proj.get("enabled", True)
    return False