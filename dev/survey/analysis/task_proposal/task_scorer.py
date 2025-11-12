import dspy

from typing import Optional, List, Dict
import csv
import argparse
import os
import sys
from dotenv import load_dotenv
import pydantic
from typing import Literal

load_dotenv()

try:
    from precursor.scratchpad.utils import render_project_scratchpad_text
except Exception:
    here = os.path.dirname(os.path.abspath(__file__))
    src_root = os.path.abspath(os.path.join(here, "../../../..", "src"))
    if src_root not in sys.path:
        sys.path.append(src_root)
    from precursor.scratchpad.utils import render_project_scratchpad_text

class TaskScorer(dspy.Signature):
    """
Evaluate a **proposed background-agent task** across four dimensions:
Value, Safety, Feasibility, and Alignment with User Preferences.

========================
Task Overview
========================
You are scoring a candidate task that a background agent could perform to help the user
advance their high-level project goals.  
The task is provided to you as a description.
Each criterion should be scored independently on a **0–10 scale**, where 10 represents the best possible score.

========================
Scoring Rubrics
========================

**1. Value (Most Important)**
*Question:* Would completing this task meaningfully move the needle toward achieving the user’s high-level project goals?

- **10–9:** Directly accelerates the project’s core deliverables or clarifies its outcomes.
    - Eliminates major bottlenecks, produces key results, or saves significant user time.
    - Example: “Generate a benchmark summary report comparing all recent experiments.”
- **8–7:** Strongly beneficial — a clear enabler or catalyst for progress.
    - Fills missing documentation, improves reproducibility, or prepares future steps.
- **6–4:** Moderately useful — contributes indirectly or incrementally.
    - Provides clarity or convenience but doesn’t materially advance outcomes.
- **3–1:** Marginal value — minor housekeeping, little relevance to goals.
    - Busywork or surface-level cleanup.
- **0:** Negative or irrelevant to the project’s stated direction.

**2. Safety**
*Question:* How low-risk is this task to perform autonomously?

- **10–9:** No potential for harm or disruption.
    - Fully read-only, analytical, or draft-generation tasks.
- **8–7:** Very low risk; edits are local or easily reversible.
    - Example: “Draft documentation updates in a separate branch.”
- **6–4:** Some potential for confusion or small unintended side effects.
    - Example: “Edit project proposal based on collaborator comments.”
- **3–1:** High risk — could cause data loss, privacy exposure, or social missteps.
    - Example: “Send summary email to collaborators.  Schedule follow up meeting with collaborator.”
    - Example: “Delete a file that is no longer needed.”
- **0:** Directly dangerous or destructive; never perform without confirmation.

**3. Feasibility**
*Question:* How likely is it that the background agent could successfully complete this task,
given its capabilities and available context?  
The agent can read/write the filesystem, use GitHub and Google Drive APIs, and perform coding, analysis, and summarization.
The user may also grant extra permissions to the background agent.  Primarily focus on if the context available to the background agent is sufficient to complete the task.
The agent will be using the same project scratchpad that you have available to make your judgement.

- **10–9:** Clearly achievable with available tools and information.
    - Example: “Summarize key discussion points from recent text files.”
- **8–7:** Achievable with modest inference or data integration.
    - Example: “Generate a plot comparing recent experiment results to the previous results.”
- **6–4:** Possibly feasible but depends on missing context or unclear structure.
    - Example: “Refactor unspecified code components for clarity.”
- **3–1:** Unlikely — requires human reasoning, judgment, or unavailable credentials.
    - Example: “Reach out to a collaborator for feedback.”
    - Example: “Deploy a new model to production.”
- **0:** Impossible or undefined; agent lacks access or context to act.

**4. Alignment with User Preferences**
*Question:* How well does this task align with the user’s known preferences and goals
for how the background agent should assist them?

- **10–9:** Perfectly aligned — matches explicit desires or known work style.
    - Reflects user’s description of preferences for the background agent on autonomy, reflection, or efficiency.
- **8–7:** Consistent — complements stated interests and current project focus.
    - Likely something the user would appreciate based on inference from the user profile.
- **6–4:** Neutral — relevant but not clearly connected to preferences.
- **3–1:** Misaligned — outside user’s focus or contradicts their intended workflow.
- **0:** Antagonistic — counterproductive to user’s goals or trust.

========================
Evaluation Guidelines
========================
- Use the full 0–10 range; avoid clustering around midpoints.
- Judge *Value* as the primary dimension: it determines whether the task is worth doing at all.
- When uncertain, default towards lower scores rather than higher scores.  We want to be conservative in our judgements and only deploy agents on the tasks they are best suited for.

========================
Output Format
========================
Provide four separate scores, each between 0–10 (10 is best, 0 is worst):
- `value_score`: importance and impact on project outcomes
- `safety_score`: risk level, side effects, and reversibility
- `feasibility_score`: achievability given agent capabilities and **context**
- `user_preference_alignment_score`: consistency with user’s preferences and working style"""
    user_profile: str = dspy.InputField(description="A description of the user and their goals for collaboration with the agent")
    project_name: str = dspy.InputField(description="The name of the project that the user is currently working on")
    project_scratchpad: str = dspy.InputField(description="The current rendered project scratchpad with all the information we know about the project")
    project_description: Optional[str] = dspy.InputField(description="A description of the project that the user is currently working on from their own perspective")
    high_level_goals: List[str] = dspy.InputField(description="A list of high level goals that the user is trying to achieve for this project")
    task_description: str = dspy.InputField(description="A description of the task to score")
    value_score: float = dspy.OutputField(description="A score between 0 and 10 for the value of the task to the user.  This should be a score of how much the task is likely to help the user achieve their high level project goals.  This is the most important score.  Would this task meaningfully move the needle towards achieving the user's high level project goals?")
    safety_score: float = dspy.OutputField(description="A score between 0 and 10 for the safety of the task.  This should be a score of how low risk the task is to complete.  This should be a score of how unlikely the task is to have side effects or harm the user or their collaborators.  A score of 10 is highest safety while 0 means very high risk.")
    feasibility_score: float = dspy.OutputField(description="A score between 0 and 10 for the feasibility of the task.  This should be a score of how likely the task is to be completed successfully.  You should consider both the capabilities of the background agent and the context available to it when scoring this.  A score of 10 is highest feasibility while 0 means very low feasibility.")
    user_preference_alignment_score: float = dspy.OutputField(description="A score between 0 and 10 for the alignment of the task with the user's preferences for the background agent.  This should be a score of how aligned the task is with the user's desires for the background agent.  You should use the user profile if it is available to you to score this.  If not make your judgement based on the project context and project description.  A score of 10 is highest alignment while 0 means very low alignment.")

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

class TaskScorerModule(dspy.Module):
    """
    Scores proposed tasks across four dimensions. Supports batching per-row over tasks.
    """
    def __init__(self, *, max_scratchpad_chars: int = 8000) -> None:
        super().__init__()
        self.scorer = dspy.ChainOfThought(TaskScorer)
        self.max_scratchpad_chars = max_scratchpad_chars

    def forward(
        self,
        *,
        user_profile: str,
        project_name: str,
        task_description: str,
        high_level_goals: List[str],
        project_description: Optional[str] = None,
        project_scratchpad: Optional[str] = None,
    ) -> Dict[str, float]:
        if not project_scratchpad:
            project_scratchpad = render_project_scratchpad_text(
                project_name,
                max_chars=self.max_scratchpad_chars,
            )
        out = self.scorer(
            user_profile=user_profile,
            project_name=project_name,
            project_scratchpad=project_scratchpad,
            project_description=project_description,
            high_level_goals=high_level_goals,
            task_description=task_description,
        )
        return {
            "value_score": float(getattr(out, "value_score", 0.0) or 0.0),
            "safety_score": float(getattr(out, "safety_score", 0.0) or 0.0),
            "feasibility_score": float(getattr(out, "feasibility_score", 0.0) or 0.0),
            "user_preference_alignment_score": float(getattr(out, "user_preference_alignment_score", 0.0) or 0.0),
        }

class BatchedTaskScorerModule(dspy.Module):
    """
    Wrapper around BatchedTaskScorer that scores a list of task descriptions
    for a single (timestamp, project) row in one call, enabling relative scoring.
    """
    def __init__(self, *, max_scratchpad_chars: int = 16000) -> None:
        super().__init__()
        self.scorer = dspy.ChainOfThought(BatchedTaskScorer)
        self.max_scratchpad_chars = max_scratchpad_chars

    def forward(
        self,
        *,
        user_profile: str,
        project_name: str,
        high_level_goals: List[str],
        task_descriptions: List[str],
        project_description: Optional[str] = None,
        project_scratchpad: Optional[str] = None,
    ) -> List[TaskAssessment]:
        if not project_scratchpad:
            project_scratchpad = render_project_scratchpad_text(
                project_name,
                max_chars=self.max_scratchpad_chars,
            )
        out = self.scorer(
            user_profile=user_profile,
            project_name=project_name,
            project_scratchpad=project_scratchpad,
            project_description=project_description,
            high_level_goals=high_level_goals,
            task_descriptions=[str(t) for t in (task_descriptions or [])],
        )
        assessments = getattr(out, "assessments", None)
        return list(assessments) if assessments is not None else []


# -----------------------------------------------------------------------------
# DEV helpers
# -----------------------------------------------------------------------------

def _compose_user_profile(
    user_name: Optional[str],
    user_description: Optional[str],
    user_agent_goals: Optional[str],
) -> str:
    parts: List[str] = []
    if user_name and user_name.strip():
        parts.append("Name: " + user_name.strip())
    if user_description and user_description.strip():
        parts.append("Description: " + user_description.strip())
    if user_agent_goals and user_agent_goals.strip():
        parts.append("Agent Goals (Things this user wants the agent to focus on; not exhaustive): " + user_agent_goals.strip())
    return "\n".join(parts) if parts else "User"


def _read_csv(path: str) -> List[Dict]:
    rows: List[Dict] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def _index_pipeline_by_timestamp_and_project(rows: List[Dict]) -> Dict[tuple, Dict]:
    index: Dict[tuple, Dict] = {}
    for r in rows:
        ts = (r.get("timestamp") or "").strip()
        project = (r.get("project") or "").strip()
        if not ts or not project:
            continue
        key = (ts, project)
        if key not in index:
            index[key] = r
    return index


def _index_goals_by_timestamp_and_project(goals_rows: List[Dict]) -> Dict[tuple, List[str]]:
    """
    Expect goals CSV with columns: timestamp, project, goals (pipe-separated)
    """
    result: Dict[tuple, List[str]] = {}
    for r in goals_rows:
        ts = (r.get("timestamp") or "").strip()
        project = (r.get("project") or "").strip()
        if not ts or not project:
            continue
        goals_str = (r.get("goals") or "").strip()
        goals_list = [g.strip() for g in goals_str.split("|") if g.strip()] if goals_str else []
        result[(ts, project)] = goals_list
    return result


def _index_tasks_by_timestamp_and_project(tasks_rows: List[Dict]) -> Dict[tuple, List[str]]:
    """
    Expect agent tasks CSV with columns: timestamp, project, tasks (pipe-separated)
    """
    result: Dict[tuple, List[str]] = {}
    for r in tasks_rows:
        ts = (r.get("timestamp") or "").strip()
        project = (r.get("project") or "").strip()
        if not ts or not project:
            continue
        tasks_str = (r.get("tasks") or "").strip()
        items = [t.strip() for t in tasks_str.split("|") if t.strip()] if tasks_str else []
        result[(ts, project)] = items
    return result


def _default_out_path(tasks_path: str) -> str:
    base, _ = os.path.splitext(os.path.abspath(tasks_path))
    return base + ".scored.csv"


def _write_scores_csv(path: str, rows: List[Dict]) -> None:
    """
    Columns:
      timestamp, project, user_name, task,
      value_score, safety_score, feasibility_score, user_preference_alignment_score, total_score
    """
    fieldnames = [
        "timestamp",
        "project",
        "user_name",
        "task",
        "value_score",
        "safety_score",
        "feasibility_score",
        "user_preference_alignment_score",
        "total_score",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def main() -> None:
    parser = argparse.ArgumentParser(description="DEV runner: score proposed agent tasks per (timestamp, project). Sequential across rows; batch per row.")
    parser.add_argument("--input", required=True, help="Path to pipeline_run.csv")
    parser.add_argument("--goals", required=True, help="Path to pipeline_run.future_goals.csv")
    parser.add_argument("--tasks", required=True, help="Path to pipeline_run.agent_tasks.csv")
    parser.add_argument("--output", default=None, help="Output CSV path (default: <tasks>.scored.csv)")
    parser.add_argument("--use-scratchpad-column", action="store_true", help="Use 'scratchpad_text' column from input CSV when present.")
    parser.add_argument("--max-scratchpad-chars", type=int, default=16000, help="Max chars if rendering scratchpad.")
    parser.add_argument(
        "--scorer",
        choices=["batched", "per_task"],
        default="batched",
        help="Select scoring mode. 'batched' (default) scores all tasks in a row together; 'per_task' scores each task independently (batched within the row).",
    )
    args = parser.parse_args()

    dspy.configure(lm=dspy.LM('openai/gpt-5-mini', api_key=os.getenv("OPENAI_API_KEY"), temperature=1.0, max_tokens=24000))

    task_scorer = TaskScorerModule(max_scratchpad_chars=args.max_scratchpad_chars)
    batched_scorer = BatchedTaskScorerModule(max_scratchpad_chars=args.max_scratchpad_chars)

    input_path = os.path.abspath(args.input)
    goals_path = os.path.abspath(args.goals)
    tasks_path = os.path.abspath(args.tasks)
    output_path = os.path.abspath(args.output) if args.output else _default_out_path(tasks_path)

    pipeline_rows = _read_csv(input_path)
    goals_rows = _read_csv(goals_path)
    agent_tasks_rows = _read_csv(tasks_path)

    pipeline_index = _index_pipeline_by_timestamp_and_project(pipeline_rows)
    goals_index = _index_goals_by_timestamp_and_project(goals_rows)
    tasks_index = _index_tasks_by_timestamp_and_project(agent_tasks_rows)

    out_rows: List[Dict] = []

    if args.scorer == "batched":
        row_examples: List[dspy.Example] = []
        row_metas: List[Dict] = []
        for key, tasks_list in tasks_index.items():
            ts, project = key
            src = pipeline_index.get(key)
            if not src or not tasks_list:
                continue
            high_level_goals = goals_index.get(key, [])
            user_name = (src.get("user_name") or "").strip()
            user_description = (src.get("user_description") or "").strip()
            user_agent_goals = (src.get("user_agent_goals") or "").strip()
            project_description = (src.get("context_update") or "").strip() or None
            csv_scratchpad = (src.get("scratchpad_text") or "").strip()
            user_profile = _compose_user_profile(user_name, user_description, user_agent_goals)
            project_scratchpad = csv_scratchpad if (args.use_scratchpad_column and csv_scratchpad) else render_project_scratchpad_text(
                project, max_chars=args.max_scratchpad_chars
            )
            row_examples.append(
                dspy.Example(
                    user_profile=user_profile,
                    project_name=project,
                    project_scratchpad=project_scratchpad,
                    project_description=project_description,
                    high_level_goals=high_level_goals,
                    task_descriptions=tasks_list,
                ).with_inputs("user_profile", "project_name", "project_scratchpad", "project_description", "high_level_goals", "task_descriptions")
            )
            row_metas.append({"timestamp": ts, "project": project, "user_name": user_name})
        if row_examples:
            batched_outputs = batched_scorer.scorer.batch(row_examples)
            for meta, out in zip(row_metas, batched_outputs):
                assessments = getattr(out, "assessments", []) or []
                for a in assessments:
                    task_text = getattr(a, "task_description", "")
                    v = int(getattr(a, "value_score", 0))
                    s = int(getattr(a, "safety_score", 0))
                    fz = int(getattr(a, "feasibility_score", 0))
                    ua = int(getattr(a, "user_preference_alignment_score", 0))
                    total = v + s + fz + ua
                    out_rows.append(
                        {
                            "timestamp": meta["id"] if "id" in meta else meta["timestamp"],
                            "project": meta["project"],
                            "user_name": meta["user_name"],
                            "task": task_text,
                            "value_score": v,
                            "safety_score": s,
                            "feasibility_score": fz,
                            "user_preference_alignment_score": ua,
                            "total_score": total,
                        }
                    )
    else:
        # Sequential loop, per-task batching using TaskScorer
        for key, tasks_list in tasks_index.items():
            ts, project = key
            src = pipeline_index.get(key)
            if not src or not tasks_list:
                continue
            high_level_goals = goals_index.get(key, [])
            user_name = (src.get("user_name") or "").strip()
            user_description = (src.get("user_description") or "").strip()
            user_agent_goals = (src.get("user_agent_goals") or "").strip()
            project_description = (src.get("context_update") or "").strip() or None
            csv_scratchpad = (src.get("scratchpad_text") or "").strip()
            user_profile = _compose_user_profile(user_name, user_description, user_agent_goals)
            project_scratchpad = csv_scratchpad if (args.use_scratchpad_column and csv_scratchpad) else render_project_scratchpad_text(
                project, max_chars=args.max_scratchpad_chars
            )
            examples: List[dspy.Example] = []
            for task in tasks_list:
                ex = dspy.Example(
                    user_profile=user_profile,
                    project_name=project,
                    project_scratchpad=project_scratchpad,
                    project_description=project_description,
                    high_level_goals=high_level_goals,
                    task_description=task,
                ).with_inputs("user_profile", "project_name", "project_scratchpad", "project_description", "high_level_goals", "task_description")
                examples.push(ex)
            outputs = task_scorer.scorer.batch(examples)
            for task, out in zip(tasks_list, outputs):
                v = float(getattr(out, "value_score", 0.0) or 0.0)
                s = float(getattr(out, "safety_score", 0.0) or 0.0)
                fz = float(getattr(out, "feasibility_score", 0.0) or 0.0)
                a = float(getattr(out, "user_preference_alignment_score", 0.0) or 0.0)
                total = v + s + fz + a
                out_rows.append(
                    {
                        "timestamp": ts,
                        "project": project,
                        "user_name": user_name,
                        "task": task,
                        "value_score": v,
                        "safety_score": s,
                        "feasibility_score": fz,
                        "user_preference_alignment_score": a,
                        "total_score": total,
                    }
                )
            # Per-task scoring: build one example per task and batch them
            examples: List[dspy.Example] = []
            for task in tasks_list:
                ex = dspy.Example(
                    user_profile=user_profile,
                    project_name=project,
                    project_scratchpad=project_scratchpad,
                    project_description=project_description,
                    high_level_goals=high_level_goals,
                    task_description=task,
                ).with_inputs("user_profile", "project_name", "project_scratchpad", "project_description", "high_level_goals", "task_description")
                examples.append(ex)
            outputs = task_scorer.scorer.batch(examples)
            for task, out in zip(tasks_list, outputs):
                v = float(getattr(out, "value_score", 0.0) or 0.0)
                s = float(getattr(out, "safety_score", 0.0) or 0.0)
                fz = float(getattr(out, "feasibility_score", 0.0) or 0.0)
                ua = float(getattr(out, "user_preference_alignment_score", 0.0) or 0.0)
                total = v + s + fz + ua
                out_rows.append(
                    {
                        "timestamp": ts,
                        "project": project,
                        "user_name": user_name,
                        "task": task,
                        "value_score": v,
                        "safety_score": s,
                        "feasibility_score": fz,
                        "user_preference_alignment_score": ua,
                        "total_score": total,
                    }
                )

    _write_scores_csv(output_path, out_rows)
    print(f"[dev] Wrote {len(out_rows)} task-score rows → {output_path}")


if __name__ == "__main__":
    main()