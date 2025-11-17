# scratchpad/scratchpad_tools.py
"""
Scratchpad tool functions.

These are intentionally LLM-friendly and have rich docstrings, because
DSPy (or any other tool-calling layer) will read these to decide how to call
them.

They delegate to:
- scratchpad.store  (SQLite + platformdirs storage)
- scratchpad.render (to produce the human/LLM-facing markdown)
"""

from __future__ import annotations

import re
from typing import Optional, Literal, List

from precursor.scratchpad import store, render
from precursor.projects.utils import get_project_names


# ---------------------------------------------------------------------------
# private helpers
# ---------------------------------------------------------------------------

def _clean_proposition_text(text: str) -> str:
    t = str(text or "").strip()
    # strip trailing "(confidence: N)"
    while True:
        new_t = re.sub(r"\s*\(confidence\s*:\s*\d+\)\s*$", "", t, flags=re.IGNORECASE)
        if new_t == t:
            break
        t = new_t.strip()
    # strip leading "1. " / "- " / "• "
    t = re.sub(r"^\s*(?:\d+[\.)]\s+|[-•]\s+)", "", t)
    return t.strip()


# def _split_into_items(raw: str) -> List[str]:
#     raw = str(raw or "").strip()
#     if not raw:
#         return []

#     # 1) numbered list
#     parts = re.split(r"\s+\d+[\.)]\s+", raw)
#     parts = [p.strip() for p in parts if p and p.strip()]

#     # 2) Title: description lines
#     if len(parts) <= 1:
#         lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
#         title_colon = re.compile(r"^[A-Z][A-Za-z0-9 .,'/()&_-]*:\s+")
#         if sum(1 for ln in lines if title_colon.match(ln)) >= 2:
#             parts = lines

#     # 3) bullets
#     if len(parts) <= 1:
#         lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
#         bullet_re = re.compile(r"^[\-•]\s+")
#         if any(bullet_re.match(ln) for ln in lines):
#             tmp: List[str] = []
#             if lines and not bullet_re.match(lines[0]):
#                 tmp.append(lines[0])
#             tmp.extend([bullet_re.sub("", ln, count=1).strip() for ln in lines if bullet_re.match(ln)])
#             parts = tmp

#     # 4) semicolon-separated
#     if len(parts) <= 1 and " ; " in raw:
#         parts = [p.strip() for p in raw.split(" ; ") if p and p.strip()]

#     # 5) plain newline fallback
#     # If we STILL have just 1 part, but the user gave us multiple non-empty lines,
#     # treat each line as an item. This helps with LLM outputs like:
#     #   "Do X\nDo Y"
#     if len(parts) <= 1:
#         lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
#         if len(lines) > 1:
#             parts = lines

#     return parts if parts else [raw]


def _normalize_confidence(confidence: int | float | str) -> int:
    """Clamp confidence to [0, 10] and coerce weird LLM outputs."""
    try:
        c = int(confidence)
    except Exception:
        c = 0
    return max(0, min(10, c))


def _is_duplicate(
    project_name: str,
    section: str,
    message: str,
    subsection: Optional[str] = None,
) -> bool:
    """
    Check if an identical message already exists in the same project + section
    (+ optional subsection).
    """
    message_norm = (message or "").strip().lower()
    if not message_norm:
        return False

    # list entries for this project; filter in Python to keep logic simple
    entries = store.list_entries(project_name)
    for e in entries:
        if e["section"] != section:
            continue
        if section == "Project Resources":
            entry_sub = e.get("subsection") or "Other"
            if subsection and entry_sub != subsection:
                continue
        if (e["message"] or "").strip().lower() == message_norm:
            return True
    return False


# ---------------------------------------------------------------------------
# public LLM-facing tools
# ---------------------------------------------------------------------------

def append_to_scratchpad(
    project_name: str,
    section: str,
    proposal_text: str,
    confidence: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10] = 0,
    subsection: Optional[str] = None,
) -> str:
    """Add a brand new note/observation to the project scratchpad.

    Parameters
    ----------
    project_name : str
        Must match an existing project.
    section : str
        Should be one of:
          - "Ongoing Objectives"
          - "Completed Objectives"
          - "Suggestions"
          - "Notes"
          - "Project Resources"
          - "Next Steps"

        If you are adding a file/repo/folder/collaborator, use "Project Resources".
    proposal_text : str
        The text to add. This function is robust to numbered lists and bullets
        and may split the text into multiple propositions automatically.
    confidence : int
        0–10, how confident you are in this proposition.
    subsection : str, optional
        Only used when section == "Project Resources".
        Should be one of:
          - "Files"
          - "Repos"
          - "Folders"
          - "Core Collaborators"
          - "Other"

        Pass it as a separate argument, e.g.:
            append_to_scratchpad(
                project_name="My Research Project",
                section="Project Resources",
                proposal_text="research-project-repo",
                confidence=8,
                subsection="Repos",
            )

    Returns
    -------
    str
        An interpretable confirmation + the updated scratchpad.
    """
    store.init_db()

    # make sure the project exists in config
    if not store.is_valid_project(project_name):
        current = render.render_project_scratchpad(project_name)
        # Suggest known projects to help correct the name
        all_projects = get_project_names(only_enabled=False)
        suggestions = "\n".join(f"- {p}" for p in all_projects) if all_projects else "None configured."
        return (
            f"Unknown project '{project_name}'. Please add it to config/projects.yaml or fix the name.\n\n"
            f"Did you mean one of these instead?\n{suggestions}\n\n"
            f"== UPDATED SCRATCHPAD ==\n{current}"
        )

    confidence = _normalize_confidence(confidence)

    parts = [proposal_text]
    added = 0
    for part in parts:
        cleaned = _clean_proposition_text(part)
        if not cleaned:
            continue
        # avoid duplicates inside this project/section(/subsection)
        if _is_duplicate(project_name, section, cleaned, subsection=subsection):
            continue
        store.add_entry(
            project_name=project_name,
            section=section,
            message=cleaned,
            confidence=confidence,
            subsection=subsection,
        )
        added += 1

    updated = render.render_project_scratchpad(project_name)
    if added == 0:
        return "No new propositions added (duplicate or empty)\n\n== UPDATED SCRATCHPAD ==\n" + updated
    return f"Added {added} propositions to the project scratchpad\n\n== UPDATED SCRATCHPAD ==\n{updated}"


def remove_from_scratchpad(
    project_name: str,
    section: str,
    index: int,
    subsection: Optional[str] = None,
) -> str:
    """Remove a note/observation from the project scratchpad.

    Parameters
    ----------
    project_name : str
        Must match an existing project.
    section : str
        One of:
          - "Ongoing Objectives"
          - "Completed Objectives"
          - "Suggestions"
          - "Notes"
          - "Project Resources"
          - "Next Steps"
    index : int
        The 0-based display index **within that section** that you want to remove.
        This is the same index that appears in the rendered scratchpad like:
            [0] First item
            [1] Second item
    subsection : str, optional
        If the section is "Project Resources" you may also specify which subsection
        this index refers to (e.g. "Files"). If omitted, we look in the whole
        "Project Resources" section in display order.

    Returns
    -------
    str
        Confirmation + updated scratchpad.
    """
    store.init_db()

    if not store.is_valid_project(project_name):
        current = render.render_project_scratchpad(project_name)
        return (
            f"Unknown project '{project_name}'. Please add it to config/projects.yaml or fix the name.\n\n"
            f"== UPDATED SCRATCHPAD ==\n{current}"
        )

    ok = store.delete_entry_by_display_index(
        project_name=project_name,
        section=section,
        display_index=index,
        subsection=subsection,
    )
    updated = render.render_project_scratchpad(project_name)
    if not ok:
        return (
            f"Could not remove proposition {index} from section '{section}'\n\n"
            f"== UPDATED SCRATCHPAD ==\n{updated}"
        )
    return (
        f"Removed proposition {index} from section '{section}'\n\n"
        f"== UPDATED SCRATCHPAD ==\n{updated}"
    )


def edit_in_scratchpad(
    project_name: str,
    section: str,
    index: int,
    new_proposition_text: str,
    new_confidence: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10] = 0,
    subsection: Optional[str] = None,
) -> str:
    """Edit a note/observation in the project scratchpad.

    Parameters
    ----------
    project_name : str
        Must match an existing project.
    section : str
        One of:
          - "Ongoing Objectives"
          - "Completed Objectives"
          - "Suggestions"
          - "Notes"
          - "Project Resources"
          - "Next Steps"
    index : int
        The 0-based display index inside that section.
    new_proposition_text : str
        The updated text. This may itself contain a short list; in that case
        the first item will REPLACE the target entry and the remaining items
        will be APPENDED as new entries in the same section.
    new_confidence : int
        0–10, new confidence value.
    subsection : str, optional
        If editing inside "Project Resources", specify one of:
          - "Files"
          - "Repos"
          - "Folders"
          - "Core Collaborators"
          - "Other"

    Returns
    -------
    str
        Confirmation + updated scratchpad.
    """
    store.init_db()

    if not store.is_valid_project(project_name):
        current = render.render_project_scratchpad(project_name)
        return (
            f"Unknown project '{project_name}'. Please add it to config/projects.yaml or fix the name.\n\n"
            f"== UPDATED SCRATCHPAD ==\n{current}"
        )

    new_confidence = _normalize_confidence(new_confidence)

    parts = [new_proposition_text]
    parts = [_clean_proposition_text(p) for p in parts if _clean_proposition_text(p)]

    if not parts:
        updated = render.render_project_scratchpad(project_name)
        return "No edit performed (empty or invalid text)\n\n== UPDATED SCRATCHPAD ==\n" + updated

    primary = parts[0]
    ok = store.update_entry_by_display_index(
        project_name=project_name,
        section=section,
        display_index=index,
        new_message=primary,
        new_confidence=new_confidence,
        subsection=subsection,
    )

    if not ok:
        updated = render.render_project_scratchpad(project_name)
        return (
            f"Could not edit proposition {index} in section '{section}'\n\n"
            f"== UPDATED SCRATCHPAD ==\n{updated}"
        )

    # extra items become new entries (but don't add duplicates)
    extras = parts[1:]
    added_extras = 0
    for extra in extras:
        if not extra:
            continue
        if _is_duplicate(project_name, section, extra, subsection=subsection):
            continue
        store.add_entry(
            project_name=project_name,
            section=section,
            message=extra,
            confidence=new_confidence,
            subsection=subsection,
        )
        added_extras += 1

    updated = render.render_project_scratchpad(project_name)
    return (
        f"Edited proposition {index} in section '{section}' and added {added_extras} extra item(s)\n\n"
        f"== UPDATED SCRATCHPAD ==\n{updated}"
    )


def get_refreshed_scratchpad(project_name: str) -> str:
    """Get the refreshed project scratchpad.
    
    Parameters
    ----------
    project_name : str
        Must match an existing project.

    Returns
    -------
    str
        The current rendered scratchpad in markdown form.
    """
    store.init_db()

    if not store.is_valid_project(project_name):
        current = render.render_project_scratchpad(project_name)
        return (
            f"Unknown project '{project_name}'. Please add it to config/projects.yaml or fix the name.\n\n"
            f"== UPDATED SCRATCHPAD ==\n{current}"
        )

    return render.render_project_scratchpad(project_name)