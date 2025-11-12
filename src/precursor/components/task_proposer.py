import dspy
from typing import Optional, List
from precursor.scratchpad.utils import render_project_scratchpad_text

class FutureGoalInducer(dspy.Signature):
    """
    Infer the user's **future, high-level goals** for this project.

    ========================
    Task Overview
    ========================
    Given:
    - the user’s own description of themselves and their long-term aspirations,
    - the name and description of the current project,
    - and the project’s scratchpad (containing objectives, notes, next steps, and resources),

    Brainstorm a concise, **rank-ordered list of strategic goals** that the user is likely pursuing through this project.
    These goals should represent *larger deliverables, milestones, or transformations* that require multiple steps or sub-objectives to achieve.
    Think of them as “the things the user would celebrate completing a week or a month from now.”

    ========================
    Reasoning Framework
    ========================
    Follow this structured reasoning before finalizing your list.

    **1. Interpret the project in context.**
    - What kind of work is this (research, design, writing, engineering, organization, etc.)?
    - What stage is the project at (early exploration, drafting, implementation, evaluation, polish, dissemination)?
    - How does this project connect to the user’s broader goals and professional identity?

    **2. Extract signals from the scratchpad.**
    - What recurring *themes, objectives, or constraints* appear?
    - Which “Next Steps” imply a larger deliverable or milestone?
    - Are there patterns that suggest upcoming shifts (e.g., from prototyping → documentation → publication)?

    **3. Synthesize medium-term objectives.**
    - Group related short-term tasks into coherent larger goals.
    - Express each goal as a **clear outcome**, not a single action.
      Example: “Finalize user study design and collect pilot data,” not “write the survey.”

    **4. Check alignment with the user’s self-description.**
    - Ensure the goals reflect the user’s style, values, and motivation.
      For example, a user who values collaboration may frame goals in terms of *team progress* or *shared understanding*.

    **5. Prioritize and refine.**
    - Rank goals by relevance and importance.
    - Keep them distinct, non-redundant, and phrased at similar abstraction levels.
    - Avoid restating existing scratchpad objectives verbatim; abstract them upward.

    ========================
    Output Guidelines
    ========================
    - Return 3–7 concise goal statements.
    - Order them from most central to least central.
    - Each should be written as a short phrase describing an outcome or milestone.
      Examples:
        - “Publish a polished research paper draft integrating recent results.”
        - “Design a reusable data-analysis pipeline for future experiments.”
        - “Consolidate collaboration workflows and onboarding materials.”
        - “Refactor project architecture for long-term maintainability.”
        - “Develop a prototype suitable for user testing and demo.”

    ========================
    Evaluation Checklist
    ========================
    ✅ Distinct goals that reflect higher-level intent  
    ✅ Consistent with project context and user profile  
    ✅ Abstracted beyond immediate tasks  
    ✅ Realistic in scope (multi-step, not vague ambition)  
    ✅ Ordered by relevance and importance  
    """
    user_profile: str = dspy.InputField(description="A description of the user and their goals for collaboration with the agent")
    project_name: str = dspy.InputField(description="The name of the project that the user is currently working on")
    project_scratchpad: str = dspy.InputField(description="The current rendered project scratchpad with all the information we know about the project")
    project_description: Optional[str] = dspy.InputField(description="A description of the project that the user is currently working on from their own perspective")
    user_agent_goals: Optional[str] = dspy.InputField(description="Existing agent-recorded goals or intentions for the user/project (optional)")
    future_goals: List[str] = dspy.OutputField(description="A list of high level goals that the user may have for this project ordered from most important/relevant to least important")

class FutureGoalInducerModule(dspy.Module):
    """
    DSPy module that induces future high-level goals for a project, mirroring
    the structure used in the feasibility estimator.
    """
    def __init__(self, *, max_scratchpad_chars: int = 12000) -> None:
        super().__init__()
        self.inducer = dspy.ChainOfThought(FutureGoalInducer)
        self.max_scratchpad_chars = max_scratchpad_chars

    def forward(
        self,
        *,
        user_profile: str,
        project_name: str,
        project_description: Optional[str] = None,
        user_agent_goals: Optional[str] = None,
        project_scratchpad: Optional[str] = None,
    ) -> List[str]:
        if not project_scratchpad:
            project_scratchpad = render_project_scratchpad_text(
                project_name,
                max_chars=self.max_scratchpad_chars,
            )

        example = dspy.Example(
            user_profile=user_profile,
            project_name=project_name,
            project_scratchpad=project_scratchpad,
            project_description=project_description,
            user_agent_goals=user_agent_goals,
        ).with_inputs("user_profile", "project_name", "project_scratchpad", "project_description")

        output = self.inducer(
            user_profile=user_profile,
            project_name=project_name,
            project_scratchpad=project_scratchpad,
            project_description=project_description,
            user_agent_goals=user_agent_goals,
        )
        raw_goals = getattr(output, "future_goals", None)
        if not raw_goals:
            return []
        # Keep it dead simple: ensure strings only and strip empties.
        goals: List[str] = []
        for g in raw_goals:
            if not g:
                continue
            goals.append(str(g).strip())
        return [g for g in goals if g]