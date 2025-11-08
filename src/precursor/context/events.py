# src/precursor/context/events.py
"""
Lightweight, serializable event types that observers emit and managers consume.

Observers (real gum source, CSV simulator, etc.) should create a ContextEvent
and hand it to the StateManager.  Dependency-light by design.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
import dspy


@dataclass
class ContextEvent:
    """
    A single "what the user is doing right now" snapshot.

    Observers are responsible for serializing the gum output into `recent_propositions`
    as a string — this field directly feeds into the project classifier.
    """
    timestamp: datetime
    context_update: str

    # optional enrichments
    screenshot: Optional[dspy.Image] = None

    # identity / profile
    user_name: Optional[str] = None
    user_description: Optional[str] = None  # from user.yaml

    # structured context
    calendar_events: Optional[str] = None
    recent_propositions: Optional[str] = None  # serialized gum.recent() output

    # raw payload for debugging / replay
    raw: Optional[Any] = None