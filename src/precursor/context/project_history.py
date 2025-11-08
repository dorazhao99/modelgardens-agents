# src/precursor/context/project_history.py
"""
Keeps track of the *recent* project classification history.

We intentionally keep this separate from dispatch/ so that:
- classification components can store their own history,
- agent triggers can *read* that history without owning it,
- and tests can just create a ProjectHistory() and shove entries into it.

Default: store last 20 readings.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class ProjectReading:
    """
    One classification outcome at a point in time.
    """
    timestamp: datetime
    project: str
    # optionally, store the "why" or the objectives we saw at that moment
    objectives: Optional[List[str]] = None


class ProjectHistory:
    """
    Ring-buffer style history of recent project predictions.

    - append() to add a new reading
    - recent() to get the latest K
    - last_project() to get the most recent project (or None)
    """

    def __init__(self, max_len: int = 20) -> None:
        self._max_len = max_len
        self._items: List[ProjectReading] = []

    def append(
        self,
        *,
        timestamp: datetime,
        project: str,
        objectives: Optional[List[str]] = None,
    ) -> None:
        reading = ProjectReading(
            timestamp=timestamp,
            project=project,
            objectives=objectives,
        )
        self._items.append(reading)
        # trim from the front if too many
        if len(self._items) > self._max_len:
            excess = len(self._items) - self._max_len
            self._items = self._items[excess:]

    def recent(self, n: int = 20) -> List[ProjectReading]:
        """
        Return up to n most recent readings, newest last.
        """
        if n >= len(self._items):
            return list(self._items)
        return self._items[-n:]

    def last_project(self) -> Optional[str]:
        if not self._items:
            return None
        return self._items[-1].project