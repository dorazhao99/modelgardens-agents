import dspy
from typing import Optional, List, Dict

class BackgroundAgentTaskProposer(dspy.Signature):
    """
Propose **autonomous background-agent tasks** that would meaningfully advance the user’s project.

========================
Task Overview
========================
The user is actively working on a project with clear goals and a known set of important milestones or todos.
Your job is to suggest **specific, high-value tasks** that a background agent could complete independently
to accelerate progress toward these goals.

Think of these as *“Next Steps” done quietly in the background* — tasks that save future effort,
increase clarity, or reduce friction without requiring human confirmation.

========================
Design Principles
========================

**1. Value**
- Each task should *tangibly improve* the project’s quality, clarity, or momentum.
- Avoid filler or clerical tasks; prefer work that delivers insight, structure, or reusable artifacts.
- Example improvements:
    - Clarifying documentation or reports
    - Automating evaluation or analysis
    - Tidying or refactoring confusing files
    - Synthesizing prior work into concise summaries

**2. Low Risk**
- No actions that affect external parties (no emails, messages, orders, or deletions).
- Tasks should have *no irreversible effects* and minimal risk if imperfectly executed.
- Safe examples:
    - Drafting summaries or reports
    - Analyzing repository structure
    - Preparing optional improvements in a branch or sandbox
    - Editing the codebase and submitting a PR using the coding agent
- Bad examples would include sending messages, sending a meeting invite, cleaning up files, ordering supplies, etc.

**3. Feasibility**
- The background agent has access to:
    - Local filesystem
    - Google Drive
    - GitHub (clone, edit, commit, submit a PR) using the coding agent
    - Any additional tools that the user may have granted permission to use
    and is highly capable at coding, editing, and content summarization.
- Propose tasks it can realistically perform with only this context and its local tools.

**4. Independence**
- Do *not* assign the user’s current active objective — assume they’re already doing that.
- Focus on *supporting tasks* that unblock, amplify, or complement their main effort.
- Good examples include:
    - “Generate concise plots comparing recent experiment results.”
    - “Audit recent commits for undocumented configuration changes.”
    - “Draft a ‘methods’ section summarizing recent model updates.”

**5. User Preference Alignment**
- The user may have provided specific requests and preferences for the background agent.
- Consider the user’s working style and collaboration goals from their profile.
- Prioritize tasks that align with what they find valuable or have explicitly requested.
- Don't be limited to the user's specific requests.  Feel free to propose tasks beyond what the user has requested.
- The user's desires are not exhaustive and you should not be limited to them, but they are important inspiration for the tasks you propose.

**6. Learn from Past Agent Feedback**
- Review the “Agent Completed Tasks” sections of the project scratchpad:
    - **Accepted Agent Completed Tasks** indicate work the user found useful — take inspiration from these when proposing new tasks.
    - **Rejected Agent Completed Tasks** reflect approaches or task types the user did *not* find helpful — avoid repeating or rephrasing similar ideas.
- If no prior agent feedback is available, proceed normally.
- Treat these sections as direct signals of what the user values or dislikes in background-agent contributions.

**7. Optional Breadth**
- A few tasks may span multiple project goals — e.g., workflow improvements or reusable utilities.
- These “meta-tasks” are especially valuable when they create leverage across high level project goals.
- You can propose some tasks that are broadly helpful across multiple high level project goals and some which are more specific to a single high level project goal.

========================
Output Guidelines
========================
- Propose **10 unique, diverse, and independent tasks**.
- Phrase each as a *single, clear, actionable sentence* beginning with a verb.
- Each task should be:
    - Valuable → contributes to real progress or insight
    - Low Risk → no risk of external side effects to user or collaborators
    - Feasible → fits within the agent’s capabilities
    - Independent → complements, not duplicates, active work
    - (BONUS) User Preference Alignment → aligns with the user's desires for the background agent
    - (BONUS) Optional Breadth → spans multiple project goals and benefits the user in a holistic way
- These tasks will be provided as instructions to a background agent, so they should be specific, actionable, and quite precisely grounded in the project context to provide the necessary handoff.

**Examples**
NOTE: these are general for the sake of example.  Your tasks should be more specific and tailored to the user's project and goals.
- “Refactor the data-loading pipeline to generate cached intermediate tensors for faster iteration.”
- “Summarize recent experiment logs into a markdown report with key metrics and observations.”
- “Search the codebase for duplicate utility functions and propose a unified helper module.”
- “Draft a ‘Limitations & Future Work’ section summarizing recurring themes in past notes.”
- “Organize the Drive folder into subfolders for data, figures, and drafts.”
- “Generate plots comparing recent training runs for visual inclusion in the next report.”
- “Identify missing docstrings and auto-generate candidate documentation stubs.”
- “Extract collaborator mentions from notes and compile a private contact list (without messaging).”
- “Create a small script to automate nightly model evaluation runs and archive outputs.”
- “Produce a concise one-page project summary synthesizing all key artifacts.”

========================
Evaluation Checklist
========================
✅ Each task is concrete, valuable, and autonomous
✅ No social or irreversible actions
✅ Feasible for a local+API-connected agent
✅ Independent of the user’s main objective
✅ Covers a diverse range of contribution types
    """
    user_profile: str = dspy.InputField(description="A description of the user and their goals for collaboration with the agent")
    project_name: str = dspy.InputField(description="The name of the project that the user is currently working on")
    project_scratchpad: str = dspy.InputField(description="The current rendered project scratchpad with all the information we know about the project")
    project_description: Optional[str] = dspy.InputField(description="A description of the project that the user is currently working on from their own perspective")
    important_todo_list: str = dspy.InputField(description="A list of important todos that the user is trying to complete in order to achieve their high level project goals.  You should take inspiration from this list in proposing your background agent tasks.")
    tasks: List[str] = dspy.OutputField(description="A list of tasks that a background agent would be especially helpful for completing to push the user towards achieving their high level project goals.")

def organize_milestones(milestones: Dict[str, List[str]]) -> str:
    """
    Convert the dictionary of high level goals and their milestones into a string that can be provided to the background agent.
    """
    parts = []
    for goal, milestones in milestones.items():
        parts.append(f"## {goal}")
        for milestone in milestones:
            parts.append(f"  - [ ] {milestone}")
        parts.append("")
    return "\n".join(parts)