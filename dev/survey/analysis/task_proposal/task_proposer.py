import dspy
from typing import Optional, List
import csv
import argparse
import os
import sys
from typing import Dict
from dotenv import load_dotenv

load_dotenv()

try:
    from tqdm import tqdm
except Exception:
    def tqdm(x, **kwargs):
        return x

try:
    from precursor.scratchpad.utils import render_project_scratchpad_text
except Exception:
    # Allow running from dev/ without PYTHONPATH=src
    here = os.path.dirname(os.path.abspath(__file__))
    src_root = os.path.abspath(os.path.join(here, "../../../..", "src"))
    if src_root not in sys.path:
        sys.path.append(src_root)
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
    def __init__(self, *, max_scratchpad_chars: int = 8000) -> None:
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


# ---------------------------------------------------------------------------
# Dev-only helpers (simple and local on purpose)
# ---------------------------------------------------------------------------

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


def _write_goals_csv(path: str, rows: List[Dict]) -> None:
    """
    Write a minimal CSV with a single 'goals' column (pipe-separated).
    """
    fieldnames = ["timestamp", "project", "user_name", "goals"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            goals_list = r.get("goals") or []
            goals_str = " | ".join([g for g in goals_list if g])
            writer.writerow(
                {
                    "timestamp": r.get("timestamp") or "",
                    "project": r.get("project") or "",
                    "user_name": r.get("user_name") or "",
                    "goals": goals_str,
                }
            )


def _default_out_path(input_path: str) -> str:
    base, _ = os.path.splitext(os.path.abspath(input_path))
    return base + ".future_goals.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="DEV runner: induce future goals from a CSV and write a simple output CSV.")
    parser.add_argument("--input", required=True, help="Path to input CSV (e.g., dev/survey/pipeline_run.csv)")
    parser.add_argument("--output", default=None, help="Output CSV path (default: <input>.future_goals.csv)")
    parser.add_argument("--use-scratchpad-column", action="store_true", help="Use 'scratchpad_text' column when present.")
    parser.add_argument("--max-scratchpad-chars", type=int, default=8000, help="Max chars if rendering scratchpad.")
    parser.add_argument("--batch", action="store_true", help="Process with a single DSPy .batch() call (DSPy shows its own progress).")
    args = parser.parse_args()

    dspy.configure(lm=dspy.LM('openai/gpt-5-mini', api_key=os.getenv("OPENAI_API_KEY"), temperature=1.0, max_tokens=24000))


    inducer = FutureGoalInducerModule(max_scratchpad_chars=args.max_scratchpad_chars)

    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output) if args.output else _default_out_path(input_path)

    in_rows = _read_csv(input_path)
    out_rows: List[Dict] = []

    if args.batch:
        # Build DSPy Examples and run a single .batch() call.
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

            user_profile = _compose_user_profile(user_name, user_description, user_agent_goals)
            # Use CSV scratchpad when requested; otherwise render from store.
            project_scratchpad = csv_scratchpad if (args.use_scratchpad_column and csv_scratchpad) else render_project_scratchpad_text(
                project, max_chars=args.max_scratchpad_chars
            )

            ex = dspy.Example(
                user_profile=user_profile,
                project_name=project,
                project_scratchpad=project_scratchpad,
                project_description=project_description,
                user_agent_goals=user_agent_goals or None,
            ).with_inputs("user_profile", "project_name", "project_scratchpad", "project_description", "user_agent_goals")
            examples.append(ex)
            meta.append(
                {
                    "timestamp": row.get("timestamp") or "",
                    "project": project,
                    "user_name": user_name,
                }
            )

        if examples:
            outputs = inducer.inducer.batch(examples)
            for m, out in zip(meta, outputs):
                raw_goals = getattr(out, "future_goals", None) or []
                goals: List[str] = []
                for g in raw_goals:
                    if not g:
                        continue
                    goals.append(str(g).strip())
                out_rows.append(
                    {
                        "timestamp": m["timestamp"],
                        "project": m["project"],
                        "user_name": m["user_name"],
                        "goals": [g for g in goals if g],
                    }
                )
    else:
        # Row-by-row mode with tqdm progress bar.
        for row in tqdm(in_rows, desc="Inducing future goals"):
            project = (row.get("project") or "").strip()
            if not project:
                continue

            user_name = (row.get("user_name") or "").strip()
            user_description = (row.get("user_description") or "").strip()
            user_agent_goals = (row.get("user_agent_goals") or "").strip()
            project_description = (row.get("context_update") or "").strip() or None
            csv_scratchpad = (row.get("scratchpad_text") or "").strip()

            user_profile = _compose_user_profile(user_name, user_description, user_agent_goals)

            goals = inducer(
                user_profile=user_profile,
                project_name=project,
                project_description=project_description,
                user_agent_goals=user_agent_goals or None,
                project_scratchpad=csv_scratchpad if (args.use_scratchpad_column and csv_scratchpad) else None,
            )

            out_rows.append(
                {
                    "timestamp": row.get("timestamp") or "",
                    "project": project,
                    "user_name": user_name,
                    "goals": goals,
                }
            )

    _write_goals_csv(output_path, out_rows)
    print(f"[dev] Wrote {len(out_rows)} rows → {output_path}")


if __name__ == "__main__":
    main()