# src/precursor/components/feasibility_estimator.py
from __future__ import annotations

from typing import List, Optional

import dspy
import pydantic

from precursor.scratchpad.utils import (
    render_project_scratchpad_text,
    extract_actions_from_scratchpad,
)

class ActionFeasibility(pydantic.BaseModel):
    action: str
    missing_context: Optional[str] = None
    feasibility: int  # 1–10

# ---------------------------------------------------------------------------
# DSPy signature
# ---------------------------------------------------------------------------

class FeasibilityEstimationSignature(dspy.Signature):
    """
    Given a project scratchpad and a list of candidate actions / next steps,
    estimate how feasible it is for the agent (with its typical tools) to
    complete them **without** asking the user for more context.

    Scoring rubric (1–10):

    - 1: Extremely ambiguous. You would almost certainly need the user to supply
         a lot more context or do work themselves.
    - 2–3: Some signal, but still underspecified. Likely to stall without more
           details or pointers.
    - 4–5: Partially grounded in the scratchpad. With file/code/drive agents
           you could probably gather enough info, but it might take a couple of
           hops.
    - 6–7: Mostly clear. You can see the work item, the resources, or the files,
           and you can probably execute with minimal user involvement.
    - 8–9: Very clear. The action is fully specified or directly tied to
           resources listed in the scratchpad.
    - 10: Perfectly clear and actionable right now. You are highly confident you
           can do it end-to-end without the user doing anything.

    The model should return one structured item per input action.
    """
    project_scratchpad: str = dspy.InputField(
        description="Rendered scratchpad text for this project"
    )
    next_steps: list[str] = dspy.InputField(
        description="A list of potential next steps or suggestions to score"
    )
    feasibility: list[dict] = dspy.OutputField(
        description="One feasibility object per input action, in order"
    )


class FeasibilityEstimator(dspy.Module):
    def __init__(self, *, batch_size: int = 10, max_scratchpad_chars: int = 8000) -> None:
        super().__init__()
        self.estimator = dspy.ChainOfThought(FeasibilityEstimationSignature)
        self.batch_size = batch_size
        self.max_scratchpad_chars = max_scratchpad_chars

    def forward(
        self,
        *,
        project_name: str,
        extra_steps: Optional[List[str]] = None,
    ) -> List[ActionFeasibility]:
        # 1) load scratchpad via shared helper
        scratchpad_text = render_project_scratchpad_text(
            project_name,
            max_chars=self.max_scratchpad_chars,
        )

        # 2) parse actions via shared helper
        actions_from_pad = extract_actions_from_scratchpad(scratchpad_text)

        all_steps: List[str] = list(actions_from_pad)
        if extra_steps:
            all_steps.extend([s for s in extra_steps if s and s.strip()])

        if not all_steps:
            return []

        datasets: List[dspy.Example] = []
        for i in range(0, len(all_steps), self.batch_size):
            batch = all_steps[i : i + self.batch_size]
            datasets.append(
                dspy.Example(
                    project_scratchpad=scratchpad_text,
                    next_steps=batch,
                ).with_inputs("project_scratchpad", "next_steps")
            )

        outputs = self.estimator.batch(datasets)

        results: List[ActionFeasibility] = []
        for out in outputs:
            raw_list = getattr(out, "feasibility", []) or []
            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                score = int(item.get("feasibility", 5))
                if score < 1:
                    score = 1
                elif score > 10:
                    score = 10
                results.append(
                    ActionFeasibility(
                        action=item.get("action", ""),
                        missing_context=item.get("missing_context"),
                        feasibility=score,
                    )
                )
        return results