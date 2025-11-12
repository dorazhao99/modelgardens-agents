import dspy
from typing import Optional, List

class FutureGoalInducer(dspy.Signature):
    """
Infer the user's **future, high-level goals** for this project.  These should not be task-level goals or overly specific to a particular set of work/tasks.  Instead, they should be larger objectives or deliverables that may take multiple steps to complete and exist at a higher time horizon than the current objectives.

Importantly these should be objectives that the user would like to achieve in a week or a months time.  You should not get caught up in the details of the current tasks or objectives.  Instead, you should focus on the larger objectives that the user is likely to be pursuing.

========================
Task Overview
========================
Given:
- the user’s own description of themselves and their long-term aspirations,
- the name and description of the current project,
- and the project’s scratchpad (containing objectives, notes, next steps, and resources),
- and the user's own description of the project that the user is currently working on from their own perspective
- and the user's own description of their own goals for working with an agent

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
✅ Ordered by relevance and importance"""
    user_profile: str = dspy.InputField(description="A description of the user and their goals for collaboration with the agent")
    project_name: str = dspy.InputField(description="The name of the project that the user is currently working on")
    project_scratchpad: str = dspy.InputField(description="The current rendered project scratchpad with all the information we know about the project")
    project_description: Optional[str] = dspy.InputField(description="A description of the project that the user is currently working on from their own perspective")
    future_goals: List[str] = dspy.OutputField(description="A list of high level goals that the user may have for this project ordered from most important/relevant to least important")