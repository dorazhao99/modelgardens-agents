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


# -----------------------------------------------------------------------------
# scratchpad rendering helpers
# -----------------------------------------------------------------------------

def render_project_scratchpad_text(project_name: str, *, max_chars: int = 8000) -> str:
    """
    Render a single project's scratchpad text, bounded to max_chars.

    This is useful for components that just need "the current scratchpad for X".
    """
    scratchpad_store.init_db()
    try:
        text = scratchpad_render.render_project_scratchpad(project_name)
    except Exception:
        return ""
    return text[:max_chars]


def render_all_scratchpads_for_projects(
    projects: List[Dict[str, Any]],
    *,
    max_chars_per_project: int = 4000,
) -> str:
    """
    Given a list of normalized projects (with "name"), render each project's
    scratchpad and stitch them together.

    We do NOT filter by enabled here anymore — callers can pass in the filtered
    list if they want. We render whatever they give us.
    """
    scratchpad_store.init_db()

    chunks: List[str] = []
    for p in projects:
        project_name = p["name"]
        try:
            text = scratchpad_render.render_project_scratchpad(project_name)
        except Exception:
            continue
        snippet = text[:max_chars_per_project]
        chunks.append(f"--- Scratchpad for {project_name} ---\n{snippet}")
    return "\n\n".join(chunks)


# -----------------------------------------------------------------------------
# scratchpad parsing helpers (for suggestions / next steps)
# -----------------------------------------------------------------------------

def extract_section(text: str, header: str) -> str:
    """
    Grab the text under a markdown header (e.g. "## Suggestions") until the next
    header. Returns "" if not found.
    """
    if not text:
        return ""
    parts = text.split(header, 1)
    if len(parts) < 2:
        return ""
    tail = parts[1]
    if "\n## " in tail:
        tail = tail.split("\n## ", 1)[0]
    return tail.strip()


def scratchpad_lines_to_actions(block: str) -> List[str]:
    """
    Our scratchpad renderer emits lines like:

        [0] Do the thing (confidence: 7)

    This turns those into just "Do the thing".
    """
    if not block:
        return []
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    actions: List[str] = []
    for ln in lines:
        # drop "[0] " prefix if present
        if "] " in ln:
            ln = ln.split("] ", 1)[1]
        # drop "(confidence: ...)" suffix if present
        if " (confidence:" in ln:
            ln = ln.split(" (confidence:", 1)[0]
        ln = ln.strip()
        if ln:
            actions.append(ln)
    return actions


def extract_actions_from_scratchpad(scratchpad_text: str) -> List[str]:
    """
    Convenience: pull actions from both Suggestions and Next Steps.
    """
    suggestions_block = extract_section(scratchpad_text, "## Suggestions")
    next_steps_block = extract_section(scratchpad_text, "## Next Steps")

    actions: List[str] = []
    actions.extend(scratchpad_lines_to_actions(suggestions_block))
    actions.extend(scratchpad_lines_to_actions(next_steps_block))
    return actions