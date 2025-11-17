# src/precursor/scratchpad/render.py
"""
Render a project's scratchpad from the SQLite store into a Markdown-like
string that is easy for an LLM (and a human) to read.

This is the view layer:
- persistence:  precursor.scratchpad.store
- structure:    precursor.scratchpad.schema
- project meta: precursor.config.loader (projects.yaml)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from collections import defaultdict

from precursor.scratchpad import store
from precursor.scratchpad.schema import PROJECT_SECTIONS, PROJECT_RESOURCE_SUBSECTIONS
from precursor.config.loader import load_projects_yaml


# ---------------------------------------------------------------------------
# project metadata
# ---------------------------------------------------------------------------

def _get_project_meta(project_name: str) -> Dict[str, Any]:
    """
    Look up project metadata (name, description, enabled) from config/projects.yaml.

    If the project isn't found, we return a sensible fallback so rendering does
    not fail.
    """
    cfg = load_projects_yaml()
    projects = cfg.get("projects", []) if isinstance(cfg, dict) else []
    for p in projects:
        if p.get("name") == project_name:
            return {
                "name": p.get("name", project_name),
                "description": (p.get("description") or "").strip(),
                "enabled": bool(p.get("enabled", True)),
            }

    # fallback
    return {
        "name": project_name,
        "description": "",
        "enabled": True,
    }


# ---------------------------------------------------------------------------
# formatting helpers
# ---------------------------------------------------------------------------

def _format_entry(idx: int, message: str, confidence: Optional[int]) -> str:
    """
    Standard line format used everywhere:

        [0] some text (confidence: 7)
    """
    if confidence is None:
        confidence = 0
    return f"[{idx}] {message} (confidence: {confidence})"


def _group_entries_by_section(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group rows by section name.
    """
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        grouped[r["section"]].append(r)
    return grouped


def _render_project_resources(all_rows: List[Dict[str, Any]]) -> str:
    """
    Render the "Project Resources" section with subsections, e.g.

    ## Project Resources
    ### Files
    [0] ...
    ### Repos
    [0] ...
    """
    resources = [r for r in all_rows if r["section"] == "Project Resources"]
    if not resources:
        return "None"

    # group by subsection; default to "Other"
    by_sub: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in resources:
        sub = r.get("subsection") or "Other"
        by_sub[sub].append(r)

    lines: List[str] = []
    for sub in PROJECT_RESOURCE_SUBSECTIONS:
        sub_rows = by_sub.get(sub, [])
        if not sub_rows:
            # we *could* skip empty subsections, but in your earlier examples
            # you liked seeing the structure, so we show them with "None".
            lines.append(f"### {sub}")
            lines.append("None")
            lines.append("")
            continue

        lines.append(f"### {sub}")
        for idx, row in enumerate(sub_rows):
            lines.append(_format_entry(idx, row["message"], row.get("confidence", 0)))
        lines.append("")

    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# public renderer
# ---------------------------------------------------------------------------

def render_project_scratchpad(project_name: str) -> str:
    """
    Render a single project's scratchpad to a Markdown-like string.

    This mirrors your original in-memory layout so that LLMs can say
    "edit Notes index 1" and we can map that back to the DB using
    display-order indices.
    """
    # ensure DB exists
    store.init_db()

    # if the project itself isn't valid we don't want to explode
    if not store.is_valid_project(project_name):
        return f"# {project_name}\n\n(Project not found in config/projects.yaml)\n"

    # load meta for description
    meta = _get_project_meta(project_name)
    project_desc = meta.get("description") or ""

    # fetch all active entries for this project
    rows = store.list_entries(project_name)
    grouped = _group_entries_by_section(rows)

    out: List[str] = []
    out.append(f"# {project_name}")
    if project_desc:
        out.append("")
        out.append(project_desc)
    out.append("")

    # render sections in canonical order
    for section in PROJECT_SECTIONS:
        if section == "Project Resources":
            out.append("## Project Resources")
            out.append(_render_project_resources(rows))
            out.append("")
            continue

        # BEGIN TEMP_DISABLE_SELECTED_SECTIONS
        # Temporarily disable rendering of several sections:
        # - Next Steps
        # - Ongoing Objectives
        # - Completed Objectives
        # - Suggestions
        # - Notes
        # To re-enable, remove or comment out this conditional block.
        if section in {"Next Steps", "Ongoing Objectives", "Completed Objectives", "Suggestions", "Notes"}:
            continue
        # END TEMP_DISABLE_SELECTED_SECTIONS

        out.append(f"## {section}")
        sec_rows = grouped.get(section, [])
        if not sec_rows:
            out.append("None")
        else:
            for idx, row in enumerate(sec_rows):
                out.append(_format_entry(idx, row["message"], row.get("confidence", 0)))
        out.append("")

    # final string
    return "\n".join(out).rstrip() + "\n"