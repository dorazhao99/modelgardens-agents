# src/precursor/scratchpad/utils.py
"""
Scratchpad-specific helpers.

Keeps logic that needs the scratchpad store/render close to the scratchpad
package (instead of putting it in the classifier).
"""

from __future__ import annotations

from typing import Any, Dict, List

from precursor.scratchpad import store as scratchpad_store
from precursor.scratchpad import render as scratchpad_render


def render_all_scratchpads_for_projects(
    projects: List[Dict[str, Any]],
    *,
    max_chars_per_project: int = 4000,
) -> str:
    """
    Given a list of normalized projects (with "name" and "enabled"),
    render each enabled project's scratchpad and stitch them together.

    Any project that doesn't have a scratchpad yet is skipped.

    This is the thing the project classifier wants.
    """
    scratchpad_store.init_db()

    chunks: List[str] = []
    for p in projects:
        project_name = p["name"]
        text = scratchpad_render.render_project_scratchpad(project_name)
        snippet = text[:max_chars_per_project]
        chunks.append(f"--- Scratchpad for {project_name} ---\n{snippet}")
    return "\n\n".join(chunks)