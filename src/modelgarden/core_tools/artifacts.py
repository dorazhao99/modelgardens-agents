"""
Artifacts tool.

Record agent-created artifacts into the project's scratchpad using a single line
message and **hidden metadata**. The visible message is concise (short_summary + URI);
the longer operational write-up goes into `metadata` (not rendered).

Section used:
  - "Agent Completed Tasks (Pending Review)"

Docstring clarity matters for DSPy: include precise argument semantics.
"""

# from __future__ import annotations
# from typing import Optional

# from precursor.scratchpad import store
# from precursor.projects.utils import get_project_names

# def store_artifact(
#     project_name: str,
#     task: str,
#     short_description: str,
#     uri: str,
#     step_by_step_summary: Optional[str] = None,
# ) -> str:
#     f"""
#     Store an artifact reference so that the user can review it later.  This is the only way to ensure an artifact will be available for the user to actually interact with.

#     IT IS IMPERATIVE that this method is called every time an artifact is created or edited.  This is the ONLY way to ensure an artifact will be available for the user to actually interact with.

#     Only call this method once per artifact per task, likely one of the final function calls to make before returning the result to the user.
    
#     Parameters
#     ----------
#     project_name : str
#         Must match an existing project name.
#     task : str
#         The specific task that the agent was addressing when creating this artifact.
#     short_description : str
#         One-sentence human-readable summary of the artifact (what it is).  Limit technical details and describe in layman's terms.
#     uri : str
#         Pointer/handle to the created/edited resource (e.g., drive url, file path, pr url, etc.).
#     step_by_step_summary : str, optional
#         Hidden operational details about what the agent did to produce this artifact.
#         This is NOT rendered in the scratchpad; it will be stored inside metadata.

#     Returns
#     -------
#     str
#         A short confirmation string suitable for logging or display.
#     """
#     store.init_db()

#     # Validate project early and provide helpful suggestions
#     if not store.is_valid_project(project_name):
#         all_projects = get_project_names(only_enabled=False)
#         suggestions = "\n".join(f"- {p}" for p in all_projects) if all_projects else "None configured."
#         return (
#             f"Unknown project '{project_name}'. Please fix the name or add it to config/projects.yaml.\n\n"
#             f"Did you mean one of these instead?\n{suggestions}\n\n"
#         )

#     visible_message = f"{task} [{short_description}] (uri: {uri})".strip()
#     metadata = {
#         "task": task,
#         "uri": uri,
#         "step_by_step_summary": step_by_step_summary,
#         "short_description": short_description,
#     }

#     # --- light idempotency: skip if same project+section has same uri+task ---
#     existing = store.list_entries(project_name, section="Agent Completed Tasks (Pending Review)")
#     for row in existing:
#         md = row.get("metadata") or {}
#         if md.get("uri") == uri and md.get("task", "").strip() == task:
#             return f"Artifact already recorded as entry {row['id']} (pending review)."

#     # We deliberately do not create a separate table; metadata lives per row.
#     entry_id = store.add_entry(
#         project_name=project_name,
#         section="Agent Completed Tasks (Pending Review)",
#         message=visible_message,
#         confidence=10,
#         subsection=None,
#         metadata=metadata,
#     )

#     return f"Recorded artifact entry {entry_id} in 'Agent Completed Tasks (Pending Review)'."