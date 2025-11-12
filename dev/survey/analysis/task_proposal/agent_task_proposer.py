import dspy 

from typing import Optional, List, Dict
import csv
import argparse
import os
import sys
from dotenv import load_dotenv

load_dotenv()

try:
    from precursor.scratchpad.utils import render_project_scratchpad_text
except Exception:
    here = os.path.dirname(os.path.abspath(__file__))
    src_root = os.path.abspath(os.path.join(here, "../../../..", "src"))
    if src_root not in sys.path:
        sys.path.append(src_root)
    from precursor.scratchpad.utils import render_project_scratchpad_text


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


class BackgroundAgentTaskProposerModule(dspy.Module):
    """
    Simple DSPy module to propose agent tasks given aggregated milestones.
    Batch-friendly: uses ChainOfThought under the hood.
    """
    def __init__(self, *, max_scratchpad_chars: int = 8000) -> None:
        super().__init__()
        self.proposer = dspy.ChainOfThought(BackgroundAgentTaskProposer)
        self.max_scratchpad_chars = max_scratchpad_chars

    def forward(
        self,
        *,
        user_profile: str,
        project_name: str,
        important_todo_list: str,
        project_description: Optional[str] = None,
        project_scratchpad: Optional[str] = None,
    ) -> List[str]:
        if not project_scratchpad:
            project_scratchpad = render_project_scratchpad_text(
                project_name,
                max_chars=self.max_scratchpad_chars,
            )
        output = self.proposer(
            user_profile=user_profile,
            project_name=project_name,
            project_scratchpad=project_scratchpad,
            project_description=project_description,
            important_todo_list=important_todo_list,
        )
        raw = getattr(output, "tasks", None) or []
        tasks: List[str] = []
        for t in raw:
            if not t:
                continue
            tasks.append(str(t).strip())
        return [t for t in tasks if t]


# -----------------------------------------------------------------------------
# DEV helpers (simple; local to this runner)
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

def _index_milestones_by_timestamp_and_project(milestones_rows: List[Dict]) -> Dict[tuple, Dict[str, List[str]]]:
    """
    Group milestones by (timestamp, project) so runs at different times don't get merged.
    Return: (timestamp, project) -> { high_level_goal -> [milestones...] }
    """
    result: Dict[tuple, Dict[str, List[str]]] = {}
    for r in milestones_rows:
        ts = (r.get("timestamp") or "").strip()
        project = (r.get("project") or "").strip()
        goal = (r.get("high_level_goal") or "").strip()
        if not ts or not project or not goal:
            continue
        ms_str = (r.get("milestones") or "").strip()
        items = [m.strip() for m in ms_str.split("|") if m.strip()] if ms_str else []
        if not items:
            continue
        key = (ts, project)
        by_goal = result.setdefault(key, {})
        by_goal[goal] = items
    return result


def _index_pipeline_by_timestamp_and_project(rows: List[Dict]) -> Dict[tuple, Dict]:
    """
    Build a quick lookup from (timestamp, project) -> source row from pipeline_run.csv
    """
    index: Dict[tuple, Dict] = {}
    for r in rows:
        ts = (r.get("timestamp") or "").strip()
        project = (r.get("project") or "").strip()
        if not ts or not project:
            continue
        key = (ts, project)
        # First one wins; rows at the same ts/project should be equivalent for our purposes
        if key not in index:
            index[key] = r
    return index


def _write_tasks_csv(path: str, rows: List[Dict]) -> None:
    """
    Columns: timestamp, project, user_name, tasks
    'tasks' is pipe-separated string.
    """
    fieldnames = ["timestamp", "project", "user_name", "tasks"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            tasks = r.get("tasks") or []
            tasks_str = " | ".join([t for t in tasks if t])
            writer.writerow(
                {
                    "timestamp": r.get("timestamp") or "",
                    "project": r.get("project") or "",
                    "user_name": r.get("user_name") or "",
                    "tasks": tasks_str,
                }
            )


def _default_out_path(input_path: str) -> str:
    base, _ = os.path.splitext(os.path.abspath(input_path))
    return base + ".agent_tasks.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="DEV runner: propose background-agent tasks using aggregated milestones (DSPy batch).")
    parser.add_argument("--input", required=True, help="Path to pipeline_run.csv")
    parser.add_argument("--milestones", required=True, help="Path to pipeline_run.milestones.csv (from milestone proposer)")
    parser.add_argument("--output", default=None, help="Output CSV path (default: <input>.agent_tasks.csv)")
    parser.add_argument("--use-scratchpad-column", action="store_true", help="Use 'scratchpad_text' column from input CSV when present.")
    parser.add_argument("--max-scratchpad-chars", type=int, default=8000, help="Max chars if rendering scratchpad.")
    args = parser.parse_args()

    # Configure DSPy for local dev (consistent with other dev runners).
    dspy.configure(lm=dspy.LM('openai/gpt-5-mini', api_key=os.getenv("OPENAI_API_KEY"), temperature=1.0, max_tokens=24000))

    module = BackgroundAgentTaskProposerModule(max_scratchpad_chars=args.max_scratchpad_chars)

    input_path = os.path.abspath(args.input)
    milestones_path = os.path.abspath(args.milestones)
    output_path = os.path.abspath(args.output) if args.output else _default_out_path(input_path)

    in_rows = _read_csv(input_path)
    ms_rows = _read_csv(milestones_path)
    milestones_by_run = _index_milestones_by_timestamp_and_project(ms_rows)
    pipeline_index = _index_pipeline_by_timestamp_and_project(in_rows)

    examples: List[dspy.Example] = []
    meta: List[Dict] = []

    # Build one example per (timestamp, project) present in milestones
    for (ts, project), goal_ms in milestones_by_run.items():
        src = pipeline_index.get((ts, project))
        if not src:
            # No matching pipeline row; skip this (timestamp, project)
            continue

        user_name = (src.get("user_name") or "").strip()
        user_description = (src.get("user_description") or "").strip()
        user_agent_goals = (src.get("user_agent_goals") or "").strip()
        project_description = (src.get("context_update") or "").strip() or None
        csv_scratchpad = (src.get("scratchpad_text") or "").strip()

        user_profile = _compose_user_profile(user_name, user_description, user_agent_goals)
        important_todo_list = organize_milestones(goal_ms)
        project_scratchpad = csv_scratchpad if (args.use_scratchpad_column and csv_scratchpad) else render_project_scratchpad_text(
            project, max_chars=args.max_scratchpad_chars
        )

        ex = dspy.Example(
            user_profile=user_profile,
            project_name=project,
            project_scratchpad=project_scratchpad,
            project_description=project_description,
            important_todo_list=important_todo_list,
        ).with_inputs("user_profile", "project_name", "project_scratchpad", "project_description", "important_todo_list")
        examples.append(ex)
        meta.append(
            {
                "timestamp": ts,
                "project": project,
                "user_name": user_name,
            }
        )

    out_rows: List[Dict] = []
    if examples:
        outputs = module.proposer.batch(examples)
        for m, out in zip(meta, outputs):
            raw_tasks = getattr(out, "tasks", None) or []
            tasks: List[str] = []
            for it in raw_tasks:
                if not it:
                    continue
                tasks.append(str(it).strip())
            out_rows.append(
                {
                    "timestamp": m["timestamp"],
                    "project": m["project"],
                    "user_name": m["user_name"],
                    "tasks": [t for t in tasks if t],
                }
            )

    _write_tasks_csv(output_path, out_rows)
    print(f"[dev] Wrote {len(out_rows)} rows → {output_path}")


if __name__ == "__main__":
    main()