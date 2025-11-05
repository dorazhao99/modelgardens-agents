# src/precursor/components/objectives_inducer.py
from __future__ import annotations

from typing import List, Optional, Tuple

import dspy
import pydantic

GOAL_INDUCTION_PROMPT = """I have the attached a CONTEXT that a current user is working on:

Now, employ the following reasoning framework when inferring the goals. 
0. If there is an attached screenshot, use context clues to infer what application the user is viewing and what they might be doing in that application. Are they the direct author of the text, or are they viewing it as a reader? Are they actively editing the text, providing feedback, or synthesizing the content?
1. Identify the genre of what the user is working on and their stage of completion. Map the content's genre and completion stage to common goals users of these genre and stages may have and form an initial hypothesis of what the user's goals may be.
2. Infer who the intended audience of the content is. Based on how you think the user wants their audience to receive their content, update your goal hypothesis.
3. Think about what an ideal version of the user's current content would look like and identify what is missing. Then, use this to update your goal hypothesis.
4. Simulate what the user's reaction would be to possible tools generated (e.g. grammar checker, style reviser, high-level structure advisor, new content generator, etc.). Use the user's responses to update your goal hypothesis.

For each step in your reasoning, briefly write out your thought process, your current hypothesis of the goals as a numbered list, and what the updated list would be after your reasoning.

After you are done, finalize the [[limit]] most important goals. Make sure these goals are distinct and have minimal overlap. """

class Goal(pydantic.BaseModel):
    name: str
    description: str
    weight: pydantic.conint(ge=1, le=10)


class InduceObjectivesWithScreenshot(dspy.Signature):
    context: str = dspy.InputField(description="Rich context about what the user is doing right now")
    screenshot: dspy.Image = dspy.InputField(description="Screenshot of the user's current workspace")
    limit: int = dspy.InputField(description="How many goals to return")
    goals: List[Goal] = dspy.OutputField(description="Induced goals (most important first)")


class InduceObjectives(dspy.Signature):
    context: str = dspy.InputField(description="Rich context about what the user is doing right now")
    limit: int = dspy.InputField(description="How many goals to return")
    goals: List[Goal] = dspy.OutputField(description="Induced goals (most important first)")


class ObjectivesInducer(dspy.Module):
    """
    Thin wrapper around two DSPy chains:
    - with screenshot
    - without screenshot

    It does NOT know about gum, calendar, or screenshot capture.
    Callers can build the context with `precursor.context.utils.build_user_activity_context`
    and capture screenshots with `precursor.context.utils.grab_screen_dspy_image`.
    """

    def __init__(self) -> None:
        super().__init__()
        self._with_screenshot = dspy.ChainOfThought(
            InduceObjectivesWithScreenshot.with_instructions(GOAL_INDUCTION_PROMPT)
        )
        self._without_screenshot = dspy.ChainOfThought(
            InduceObjectives.with_instructions(GOAL_INDUCTION_PROMPT)
        )

    def forward(
        self,
        *,
        context: str,
        limit: int = 3,
        screenshot: Optional[dspy.Image] = None,
    ) -> Tuple[List[Goal], str]:
        """
        Run the inducer and return (goals, reasoning-like text if present).

        We return the reasoning as a string in second position to preserve what
        your original code was doing.
        """
        if screenshot is not None:
            res = self._with_screenshot(
                context=context,
                screenshot=screenshot,
                limit=limit,
            )
        else:
            res = self._without_screenshot(
                context=context,
                limit=limit,
            )

        # dspy modules usually expose chain-of-thought on `.reasoning` or similar;
        # be defensive here
        reasoning = getattr(res, "reasoning", "")
        return res.goals, reasoning