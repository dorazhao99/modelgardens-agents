# src/precursor/projects/utils.py
"""
General project utilities.

These sit above `precursor.config.loader` (which only loads YAML)
and provide a normalized view of projects for other components.
"""

from __future__ import annotations

from typing import Any, Dict, List

from precursor.config.loader import load_projects_yaml


def load_projects_normalized(*, only_enabled: bool = False) -> List[Dict[str, Any]]:
    """
    Load projects from config and normalize shape.

    Returns a list like:
        [
          {
            "name": "Background Agents",
            "description": "Long-running agents ...",
            "agent_enabled": True,
          },
          ...
        ]

    Parameters
    ----------
    only_enabled : bool
        If True, return only projects with enabled == True.
    """
    cfg = load_projects_yaml() or {}
    raw = cfg.get("projects", []) or []
    out: List[Dict[str, Any]] = []
    for p in raw:
        name = (p.get("name") or "").strip()
        if not name:
            continue
        agent_enabled = bool(p.get("agent_enabled", True))
        if only_enabled and not agent_enabled:
            continue
        out.append(
            {
                "name": name,
                "description": (p.get("description") or "").strip(),
                "agent_enabled": agent_enabled,
            }
        )
    return out


def get_project_names(*, only_enabled: bool = True) -> List[str]:
    """
    Return just the names.
    """
    projects = load_projects_normalized(only_enabled=only_enabled)
    return [p["name"] for p in projects]


def is_valid_project(project_name: str) -> bool:
    """
    True iff the given project name appears in config/projects.yaml.
    """
    return project_name in get_project_names(only_enabled=False)


def is_project_enabled(project_name: str) -> bool:
    """
    True iff the project exists AND is enabled.
    """
    projects = load_projects_normalized(only_enabled=False)
    for p in projects:
        if p["name"] == project_name:
            return p.get("enabled", True)
    return False


def projects_to_labeled_list(projects: List[Dict[str, Any]]) -> List[str]:
    """
    Turn normalized projects into the richer list the classifier wants:

        ["Project A: desc...", "Project B: desc...", ...]

    Disabled projects are skipped.
    """
    result: List[str] = []
    for p in projects:
        if not p.get("enabled", True):
            continue
        name = p["name"]
        desc = p.get("description") or ""
        if desc:
            result.append(f"{name}: {desc}")
        else:
            result.append(name)
    return result