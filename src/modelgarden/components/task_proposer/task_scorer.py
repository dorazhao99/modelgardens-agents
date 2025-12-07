import dspy
from typing import Optional, List
import pydantic

class TaskAssessment(pydantic.BaseModel):
    task_description: str = pydantic.Field(description="A description of the task to score, should be copied from the input task description")
    reasoning: str = pydantic.Field(description="Some space to explain your reasoning and to do some pre-thinking about the task before you assign the set of final scores.  This should be at minimum four sentences, and at most 4 paragraphs (one for each score).")
    value_score: int = pydantic.Field(description="A score between 0 and 10 for the value of the task to the user.  This should be a score of how much the task is likely to help the user achieve their high level project goals.  This is the most important score.  Would this task meaningfully move the needle towards achieving the user's high level project goals?", ge=0, le=10)
    safety_score: int = pydantic.Field(description="A score between 0 and 10 for the safety of the task.  This should be a score of how low risk the task is to complete.  This should be a score of how unlikely the task is to have side effects or harm the user or their collaborators.  A score of 10 is highest safety while 0 means very high risk.", ge=0, le=10)
    feasibility_score: int = pydantic.Field(description="A score between 0 and 10 for the feasibility of the task.  This should be a score of how likely the task is to be completed successfully.  You should consider both the capabilities of the background agent and the context available to it when scoring this.  A score of 10 is highest feasibility while 0 means very low feasibility.", ge=0, le=10)
    user_preference_alignment_score: int = pydantic.Field(description="A score between 0 and 10 for the alignment of the task with the user's preferences for the background agent.  This should be a score of how aligned the task is with the user's desires for the background agent.  You should use the user profile if it is available to you to score this.  If not make your judgement based on the project context and project description.  A score of 10 is highest alignment while 0 means very low alignment.", ge=0, le=10)

class BatchedTaskScorer(dspy.Signature):
    """
You are scoring a **set of candidate background-agent tasks** for a single project.

Each task describes something the agent could do to help the user move toward their high-level project goals. 
You will return **one assessment per task**. All assessments must follow the same four scoring dimensions:

1. **value_score** – how much this task actually pushes the project toward its high-level goals  
2. **safety_score** – how low-risk and reversible the task is  
3. **feasibility_score** – how likely the agent can actually do it with the context/tools we have  
4. **user_preference_alignment_score** – how well this matches what the user says they want the agent to do

You are given:
- a user profile (what kind of help they like),
- the project name and current scratchpad (what we know right now),
- the user’s own project description (if present),
- and a list of high-level goals.
You must use this context. Do **not** score in a vacuum.

For **each** task, you must also produce a short **reasoning** section (4 sentences to 4 paragraphs) where you think through the four scores before writing them down.

========================
General principles
========================
- Score **each task independently** first.
- You *may* consider the relative usefulness of tasks in the batch (e.g. “this one clearly matters more than the others, so I won’t give them all 9s”), but you do **not** have to force an even spread.
- Use the **full 0–10 range** when it’s justified. Not every reasonable engineering task is a 9.
- When the task refers to artifacts that are **not clearly present** in the project scratchpad / description and they seem challenging to locate (e.g. “refactor unknown file”, “summarize unspecified data”), lower **feasibility** by several points.
- When in doubt, be **slightly conservative** (a 6 or 7 is fine) rather than optimistic (9–10).  For truly bad tasks you can even score (0-3).

========================
1. Value (most important)
========================
**Question:** Does this task *meaningfully* advance the project’s high-level goals or unblock an obviously important next step?

- **9–10**: Direct, high-leverage progress. Produces something the user is clearly going to need soon (report, consolidation, reproducibility, hygiene that unblocks automation). Tightly tied to the goals or the current scratchpad state.
    - Example: "Generate a benchmark summary report comparing all recent experiments.", "Perform literature review to find relevant papers for the project.", "Update status of action items from last week's sync based on work completed."
- **7–8**: Strongly helpful. Improves clarity, quality, or speed, but is slightly less central than the top items.
    - Example: "Draft documentation updates in a separate branch.", "Summarize key discussion points from recent text files."
- **4–6**: Useful but not essential. Nice to have, or only improves one small corner.
    - Example: "Refactor the data loader to use a more efficient caching strategy.", "Write up a data policy document for the project."
- **1–3**: Peripheral, cleanup-y, or not clearly connected to the current project state.
    - Example: "Clean up old files in the project directory.", "Write up a report on the current state of the project."
- **0**: Not relevant or contradicts the direction of the project.
    - Example: "Send a thank you email to a collaborator.", "Delete a file that is no longer needed."

If you’re unsure whether the task is actually needed based on the scratchpad, **do not** give 9–10 — stay in 5–7.

========================
2. Safety
========================
**Question:** How unlikely is it that this task will have side effects if run autonomously? Will this task involve communicating with third parties (not ideal)?

- **9–10**: Completely safe; read-only or generates drafts with no side effects.  
    - Example: "Summarize project notes in a new markdown file.", 
        "Generate a data-quality report in a separate folder."
- **7–8**: Very low risk; edits or adds files in isolated areas, or creates reversible changes.  
    - Example: "Refactor code in a feature branch.", 
        "Add TODO comments suggesting code improvements."
- **4–6**: Minor risks such as unclear write targets, small potential overwrites, or file clutter.  
    - Example: "Update documentation files without explicit file paths.", 
        "Run cleanup scripts that might touch multiple folders."
- **1–3**: Noticeable risk; could cause confusion, break existing work, or perform social actions.  
    - Example: "Automatically push commits to the main branch.", 
        "Send a progress email to collaborators."
        "Schedule a meeting with a collaborator."
- **0**: Clearly harmful or destructive.  
    - Example: "Delete outdated directories automatically.", 
        "Remove project data files."

If the task wording is vague about *where* to write, drop safety a little (we don’t want to spray edits into unknown places).

========================
3. Feasibility
========================
**Question:** Can the background agent actually do this with the tools and context we said it has?

Assume the agent:
- can read/write the local filesystem and repos,
- can call GitHub / Google Drive APIs,
- can edit code and documents,
- and sees the same scratchpad you see.

NOTE: The agent is pretty capable with skills so you should be asking yourself "If I had to do this task with what I know right now, would I be able to do it?"  This helps you focus on the context.

- **9–10**: Fully supported by the current project context — all resources named and accessible.  
    - Example: "Update `objective_inducer.py` with improved logging.", 
        "Summarize recent experiment logs in `results.csv`."
- **7–8**: Mostly doable, might require guessing a minor detail (file path, parameter) or using sophisticated tools.  
    - Example: "Plot performance trends from the last few experiment outputs.", 
        "Generate summary slides from current results."
- **4–6**: Possible but vague or partially underspecified; relies on unclear context.  
    - Example: "Refactor the data loader to use a more efficient caching strategy.",
        "Optimize data preprocessing for speed."
- **1–3**: Unlikely without major human input or credentials.  
    - Example: "Ask collaborator for dataset updates.", 
        "Deploy trained model to production."
- **0**: Impossible or outside agent’s access.  
    - Example: "File legal paperwork for the research project."

========================
4. Alignment with user preferences
========================
**Question:** Is this the kind of help the user said they want?

- **10–9:** Perfectly aligned — matches explicit desires or known work style.
    - Reflects user’s description of preferences for the background agent on autonomy, reflection, or efficiency.
    - Example: "Automate repetitive setup steps for experiments." (for a user who values efficiency), 
    "Draft concise documentation." (for a user focused on clarity)
- **8–7:** Consistent — complements stated interests and current project focus.
    - Likely something the user would appreciate based on inference from the user profile.
- **6–4:** Neutral — relevant but not clearly connected to preferences.
- **3–1:** Misaligned — outside user’s focus or contradicts their intended workflow.
- **0:** Antagonistic — counterproductive to user’s goals or trust.

**Incorporating prior agent feedback:**
- Review the “Agent Completed Tasks” sections of the project scratchpad:
    - **Accepted Agent Completed Tasks** indicate what the user *appreciated* — these patterns should increase alignment.
    - **Rejected Agent Completed Tasks** reflect directions the user *did not want* — these should decrease alignment.
- If no feedback is available, proceed normally.
- Treat these sections as direct evidence of what the user considers aligned or misaligned behavior.

========================
Output requirements
========================
For **each** input task:
1. Copy the task text into `task_description`.
2. Write `reasoning` with at least 4 sentences (you can do one mini-paragraph per score).
3. Produce the four scores, each an integer 0–10, consistent with the reasoning.

Remember: it is acceptable — and sometimes correct — for some tasks in the batch to get 5s and 6s if they are less central, less grounded in the scratchpad, or less aligned than the best ones.
    """
    user_profile: str = dspy.InputField(description="A description of the user and their goals for collaboration with the agent")
    project_name: str = dspy.InputField(description="The name of the project that the user is currently working on")
    project_scratchpad: str = dspy.InputField(description="The current rendered project scratchpad with all the information we know about the project")
    project_description: Optional[str] = dspy.InputField(description="A description of the project that the user is currently working on from their own perspective")
    high_level_goals: List[str] = dspy.InputField(description="A list of high level goals that the user is trying to achieve for this project")
    task_descriptions: List[str] = dspy.InputField(description="A list of descriptions of the tasks to score")
    assessments: List[TaskAssessment] = dspy.OutputField(description="A list of assessments for each task, one for each task description in the input")