# src/precursor/main.py
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Optional, Any, Dict

import dspy
from precursor.config.loader import get_user_agent_goals
import precursor.config.loader as config_loader
from precursor.context.project_history import ProjectHistory
from precursor.managers.state_manager import StateManager
from precursor.managers.agent_manager import AgentManager
from precursor.managers.ui_manager import UIManager
from precursor.observers.project_transition import ProjectActivityObserver
from precursor.observers.gum_source import GumSource
from precursor.observers.csv_simulator import CSVSimulatorObserver, CSVSimulatorConfig

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


def _resolve_scratchpad_db_path(mode: str) -> Path:
    """
    Decide which DB path to use for this run.
    """
    env_path = os.getenv("PRECURSOR_SCRATCHPAD_DB")
    if env_path:
        return Path(env_path).expanduser().resolve()

    if mode == "csv":
        return Path("dev/survey/scratchpad_sim2.db").resolve()

    return Path("scratchpad.db").resolve()


async def _run_gum_mode(
    state_mgr: StateManager,
    transition_obs: ProjectActivityObserver,
    return_obs: ProjectActivityObserver,
    max_steps: Optional[int],
    csv_logger: Optional[_CsvLogger],
    cooldown_seconds: float,
) -> None:
    processed = 0

    async def handle_event(event):
        nonlocal processed
        result = state_mgr.process_event(event)
        transition_obs.handle_processed()
        return_obs.handle_processed()

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
    if args.output_csv:
        csv_logger = _CsvLogger(Path(args.output_csv))
    if args.agent_output_csv:
        agent_csv_logger = _AgentCsvLogger(Path(args.agent_output_csv))

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

    transition_obs = ProjectActivityObserver(
        history=history,
        agent_manager=agent_mgr,
        mode="departure",
        window_size=20,
        min_entries_previous_segment=dep_min_prev,
        time_threshold=timedelta(minutes=dep_time_min),
        on_trigger=(
            (lambda project, result: agent_csv_logger.log_candidates(project=project, result=result))
            if agent_csv_logger is not None
            else None
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

    # run
    if args.mode == "gum":
        logger.info("starting in GUM mode")
        await _run_gum_mode(state_mgr, transition_obs, return_obs, args.max_steps, csv_logger, gum_cooldown)
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
#   python -m precursor.main --mode gum --output-csv dev/survey/pipeline_run.csv --agent-output-csv dev/survey/pipeline_run.agent_candidates.csv --log-level INFO
#
# CSV replay with fast mode and both logs:
#   python -m precursor.main --mode csv --csv-path dev/survey/context_log.csv --fast --output-csv dev/survey/pipeline_run_no_next_steps.csv --agent-output-csv dev/survey/pipeline_run_no_next_steps.agent_candidates.csv --log-level INFO --force-reset --max-steps 25 --no-deploy