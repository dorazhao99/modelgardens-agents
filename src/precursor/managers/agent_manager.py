# src/precursor/managers/agent_manager.py
from __future__ import annotations

import logging
from typing import Optional

from precursor.scratchpad import render as scratchpad_render
from precursor.components.feasibility_estimator import FeasibilityEstimator

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Given a project name:
      1. load its scratchpad
      2. run feasibility over the actions we can see in that scratchpad
      3. return / log high-feasibility actions
      4. (future) dispatch agents for those actions

    This is intentionally small and opinionated.
    """

    def __init__(
        self,
        *,
        feasibility_estimator: Optional[FeasibilityEstimator] = None,
        feasibility_threshold: int = 7,
    ) -> None:
        self.feasibility_estimator = feasibility_estimator or FeasibilityEstimator()
        self.feasibility_threshold = feasibility_threshold

    def run_for_project(self, project_name: str) -> dict:
        """
        Main entrypoint: run feasibility for this project right now.
        """
        logger.info("agent_manager: running for project %s", project_name)

        # 1) get latest scratchpad
        scratchpad_text = scratchpad_render.render_project_scratchpad(project_name)
        if not scratchpad_text.strip():
            logger.warning(
                "agent_manager: project %s has empty scratchpad, skipping feasibility",
                project_name,
            )
            return {
                "project": project_name,
                "actions": [],
                "candidates": [],
            }

        # 2) run feasibility on it
        results = self.feasibility_estimator(project_scratchpad=scratchpad_text)

        # 3) pick high-feasibility ones
        candidates = [
            r for r in results
            if getattr(r, "feasibility", 0) >= self.feasibility_threshold
        ]

        # 4) log them
        for r in results:
            logger.debug(
                "agent_manager: action=%r feasibility=%s missing=%r",
                getattr(r, "action", ""),
                getattr(r, "feasibility", ""),
                getattr(r, "missing_context", None),
            )

        # 5) future: actually dispatch here
        # -------------------------------------------------
        # for c in candidates:
        #     launch_agent_for_action(
        #         project_name=project_name,
        #         action=c.action,
        #         scratchpad=scratchpad_text,
        #     )
        # -------------------------------------------------

        # return structured so tests / callers can inspect
        return {
            "project": project_name,
            "actions": [
                r.model_dump() if hasattr(r, "model_dump") else r for r in results
            ],
            "candidates": [
                c.model_dump() if hasattr(c, "model_dump") else c for c in candidates
            ],
        }