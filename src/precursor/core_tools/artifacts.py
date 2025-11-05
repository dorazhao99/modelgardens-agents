# src/precursor/core_tools/artifacts.py
from __future__ import annotations
from typing import Optional

from precursor.scratchpad import store, render
from precursor.scratchpad.scratchpad_tools import append_to_scratchpad

PENDING_SECTION = "Agent Completed Tasks (Pending Review)"

def log_agent_artifact(
    project_name: str,
    title: str,
    summary: Optional[str] = None,
    artifact_uri: Optional[str] = None,
    task_completed: Optional[str] = None,
) -> str:
    """
    Record that an agent has completed a task or produced an artifact
    for a given project.

    Parameters
    ----------
    project_name : str
        The name of the project this artifact belongs to.
    title : str
        A short description of what was completed.
    summary : str, optional
        A longer explanation or context for the completed work.
    artifact_uri : str, optional
        A link or file path to the generated artifact.
    task_completed : str, optional
        If provided, must match a "Next Steps" item exactly.
        That item will be removed from "Next Steps" before logging
        the completion.

    Behavior
    --------
    - If `task_completed` is provided, remove that task from "Next Steps".
    - Always add a new entry under
      "Agent Completed Tasks (Pending Review)".
    - Confidence is always set to 10.

    Returns
    -------
    str
        A confirmation message and the updated scratchpad text.
    """
    store.init_db()

    # Try to remove a Next Step if given
    removed_note = ""
    if task_completed:
        next_steps = store.list_entries(project_name, section="Next Steps")
        wanted = task_completed.strip()
        found_index = None
        for idx, row in enumerate(next_steps):
            if (row.get("message") or "").strip() == wanted:
                found_index = idx
                break
        if found_index is not None:
            store.delete_entry_by_display_index(
                project_name=project_name,
                section="Next Steps",
                display_index=found_index,
            )
            removed_note = f"(removed Next Steps[{found_index}])"
        else:
            removed_note = "(no matching Next Steps found)"

    # Build the entry for the Pending Review section
    parts = [title]
    if summary:
        parts.append(summary)
    if artifact_uri:
        parts.append(f"(uri: {artifact_uri})")
    if task_completed:
        parts.append(f"(completed: {task_completed.strip()})")
    if removed_note:
        parts.append(removed_note)

    line = " - ".join(parts)

    append_to_scratchpad(
        project_name=project_name,
        section=PENDING_SECTION,
        proposal_text=line,
        confidence=10,
    )

    updated = render.render_project_scratchpad(project_name)
    return (
        "✅ Logged completed artifact to 'Agent Completed Tasks (Pending Review)'.\n\n"
        "== UPDATED SCRATCHPAD ==\n" + updated
    )