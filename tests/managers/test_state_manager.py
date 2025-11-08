# tests/managers/test_state_manager.py

from datetime import datetime, timedelta
from typing import List, Any

import dspy
import pytest

from precursor.context.events import ContextEvent
from precursor.context.project_history import ProjectHistory
from precursor.managers.state_manager import StateManager


class FakeGoal:
    def __init__(self, name: str, description: str = "", weight: int = 5):
        self.name = name
        self.description = description
        self.weight = weight

    def model_dump(self):
        return {
            "name": self.name,
            "description": self.description,
            "weight": self.weight,
        }


class FakeObjectivesInducer:
    def __init__(self, goals: List[FakeGoal]):
        self.goals = goals
        self.calls: List[dict] = []

    def __call__(self, *, context: str, limit: int, screenshot: dspy.Image | None):
        # record for assertions
        self.calls.append({"context": context, "limit": limit, "screenshot": screenshot})
        # mimic real return: (goals, reasoning)
        return self.goals, "fake reasoning"


class FakeProjectClassifier:
    def __init__(self, project: str = "Project Alpha"):
        self.project = project
        self.calls: List[dict] = []

    def __call__(
        self,
        *,
        recent_objectives: str,
        recent_propositions: str,
        calendar_events: str,
        screenshot: dspy.Image,
        recent_project_predictions: list[str],
    ):
        self.calls.append(
            {
                "recent_objectives": recent_objectives,
                "recent_propositions": recent_propositions,
                "calendar_events": calendar_events,
                "recent_project_predictions": recent_project_predictions,
            }
        )
        # return an object with a .project attribute (like dspy result)
        return type("Res", (), {"project": self.project})


class FakeScratchpadUpdater:
    def __init__(self):
        self.calls: List[dict] = []

    def __call__(
        self,
        *,
        project_name: str,
        user_context: str,
        current_screenshot: dspy.Image,
        user_profile: str = "",
        current_scratchpad: str | None = None,
        speculated_current_objectives: list[str] | None = None,
        speculated_former_objectives: list[str] | None = None,
        calendar_events: list[str] | None = None,
        full_project_list: list[str] | None = None,
    ):
        self.calls.append(
            {
                "project_name": project_name,
                "user_context": user_context,
                "speculated_current_objectives": speculated_current_objectives or [],
                "speculated_former_objectives": speculated_former_objectives or [],
                "calendar_events": calendar_events or [],
                "full_project_list": full_project_list or [],
            }
        )
        return "made some edits", "REFRESHED_SCRATCHPAD_TEXT"


def _make_event(
    *,
    context_update="working on alpha engine",
    recent_propositions="alpha.md was edited",
    calendar_events="Alpha sync tomorrow",
):
    # we don’t care about screenshot here — state_manager will create 1x1 fallback
    return ContextEvent(
        timestamp=datetime.now(),
        context_update=context_update,
        user_name="Test User",
        user_description="test user description",
        calendar_events=calendar_events,
        recent_propositions=recent_propositions,
        screenshot=None,
        raw=None,
    )


def test_state_manager_happy_path():
    history = ProjectHistory()
    inducer = FakeObjectivesInducer(
        goals=[
            FakeGoal("Draft outline", "Write the outline for the spec", 8),
            FakeGoal("Collect references", "Find related work", 6),
        ]
    )
    classifier = FakeProjectClassifier(project="Project Alpha")
    scratchpad = FakeScratchpadUpdater()

    sm = StateManager(
        history=history,
        objectives_inducer=inducer,
        project_classifier=classifier,
        scratchpad_updater=scratchpad,
    )

    event = _make_event()
    result = sm.process_event(event)

    # result structure
    assert result["project"] == "Project Alpha"
    assert len(result["induced_goals"]) == 2

    # history updated
    recent = history.recent(1)
    assert len(recent) == 1
    assert recent[0].project == "Project Alpha"
    assert recent[0].objectives == ["Draft outline | Write the outline for the spec | weight=8", "Collect references | Find related work | weight=6"]

    # classifier got the propositions from the event
    assert classifier.calls[0]["recent_propositions"] == "alpha.md was edited"

    # scratchpad got rich objectives (name + desc)
    sp_call = scratchpad.calls[0]
    current_objs = sp_call["speculated_current_objectives"]
    assert any("Draft outline" in s for s in current_objs)
    assert any("Collect references" in s for s in current_objs)


def test_state_manager_passes_calendar_lines_to_scratchpad():
    history = ProjectHistory()
    inducer = FakeObjectivesInducer(goals=[FakeGoal("Do thing", "desc", 5)])
    classifier = FakeProjectClassifier(project="Project Beta")
    scratchpad = FakeScratchpadUpdater()

    sm = StateManager(
        history=history,
        objectives_inducer=inducer,
        project_classifier=classifier,
        scratchpad_updater=scratchpad,
    )

    event = _make_event(calendar_events="Meeting A\nMeeting B")
    sm.process_event(event)

    sp_call = scratchpad.calls[0]
    assert sp_call["calendar_events"] == ["Meeting A", "Meeting B"]