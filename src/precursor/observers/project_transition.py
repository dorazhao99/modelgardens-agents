# src/precursor/observers/project_transition.py
"""
ProjectTransitionObserver

This observer is for the *departure* case:

- user was on PROJECT_A for a good stretch
- then user switched to PROJECT_B
- → we trigger background work for PROJECT_A (the one we just left)

Key detail (to match tests):
We measure the duration of the segment we just left as:
    duration = (start of CURRENT segment) - (start of PREVIOUS segment)

i.e. "we were on Alpha from when we first saw Alpha until we started Beta".
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional, List, Tuple
import logging

from precursor.context.project_history import ProjectHistory, ProjectReading
from precursor.managers.agent_manager import AgentManager

logger = logging.getLogger(__name__)


class ProjectTransitionObserver:
    def __init__(
        self,
        *,
        history: ProjectHistory,
        agent_manager: AgentManager,
        min_entries_per_segment: int = 3,
        min_segment_duration: timedelta = timedelta(minutes=10),
    ) -> None:
        self.history = history
        self.agent_manager = agent_manager
        self.min_entries_per_segment = min_entries_per_segment
        self.min_segment_duration = min_segment_duration

        # prevent re-firing on the same boundary
        self._last_triggered_key: Optional[str] = None

    def handle_processed(self) -> None:
        # history.recent() returns oldest → newest
        entries: List[ProjectReading] = self.history.recent(20)
        if len(entries) < 2:
            return

        current_seg, previous_seg = self._last_two_segments(entries)
        if previous_seg is None:
            return

        (
            current_project,
            current_start,
            current_end,
            current_count,
        ) = current_seg
        (
            prev_project,
            prev_start,
            prev_end,
            prev_count,
        ) = previous_seg

        # 1) enough samples in the previous segment?
        if prev_count < self.min_entries_per_segment:
            return

        # 2) measure duration as "we were on prev_project from its first
        #    timestamp until we started the current segment"
        duration = current_start - prev_start
        if duration < self.min_segment_duration:
            return

        # 3) dedupe
        seg_key = f"{prev_project}:{prev_start.isoformat()}:{current_start.isoformat()}"
        if self._last_triggered_key == seg_key:
            return

        logger.info(
            "project transition detected: left %s (entries=%d, duration=%s) → triggering agent",
            prev_project,
            prev_count,
            duration,
        )

        # real agent manager hook
        self.agent_manager.run_for_project(prev_project)

        self._last_triggered_key = seg_key

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _last_two_segments(
        self, entries: List[ProjectReading]
    ) -> Tuple[
        Tuple[str, object, object, int],
        Optional[Tuple[str, object, object, int]],
    ]:
        """
        entries: oldest → newest

        We walk backward (from newest) to build:
          - current segment (last contiguous block of same project)
          - previous segment (the block right before that)
        """
        n = len(entries)
        idx = n - 1

        # --- current segment (newest block) ---
        cur_project = entries[idx].project
        cur_end = entries[idx].timestamp
        cur_start = entries[idx].timestamp
        cur_count = 1
        idx -= 1

        while idx >= 0 and entries[idx].project == cur_project:
            cur_start = entries[idx].timestamp
            cur_count += 1
            idx -= 1

        current_segment = (cur_project, cur_start, cur_end, cur_count)

        # no previous segment
        if idx < 0:
            return current_segment, None

        # --- previous segment ---
        prev_project = entries[idx].project
        prev_end = entries[idx].timestamp
        prev_start = entries[idx].timestamp
        prev_count = 1
        idx -= 1

        while idx >= 0 and entries[idx].project == prev_project:
            prev_start = entries[idx].timestamp
            prev_count += 1
            idx -= 1

        previous_segment = (prev_project, prev_start, prev_end, prev_count)
        return current_segment, previous_segment