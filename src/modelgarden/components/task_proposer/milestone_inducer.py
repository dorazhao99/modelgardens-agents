import dspy
from typing import Optional, List

class MilestoneInducer(dspy.Signature):
    """
Decompose a **high-level project goal** into the key **milestones** required to achieve it.

========================
Task Overview
========================
You are constructing a structured plan between abstract intent and concrete execution.
Your job is to identify the *major intermediate achievements* that must occur for this goal
to be realized — the tangible checkpoints a competent project manager would track.

Each milestone should represent a **distinct, meaningful accomplishment** —
something that can be clearly “checked off” and signals visible progress toward the goal.

========================
Reasoning Framework
========================

**1. Understand the high-level goal.**
- Clarify what successful completion looks like in practical terms.
- Identify what kind of output or transformation defines “done.”
    (e.g., a published paper, functioning prototype, public release, internal adoption).

**2. Interpret the context.**
- Use the project scratchpad and description to ground your reasoning.
- Note dependencies, current progress, collaborators, and resources already listed.
- Consider the user’s profile — what do they value (rigor, creativity, efficiency, polish)?

**3. Decompose the goal into milestones.**
- Split the overall goal into **logical phases** or **critical checkpoints**.
    Examples: design → build → evaluate → refine → publish.
- Each milestone should:
    - be achievable within a shorter timeframe (days to a few weeks),
    - correspond to a visible deliverable or proof of progress,
    - often depend on one or more earlier milestones.

**4. Sequence and validate.**
- Order milestones chronologically or logically (prerequisites first).
- Check for coverage — together they should span the full path from start to completion.
- Remove redundant or trivial items (e.g., “keep working on X”).
- If the project is already in progress, start from the *current* stage.

========================
Output Guidelines
========================
- Return 1–7 milestones as short, imperative or outcome-oriented phrases.
- Keep them specific, measurable, and outcome-focused.
- They should be specific, actionable tasks that are likely to be completed in a much shorter timeframe than the high level goal itself.
- Prefer phrasing that communicates a tangible result rather than effort.
    **Examples**
- *Research / Academic*
    - “Complete baseline experiments and record reproducible benchmarks.”
    - “Write and integrate the related-work section into the paper draft.”
    - “Prepare poster and slides for conference submission.”
- *Engineering / Technical*
    - “Implement end-to-end prototype and verify data flow correctness.”
    - “Set up automated evaluation pipeline for nightly tests.”
    - “Refactor module dependencies for easier extension.”
- *Creative / Design*
    - “Create finalized storyboard and shot list for all core scenes.”
    - “Produce first visual design mockups and collect feedback.”
    - “Assemble demo reel showcasing key concept variations.”
- *Product / Coordination*
    - “Define success metrics and align with collaborators on key deliverables.”
    - “Launch pilot test with initial user group and collect structured feedback.”
    - “Compile summary report with recommendations for next phase.”
- Do not be limited to the examples above.  Feel free to propose any milestones that you think are important to achieve in order to complete the high level goal.

========================
Evaluation Checklist
========================
✅ Each milestone contributes directly to completing the high-level goal
✅ Collectively, they form a coherent, stepwise plan
✅ Each milestone is non-trivial (several hours to a few days effort) and outcome-driven
✅ Ordered logically and distinct from short-term tasks
✅ Consistent with project context and user profile

========================
Important Note
========================
Your milestones MUST be related to the exact high level goal that was provided to you.  Do not propose milestones based on other aspects of the project.  The purpose of this exercise is to propose a list of milestones that can be used almost as a checklist to progress towards the high level goal."""
    user_profile: str = dspy.InputField(description="A description of the user and their goals for collaboration with the agent")
    project_name: str = dspy.InputField(description="The name of the project that the user is currently working on")
    project_scratchpad: str = dspy.InputField(description="The current rendered project scratchpad with all the information we know about the project")
    project_description: Optional[str] = dspy.InputField(description="A description of the project that the user is currently working on from their own perspective")
    high_level_goal: str = dspy.InputField(description="A high level goal that the user is trying to achieve for this project")
    milestones: List[str] = dspy.OutputField(description="A list of milestones that are most important to achieve in order to complete the high level goal.  These should be specific, actionable tasks that are likely to be completed in a shorter timeframe than the high level goal itself.")