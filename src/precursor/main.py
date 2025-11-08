# src/precursor/main.py
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import timedelta

from precursor.context.project_history import ProjectHistory
from precursor.managers.state_manager import StateManager
from precursor.managers.agent_manager import AgentManager
from precursor.observers.project_transition import ProjectTransitionObserver
from precursor.observers.gum_source import GumSourceObserver
from precursor.observers.csv_simulator import CSVSimulatorObserver


logger = logging.getLogger(__name__)


async def _run_gum_mode(state_mgr: StateManager, transition_obs: ProjectTransitionObserver) -> None:
    """
    Real-time mode: listen to gum updates and run the pipeline.
    """
    async def handle_event(event):
        # run the core pipeline
        state_mgr.process_event(event)
        # let the transition observer look at the updated history
        transition_obs.handle_processed()

    observer = GumSourceObserver(on_event=handle_event)
    await observer.run()


async def _run_csv_mode(
    state_mgr: StateManager,
    transition_obs: ProjectTransitionObserver,
    csv_path: str,
    interval_seconds: float,
    fast: bool,
) -> None:
    """
    Simulation mode: replay a CSV of events.
    """
    async def handle_event(event):
        state_mgr.process_event(event)
        transition_obs.handle_processed()

    observer = CSVSimulatorObserver(
        csv_path=csv_path,
        on_event=handle_event,
        interval_seconds=interval_seconds,
        fast=fast,
    )
    await observer.run()


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
        default=180.0,
        help="Interval between simulated events in csv mode (ignored in fast mode).",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="In csv mode, run as fast as possible (no sleep).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    history = ProjectHistory()
    state_mgr = StateManager(history=history)
    agent_mgr = AgentManager()
    transition_obs = ProjectTransitionObserver(
        history=history,
        agent_manager=agent_mgr,
        min_entries_same=3,
        min_stable_duration=timedelta(minutes=3),
    )

    if args.mode == "gum":
        logger.info("starting in GUM mode")
        await _run_gum_mode(state_mgr, transition_obs)
    else:
        logger.info("starting in CSV mode (%s)", args.csv_path)
        await _run_csv_mode(
            state_mgr,
            transition_obs,
            csv_path=args.csv_path,
            interval_seconds=args.interval_seconds,
            fast=args.fast,
        )


if __name__ == "__main__":
    asyncio.run(main())