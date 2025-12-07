# src/precursor/main.py
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Optional, Any, Dict, Set
import re
import base64
import io

import dspy
from PIL import Image as PILImage
from platformdirs import user_data_dir
from precursor.config.loader import get_user_agent_goals
import precursor.config.loader as config_loader
from precursor.context.project_history import ProjectHistory
from precursor.managers.state_manager import StateManager
from precursor.managers.agent_manager import AgentManager
from precursor.managers.ui_manager import UIManager
from precursor.observers.project_transition import ProjectActivityObserver
from precursor.observers.gum_source import GumSource
from precursor.observers.csv_simulator import CSVSimulatorObserver, CSVSimulatorConfig
#

logger = logging.getLogger(__name__)


class _CsvLogger:
    """
    Append rows to a CSV with a fixed schema.
    We log both the incoming ContextEvent fields and the post-update scratchpad.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._header_written = self.path.exists() and self.path.stat().st_size > 0

    def log(self, event, result: Dict[str, Any]) -> None:
        # columns we care about
        fieldnames = [
            "timestamp",
            "project",
            "context_update",
            "user_name",
            "user_description",
            "user_agent_goals",
            "calendar_events",
            "recent_propositions",
            "screenshot_path",
            "scratchpad_text",
        ]
        with self.path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not self._header_written:
                writer.writeheader()
                self._header_written = True

            writer.writerow(
                {
                    "timestamp": event.timestamp.isoformat(),
                    "project": result.get("project", ""),
                    "context_update": event.context_update,
                    "user_name": event.user_name or "",
                    "user_description": event.user_description or "",
                    "user_agent_goals": getattr(event, "user_agent_goals", None)
                    or get_user_agent_goals()
                    or "",
                    "calendar_events": event.calendar_events or "",
                    "recent_propositions": event.recent_propositions or "",
                    "screenshot_path": result.get("screenshot_path", ""),
                    "scratchpad_text": result.get("scratchpad_text", ""),
                }
            )

class _AgentCsvLogger:
    """
    Append candidate tasks selected by AgentManager to a CSV.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._header_written = self.path.exists() and self.path.stat().st_size > 0

    def log_candidates(self, *, project: str, result: Dict[str, Any]) -> None:
        fieldnames = [
            "project",
            "task_description",
            "value_score",
            "feasibility_score",
            "safety_score",
            "user_preference_alignment_score",
            "true_score",
            "score_ratio",
        ]
        candidates = result.get("candidates", []) or []
        if not candidates:
            return
        with self.path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not self._header_written:
                writer.writeheader()
                self._header_written = True
            for c in candidates:
                writer.writerow(
                    {
                        "project": project,
                        "task_description": c.get("task_description", ""),
                        "value_score": c.get("value_score", ""),
                        "feasibility_score": c.get("feasibility_score", ""),
                        "safety_score": c.get("safety_score", ""),
                        "user_preference_alignment_score": c.get("user_preference_alignment_score", ""),
                        "true_score": c.get("_true_score", ""),
                        "score_ratio": c.get("_score_ratio", ""),
                    }
                )


class _AgentProposalsCsvLogger:
    """
    Append ALL proposed tasks (assessments) with their scores to a CSV.
    Includes a 'selected' column indicating whether it made the final candidate list.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._header_written = self.path.exists() and self.path.stat().st_size > 0

    def log_proposals(self, *, project: str, result: Dict[str, Any]) -> None:
        fieldnames = [
            "project",
            "task_description",
            "reasoning",
            "value_score",
            "feasibility_score",
            "safety_score",
            "user_preference_alignment_score",
            "true_score",
            "score_ratio",
            "selected",
        ]
        assessments = result.get("task_assessments", []) or []
        if not assessments:
            return
        # Build a quick lookup for selected candidates by task_description
        candidates = result.get("candidates", []) or []
        selected_set = {c.get("task_description", "") for c in candidates}

        # Pull weights to compute composite scores consistent with AgentManager
        try:
            import precursor.config.loader as _loader
            settings = _loader.get_settings() or {}
        except Exception:
            settings = {}
        value_w = float(settings.get("value_weight", 2.0))
        feas_w = float(settings.get("feasibility_weight", 1.5))
        align_w = float(settings.get("user_preference_alignment_weight", 0.5))
        denom = (value_w + feas_w + align_w)
        max_score = 10.0 * denom if denom > 0 else 1.0

        def _as_dict(obj: Any) -> Dict[str, Any]:
            if isinstance(obj, dict):
                return obj
            try:
                return dict(obj)
            except Exception:
                return {"task_description": str(obj)}

        with self.path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not self._header_written:
                writer.writeheader()
                self._header_written = True
            for a in assessments:
                ad = _as_dict(a)
                desc = (ad.get("task_description") or "").strip()
                reasoning = ad.get("reasoning", "")
                val = float(ad.get("value_score") or 0)
                feas = float(ad.get("feasibility_score") or 0)
                safe = float(ad.get("safety_score") or 0)  # not used in true_score; logged for completeness
                align = float(ad.get("user_preference_alignment_score") or 0)
                true_score = val * value_w + feas * feas_w + align * align_w
                ratio = (true_score / max_score) if max_score > 0 else 0.0
                writer.writerow(
                    {
                        "project": project,
                        "task_description": desc,
                        "reasoning": reasoning,
                        "value_score": val,
                        "feasibility_score": feas,
                        "safety_score": safe,
                        "user_preference_alignment_score": align,
                        "true_score": true_score,
                        "score_ratio": ratio,
                        "selected": "yes" if desc in selected_set else "no",
                    }
                )


class _AgentGoalsMilestonesCsvLogger:
    """
    Append high-level goals and their milestones to a single CSV.
    Rows: (project, goal, milestone) – milestones may be empty for goal-only entries.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._header_written = self.path.exists() and self.path.stat().st_size > 0

    def log_structure(self, *, project: str, result: Dict[str, Any]) -> None:
        fieldnames = ["project", "goal", "milestone"]
        future_goals = list(result.get("future_goals", []) or [])
        g2m: Dict[str, Any] = dict(result.get("goal_to_milestones", {}) or {})
        if not future_goals and not g2m:
            return
        with self.path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not self._header_written:
                writer.writeheader()
                self._header_written = True
            # Log each goal row, then its milestones
            for goal in future_goals:
                writer.writerow({"project": project, "goal": goal, "milestone": ""})
                for ms in (g2m.get(goal, []) or []):
                    writer.writerow({"project": project, "goal": goal, "milestone": ms})


def _resolve_scratchpad_db_path(mode: str) -> Path:
    """
    Decide which DB path to use for this run.
    """
    env_path = os.getenv("PRECURSOR_SCRATCHPAD_DB")
    if env_path:
        return Path(env_path).expanduser().resolve()

    if mode == "csv":
        return Path("dev/survey/scratchpad_sim2.db").resolve()

    # Default to platform-specific user data dir:
    # macOS:   ~/Library/Application Support/precursor/scratchpad.db
    # Linux:   ~/.local/share/precursor/scratchpad.db
    # Windows: C:\\Users\\<user>\\AppData\\Local\\precursor\\scratchpad.db
    data_dir = Path(user_data_dir(appname="precursor"))
    return (data_dir / "scratchpad.db").resolve()


async def _run_gum_mode(
    state_mgr: StateManager,
    transition_obs: ProjectActivityObserver,
    return_obs: ProjectActivityObserver,
    max_steps: Optional[int],
    csv_logger: Optional[_CsvLogger],
    cooldown_seconds: float,
    screenshot_dir: Optional[Path],
) -> None:
    processed = 0

    async def handle_event(event):
        nonlocal processed
        result = state_mgr.process_event(event)
        transition_obs.handle_processed()
        return_obs.handle_processed()

        # If configured, capture and save a screenshot for logging (GUM mode)
        if screenshot_dir is not None and getattr(event, "screenshot", None) is not None:
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            project_slug = result.get("project", "") or "unknown"
            project_slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", project_slug).strip("_")
            ts = event.timestamp.strftime("%Y%m%d_%H%M%S")
            # Extract exact bytes from data URL stored in dspy.Image.url
            img_obj = event.screenshot
            url_val = getattr(img_obj, "url", None)
            if isinstance(url_val, str) and url_val.startswith("data:"):
                # data:[<mediatype>][;base64],<data>
                try:
                    header, b64data = url_val.split(",", 1)
                    # Always save as a real PNG file
                    out_path = screenshot_dir / f"{ts}_{project_slug}.png"
                    raw = base64.b64decode(b64data)
                    pil = PILImage.open(io.BytesIO(raw))
                    pil.save(out_path, format="PNG")
                    result["screenshot_path"] = str(out_path.resolve())
                except Exception as e:
                    logger.warning("failed to decode and save data URL screenshot: %s", e)
            else:
                logger.warning("event.screenshot present but no data URL available; skipping save")

        if csv_logger is not None:
            csv_logger.log(event, result)

        if max_steps is not None:
            processed += 1
            if processed >= max_steps:
                logger.info("reached max_steps=%d in gum mode, stopping", max_steps)
                asyncio.get_running_loop().stop()

    observer = GumSource(on_event=handle_event, cooldown_seconds=cooldown_seconds)
    await observer.run()


async def _run_csv_mode(
    state_mgr: StateManager,
    transition_obs: ProjectActivityObserver,
    return_obs: ProjectActivityObserver,
    csv_path: str,
    interval_seconds: float,
    fast: bool,
    max_steps: Optional[int],
    csv_logger: Optional[_CsvLogger],
) -> None:
    processed = 0

    def handle_event(event):
        nonlocal processed
        result = state_mgr.process_event(event)
        transition_obs.handle_processed()
        return_obs.handle_processed()

        if csv_logger is not None:
            csv_logger.log(event, result)

        if max_steps is not None:
            processed += 1
            if processed >= max_steps:
                logger.info("reached max_steps=%d in csv mode, stopping", max_steps)
                # raise to break out of simulator loop
                raise StopIteration

    cfg = CSVSimulatorConfig(
        csv_path=csv_path,
        mode="asap" if fast else "interval",
        interval_seconds=interval_seconds,
    )
    observer = CSVSimulatorObserver(config=cfg)

    try:
        await observer.run(handle_event)
    except StopIteration:
        # graceful early exit
        pass


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run precursor observer pipeline.")
    parser.add_argument(
        "--mode",
        choices=["gum", "csv"],
        default="gum",
        help="Which source to use.",
    )
    parser.add_argument(
        "--csv-path",
        default="dev/survey/context_log.csv",
        help="CSV to replay in csv mode.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=60.0,
        help="Interval between simulated events in csv mode or observations in gum mode(ignored in --fast).",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="In csv mode, run as fast as possible (no sleep).",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Process at most this many events.",
    )
    parser.add_argument(
        "--force-reset",
        action="store_true",
        help="Delete the scratchpad DB at startup (useful for CSV replays).",
    )
    parser.add_argument(
        "--output-csv",
        default=None,
        help="If set, log each processed event + final scratchpad to this CSV.",
    )
    parser.add_argument(
        "--agent-output-csv",
        default=None,
        help="If set, log candidate tasks selected by AgentManager to this CSV.",
    )
    parser.add_argument(
        "--agent-proposals-csv",
        default=None,
        help="If set, log ALL proposed tasks and their scores to this CSV.",
    )
    parser.add_argument(
        "--agent-goals-milestones-csv",
        default=None,
        help="If set, log high-level goals and their milestones to this CSV.",
    )
    parser.add_argument(
        "--screenshot-dir",
        default=None,
        help="If set, save screenshots (GUM mode) here and log their paths.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
    )
    parser.add_argument(
        "--lm",
        default="openai/gpt-5-mini",
        help="Language model identifier to use with dspy (e.g., 'openai/gpt-4o-mini').",
    )
    parser.add_argument(
        "--no-deploy",
        action="store_true",
        help="Disable deployment; only score/log tasks (default: deploy enabled).",
    )
    parser.add_argument(
        "--exclude-projects",
        default="",
        help="Comma-separated list of project names to exclude entirely. Excluded events are skipped and do not count toward --max-steps.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # configure DSPy LM
    dspy.configure(lm=dspy.LM(args.lm, api_key=os.getenv("OPENAI_API_KEY"), temperature=1.0, max_tokens=24000))
    logger.info("configured dspy LM: %s", args.lm)
    
    # decide scratchpad path
    db_path = _resolve_scratchpad_db_path(args.mode)

    # set env var so store.py uses it (unless user already set it)
    if "PRECURSOR_SCRATCHPAD_DB" not in os.environ:
        os.environ["PRECURSOR_SCRATCHPAD_DB"] = str(db_path)

    # nuclear option
    if args.force_reset and db_path.exists():
        logger.warning("force-reset enabled → deleting scratchpad DB at %s", db_path)
        db_path.unlink()

    # build core objects
    history = ProjectHistory()
    state_mgr = StateManager(history=history)
    agent_mgr = AgentManager(deploy_enabled=not args.no_deploy)
    ui_mgr = UIManager()

    # optional CSV logger
    csv_logger: Optional[_CsvLogger] = None
    agent_csv_logger: Optional[_AgentCsvLogger] = None
    agent_proposals_logger: Optional[_AgentProposalsCsvLogger] = None
    agent_goals_logger: Optional[_AgentGoalsMilestonesCsvLogger] = None
    if args.output_csv:
        csv_logger = _CsvLogger(Path(args.output_csv))
    if args.agent_output_csv:
        agent_csv_logger = _AgentCsvLogger(Path(args.agent_output_csv))
    if getattr(args, "agent_proposals_csv", None):
        agent_proposals_logger = _AgentProposalsCsvLogger(Path(args.agent_proposals_csv))
    if getattr(args, "agent_goals_milestones_csv", None):
        agent_goals_logger = _AgentGoalsMilestonesCsvLogger(Path(args.agent_goals_milestones_csv))
    screenshot_dir: Optional[Path] = Path(args.screenshot_dir).expanduser().resolve() if args.screenshot_dir else None

    # Load transition sensitivity settings (with safe defaults)
    _settings = config_loader.get_settings() or {}
    dep_min_prev = int(_settings.get("departure_min_entries_previous_segment", 3))
    dep_time_min = float(_settings.get("departure_time_threshold_minutes", 3))
    arr_min_cur = int(_settings.get("arrival_min_entries_current_segment", 1))
    arr_time_min = float(_settings.get("arrival_time_threshold_minutes", 15))

    # Determine Gum observation cooldown (seconds)
    gum_cooldown = float(_settings.get("observation_cooldown_seconds", 60.0))
    # If user provided a non-default interval and we're in gum mode, reuse it as cooldown
    try:
        _arg_interval = float(args.interval_seconds)
    except Exception:
        _arg_interval = None
    if args.mode == "gum" and _arg_interval is not None and _arg_interval != 180.0:
        gum_cooldown = _arg_interval

    def _on_trigger(project: str, result: Dict[str, Any]) -> None:
        if agent_csv_logger is not None:
            agent_csv_logger.log_candidates(project=project, result=result)
        if 'agent_proposals_logger' in locals() and agent_proposals_logger is not None:
            agent_proposals_logger.log_proposals(project=project, result=result)
        if 'agent_goals_logger' in locals() and agent_goals_logger is not None:
            agent_goals_logger.log_structure(project=project, result=result)

    transition_obs = ProjectActivityObserver(
        history=history,
        agent_manager=agent_mgr,
        mode="departure",
        window_size=20,
        min_entries_previous_segment=dep_min_prev,
        time_threshold=timedelta(minutes=dep_time_min),
        on_trigger=(
            _on_trigger if (agent_csv_logger or agent_proposals_logger or agent_goals_logger) else None
        ),
    )
    # Arrival observer → calls UIManager, which will notify only if pending tasks exist.
    return_obs = ProjectActivityObserver(
        history=history,
        agent_manager=ui_mgr,
        mode="arrival",
        window_size=20,
        min_entries_current_segment=arr_min_cur,
        time_threshold=timedelta(minutes=arr_time_min),
        on_trigger=None,
    )

    # parse excluded projects (normalized to lowercase)
    excluded_projects: Optional[Set[str]] = None
    if getattr(args, "exclude_projects", ""):
        parts = [p.strip().lower() for p in str(args.exclude_projects).split(",")]
        filtered = {p for p in parts if p}
        excluded_projects = filtered if filtered else None

    # re-create state manager with excluded projects knowledge
    # (StateManager will classify and skip scratchpad/history if excluded)
    state_mgr = StateManager(history=history)
    if excluded_projects:
        # set attribute if supported; otherwise StateManager will handle gracefully when None
        try:
            state_mgr.excluded_projects = excluded_projects
        except Exception:
            pass

    # run
    if args.mode == "gum":
        logger.info("starting in GUM mode")
        await _run_gum_mode(state_mgr, transition_obs, return_obs, args.max_steps, csv_logger, gum_cooldown, screenshot_dir)
    else:
        logger.info("starting in CSV mode (%s)", args.csv_path)
        await _run_csv_mode(
            state_mgr,
            transition_obs,
            return_obs,
            csv_path=args.csv_path,
            interval_seconds=args.interval_seconds,
            fast=args.fast,
            max_steps=args.max_steps,
            csv_logger=csv_logger,
        )


if __name__ == "__main__":
    asyncio.run(main())

# Example usage:
# Full (GUM) run with both logs:
#   python -m precursor.main --mode gum --output-csv dev/survey/pipeline_run.csv --agent-output-csv dev/survey/pipeline_run.agent_candidates.csv --agent-proposals-csv dev/survey/pipeline_run.proposals.csv --agent-goals-milestones-csv dev/survey/pipeline_run.goals_milestones.csv --screenshot-dir dev/survey/screenshots --log-level INFO
#
# CSV replay with fast mode and both logs:
#   python -m precursor.main --mode csv --csv-path dev/survey/pipeline_run.csv --fast --output-csv dev/survey/data_collection/11_20_experiments/full_pipeline/log.csv --agent-output-csv dev/survey/data_collection/11_20_experiments/full_pipeline/agent_candidates.csv --agent-proposals-csv dev/survey/data_collection/11_20_experiments/full_pipeline/proposals.csv --agent-goals-milestones-csv dev/survey/data_collection/11_20_experiments/full_pipeline/goals_milestones.csv --force-reset --max-steps 75 --no-deploy --exclude-projects "Cotomata"
#   python -m precursor.main --mode csv --csv-path dev/survey/context_log.csv --fast --output-csv dev/survey/pipeline_run_no_next_steps.csv --agent-output-csv dev/survey/pipeline_run_no_next_steps.agent_candidates.csv --log-level INFO --force-reset --max-steps 25 --no-deploy