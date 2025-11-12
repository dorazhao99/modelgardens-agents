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


class MilestoneInducerModule(dspy.Module):
    """
    Simple DSPy module for inducing milestones for a given high-level goal.
    Batch-friendly: we use the underlying ChainOfThought for .batch([...]).
    """
    def __init__(self, *, max_scratchpad_chars: int = 8000) -> None:
        super().__init__()
        self.inducer = dspy.ChainOfThought(MilestoneInducer)
        self.max_scratchpad_chars = max_scratchpad_chars

    def forward(
        self,
        *,
        user_profile: str,
        project_name: str,
        high_level_goal: str,
        project_description: Optional[str] = None,
        project_scratchpad: Optional[str] = None,
    ) -> List[str]:
        if not project_scratchpad:
            project_scratchpad = render_project_scratchpad_text(
                project_name,
                max_chars=self.max_scratchpad_chars,
            )
        output = self.inducer(
            user_profile=user_profile,
            project_name=project_name,
            project_scratchpad=project_scratchpad,
            project_description=project_description,
            high_level_goal=high_level_goal,
        )
        raw = getattr(output, "milestones", None) or []
        milestones: List[str] = []
        for m in raw:
            if not m:
                continue
            milestones.append(str(m).strip())
        return [m for m in milestones if m]


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


def _index_goals_by_project(goals_rows: List[Dict]) -> Dict[str, List[str]]:
    """
    Input: rows from pipeline_run.future_goals.csv
    Columns expected: project, goals (pipe-separated string)
    Return: map project -> list of goals
    """
    by_project: Dict[str, List[str]] = {}
    for r in goals_rows:
        project = (r.get("project") or "").strip()
        if not project:
            continue
        goals_str = (r.get("goals") or "").strip()
        if not goals_str:
            continue
        goals_list = [g.strip() for g in goals_str.split("|") if g.strip()]
        if not goals_list:
            continue
        by_project[project] = goals_list
    return by_project


def _write_milestones_csv(path: str, rows: List[Dict]) -> None:
    """
    Columns: timestamp, project, user_name, high_level_goal, milestones
    'milestones' is pipe-separated string.
    """
    fieldnames = ["timestamp", "project", "user_name", "high_level_goal", "milestones"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            ms = r.get("milestones") or []
            ms_str = " | ".join([m for m in ms if m])
            writer.writerow(
                {
                    "timestamp": r.get("timestamp") or "",
                    "project": r.get("project") or "",
                    "user_name": r.get("user_name") or "",
                    "high_level_goal": r.get("high_level_goal") or "",
                    "milestones": ms_str,
                }
            )


def _default_out_path(input_path: str) -> str:
    base, _ = os.path.splitext(os.path.abspath(input_path))
    return base + ".milestones.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="DEV runner: induce milestones for high-level goals using DSPy batch mode.")
    parser.add_argument("--input", required=True, help="Path to pipeline_run.csv")
    parser.add_argument("--goals", required=True, help="Path to pipeline_run.future_goals.csv (from task proposer)")
    parser.add_argument("--output", default=None, help="Output CSV path (default: <input>.milestones.csv)")
    parser.add_argument("--use-scratchpad-column", action="store_true", help="Use 'scratchpad_text' column from input CSV when present.")
    parser.add_argument("--max-scratchpad-chars", type=int, default=8000, help="Max chars if rendering scratchpad.")
    args = parser.parse_args()

    # Configure DSPy for local dev (same as other dev runner).
    dspy.configure(lm=dspy.LM('openai/gpt-5-mini', api_key=os.getenv("OPENAI_API_KEY"), temperature=1.0, max_tokens=24000))

    module = MilestoneInducerModule(max_scratchpad_chars=args.max_scratchpad_chars)

    input_path = os.path.abspath(args.input)
    goals_path = os.path.abspath(args.goals)
    output_path = os.path.abspath(args.output) if args.output else _default_out_path(input_path)

    in_rows = _read_csv(input_path)
    goals_rows = _read_csv(goals_path)
    project_to_goals = _index_goals_by_project(goals_rows)

    # Build batch examples: one example per (row x goal)
    examples: List[dspy.Example] = []
    meta: List[Dict] = []

    for row in in_rows:
        project = (row.get("project") or "").strip()
        if not project:
            continue
        user_name = (row.get("user_name") or "").strip()
        user_description = (row.get("user_description") or "").strip()
        user_agent_goals = (row.get("user_agent_goals") or "").strip()
        project_description = (row.get("context_update") or "").strip() or None
        csv_scratchpad = (row.get("scratchpad_text") or "").strip()

        high_level_goals = project_to_goals.get(project, [])
        if not high_level_goals:
            continue

        user_profile = _compose_user_profile(user_name, user_description, user_agent_goals)
        project_scratchpad = csv_scratchpad if (args.use_scratchpad_column and csv_scratchpad) else render_project_scratchpad_text(
            project, max_chars=args.max_scratchpad_chars
        )

        for goal in high_level_goals:
            ex = dspy.Example(
                user_profile=user_profile,
                project_name=project,
                project_scratchpad=project_scratchpad,
                project_description=project_description,
                high_level_goal=goal,
            ).with_inputs("user_profile", "project_name", "project_scratchpad", "project_description", "high_level_goal")
            examples.append(ex)
            meta.append(
                {
                    "timestamp": row.get("timestamp") or "",
                    "project": project,
                    "user_name": user_name,
                    "high_level_goal": goal,
                }
            )

    out_rows: List[Dict] = []
    if examples:
        # DSPy will show its own progress bar for batch.
        outputs = module.inducer.batch(examples)
        for m, out in zip(meta, outputs):
            raw_ms = getattr(out, "milestones", None) or []
            milestones: List[str] = []
            for it in raw_ms:
                if not it:
                    continue
                milestones.append(str(it).strip())
            out_rows.append(
                {
                    "timestamp": m["timestamp"],
                    "project": m["project"],
                    "user_name": m["user_name"],
                    "high_level_goal": m["high_level_goal"],
                    "milestones": [s for s in milestones if s],
                }
            )

    _write_milestones_csv(output_path, out_rows)
    print(f"[dev] Wrote {len(out_rows)} rows → {output_path}")


if __name__ == "__main__":
    main()
