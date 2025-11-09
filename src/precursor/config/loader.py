# src/precursor/config/loader.py
"""
Config loader utilities.

This module is intentionally small: it just knows how to find and load the
YAML config files that live in `src/precursor/config/`, or alternative
locations specified via environment variables.

Higher-level logic (e.g. "is this project valid?") should live closer to the
consumer — for example, `precursor.scratchpad.utils` for scratchpad-related
queries.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml


# ---------------------------------------------------------------------------
# path resolution utilities
# ---------------------------------------------------------------------------

def _package_config_dir() -> Path:
    """
    Return the default path to the local config directory inside the package.
    We assume this file lives at: src/precursor/config/loader.py
    """
    return Path(__file__).resolve().parent


def _resolve_yaml_path(filename: str, env_var: str | None = None) -> Path:
    """
    Determine the YAML path according to priority:

    1. If an environment variable is provided and set (e.g. PRECURSOR_PROJECTS_FILE),
       use that path.
    2. Otherwise, fall back to the package's default config dir.
    """
    if env_var:
        env_value = os.getenv(env_var)
        if env_value:
            return Path(env_value).expanduser().resolve()
    return _package_config_dir() / filename


def _load_yaml(path: Path) -> Dict[str, Any]:
    """
    Load a YAML file from the given path.
    Raises FileNotFoundError if the file is missing.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ---------------------------------------------------------------------------
# public config loaders
# ---------------------------------------------------------------------------

def load_projects_yaml() -> Dict[str, Any]:
    """
    Load `projects.yaml`, using PRECURSOR_PROJECTS_FILE if set.

    Expected shape:
    {
        "projects": [
            {
                "name": "AutoMetrics Release",
                "description": "...",
                "enabled": true   # optional
            },
            ...
        ]
    }
    """
    path = _resolve_yaml_path("projects.yaml", env_var="PRECURSOR_PROJECTS_FILE")
    return _load_yaml(path)


def load_user_yaml() -> Dict[str, Any]:
    """
    Load `user.yaml`, using PRECURSOR_USER_FILE if set.

    Expected shape:
    {
        "name": "Michael Ryan",
        "description": "I am a CS PhD student ..."
    }
    """
    path = _resolve_yaml_path("user.yaml", env_var="PRECURSOR_USER_FILE")
    return _load_yaml(path)


def load_mcp_servers_yaml() -> Dict[str, Any]:
    """
    Load `mcp_servers.yaml`, using PRECURSOR_MCP_SERVERS_FILE if set.

    This file can declare which MCP servers to load or toggle.
    """
    path = _resolve_yaml_path("mcp_servers.yaml", env_var="PRECURSOR_MCP_SERVERS_FILE")
    return _load_yaml(path)


# ---------------------------------------------------------------------------
# convenience helpers
# ---------------------------------------------------------------------------

def get_project_names(only_enabled: bool = True) -> list[str]:
    """
    Return a list of project names, optionally filtering to only enabled ones.
    """
    cfg = load_projects_yaml()
    projects = cfg.get("projects", [])
    names: list[str] = []
    for p in projects:
        if only_enabled and not p.get("enabled", True):
            continue
        name = p.get("name")
        if name:
            names.append(name)
    return names


def get_user_name() -> str:
    """
    Return the user name from user.yaml.
    """
    cfg = load_user_yaml()
    return cfg.get("name", "")


def get_user_description() -> str:
    """
    Return the user description from user.yaml.
    """
    cfg = load_user_yaml()
    return cfg.get("description", "")

def get_user_agent_goals() -> str:
    """
    Return the user's agent-goals/preferences from user.yaml.
    """
    cfg = load_user_yaml()
    return cfg.get("agent_goals", "")

def get_user_profile() -> str:
    """
    Return the user profile from user.yaml.
    """
    cfg = load_user_yaml()
    name = cfg.get("name", "")
    description = cfg.get("description", "")
    agent_goals = cfg.get("agent_goals", "")
    parts: list[str] = []
    if name:
        parts.append(f"Name: {name}")
    if description:
        parts.append(f"Description: {description}")
    if agent_goals:
        parts.append(f"Agent Goals (Things this user wants the agent to focus on; not exhaustive): {agent_goals}")
    return "\n".join(parts)