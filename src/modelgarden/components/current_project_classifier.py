# src/precursor/components/current_project_classifier.py
from __future__ import annotations

from typing import List, Optional, Dict, Any, Literal

import dspy

# new imports — use the central helpers
from precursor.projects.utils import (
    load_projects_normalized,
    projects_to_labeled_list,
    get_project_names,
)
from precursor.scratchpad.utils import render_all_scratchpads_for_projects

class ProjectClassifierWithScratchpads(dspy.Signature):
    """
Classify the user's current work into one of the KNOWN PROJECTS.

You are given rich, structured evidence about the user’s current activity.  
Your goal is to reason step-by-step about which project the user is *most likely* working on **right now**.

Use the following context carefully:

1. **Recent Objectives** — short-term goals or TODO items the user has been pursuing.  
   → These usually describe active work streams (e.g., “Finalize figures for ACL submission”).

2. **Recent Propositions / Observations** — inferred notes or behavioral cues.  
   → These often describe *what the user was seen editing or thinking about*.  Prioritize patterns such as repo names, file paths, or repeated focus on one project.

3. **Calendar Context** — upcoming or recent meetings, events, or deadlines.  
   → Match event titles to projects (e.g., “Background Agents sync” → “Background Agents”).

4. **Ground-Truth Project List (with Descriptions)** — authoritative list of valid project names with a one-line summary each.  
   → Only predict one of these.  Use the descriptions to disambiguate similarly named tasks.

5. **Per-Project Scratchpads** — highly detailed summaries of each project’s current work, resources, and notes.  
   → Treat these as “reference pages.”  Look for overlap between user goals, files, or wording in the objectives/propositions and the scratchpad contents.

6. **Recent Project Predictions (History, in order)** — your last few predictions.  
   → The history can be informative since users are somewhat likely to continue working on the same project from timestep to timestep, though it should not be used as the sole basis for prediction.

7. **Screenshot** — optional visual signal (e.g., IDE, document, slides).  
   → Useful to make the final call on which project based on the immediate visual context (e.g., “slides for NLP Retreat” → “NLP Retreat Planning”).

**Decision Strategy**
- Begin by identifying any strong overlap between recent objectives/propositions and project scratchpads or descriptions.
- Then, weigh calendar cues and visual cues for supporting context.  Note that the CALENDAR does not always reflect the user's current work, so it should be used as a secondary signal.
- Consider recency and continuity from prior predictions.
- Finally, output exactly **one** project label from the KNOWN PROJECTS list.

If none of the context clearly maps to a specific project, choose the most general fallback such as “Misc.”
"""

    recent_objectives: str = dspy.InputField(
        description="Recent objectives or goals that the user has been working on"
    )
    recent_propositions: str = dspy.InputField(
        description="Recent propositions that we have inferred about the user (may be inaccurate)"
    )
    calendar_events: str = dspy.InputField(
        description="Upcoming calendar events that the user has scheduled"
    )
    true_projects: list[str] = dspy.InputField(
        description="Set of ground truth projects that the user has provided, ideally 'Name: description'"
    )
    project_scratchpads: str = dspy.InputField(
        description="Rendered scratchpads for each project, prefixed with the project name, to help match context → project"
    )
    recent_project_predictions: list[str] = dspy.InputField(
        description="Most recent project predictions for the user (may be inaccurate)"
    )
    screenshot: dspy.Image = dspy.InputField(
        description="The user's current screen"
    )
    project: Literal[tuple(get_project_names(only_enabled=False) or ["Misc"])] = dspy.OutputField(
        description="Predicted project label that the user is currently working on"
    )


class CurrentProjectClassifier(dspy.Module):
    """
    Small callable component to classify the *current* project.

    - pulls actual project names + descriptions from config (via precursor.projects.utils)
    - renders per-project scratchpads (truncated) via precursor.scratchpad.utils
    - feeds everything into a single signature
    - returns the model result
    """

    def __init__(
        self,
        *,
        include_scratchpads: bool = True,
        max_scratchpad_chars: int = 1200,
    ) -> None:
        super().__init__()
        self.include_scratchpads = include_scratchpads
        self.max_scratchpad_chars = max_scratchpad_chars
        self.classifier = dspy.ChainOfThought(ProjectClassifierWithScratchpads)

    # ------------------------------------------------------------------
    # public entrypoint
    # ------------------------------------------------------------------
    def forward(
        self,
        *,
        recent_objectives: str,
        recent_propositions: str,
        calendar_events: str,
        screenshot: dspy.Image,
        recent_project_predictions: Optional[List[str]] = None,
    ):
        # 1) load normalized projects from the central place
        projects: List[Dict[str, Any]] = load_projects_normalized(only_enabled=False)

        # 2) build the richer "true projects" list (name + description)
        true_projects_rich: List[str] = projects_to_labeled_list(projects)

        # 3) render per-project scratchpads (optionally)
        if self.include_scratchpads:
            project_scratchpads: str = render_all_scratchpads_for_projects(
                projects,
                max_chars_per_project=self.max_scratchpad_chars,
            )
        else:
            project_scratchpads = ""

        # 4) call the signature
        res = self.classifier(
            recent_objectives=recent_objectives,
            recent_propositions=recent_propositions,
            calendar_events=calendar_events,
            screenshot=screenshot,
            recent_project_predictions=recent_project_predictions or [],
            true_projects=true_projects_rich,
            project_scratchpads=project_scratchpads,
        )
        return res