# tests/observers/test_project_transition_observer.py

from datetime import datetime, timedelta

from precursor.context.project_history import ProjectHistory
from precursor.observers.project_transition import ProjectTransitionObserver


class FakeAgentManager:
    def __init__(self):
        self.calls = []

    def run_for_project(self, project_name: str):
        self.calls.append(project_name)


def _entry(ts_offset_minutes: int, project: str):
    # helper to make descending timestamps easier
    return (
        datetime.now() - timedelta(minutes=ts_offset_minutes),
        project,
    )


def test_triggers_previous_project_when_switch_happens():
    """
    History (newest first):
      0 min ago: Project Beta
      3 min ago: Project Beta
      6 min ago: Project Beta
      12 min ago: Project Alpha
      15 min ago: Project Alpha
      18 min ago: Project Alpha

    We were on Alpha for a while, then switched to Beta → should trigger Alpha.
    """
    history = ProjectHistory(max_len=20)
    # append in chronological order, since ProjectHistory probably expects that
    history.append(timestamp=datetime.now() - timedelta(minutes=18), project="Project Alpha", objectives=[])
    history.append(timestamp=datetime.now() - timedelta(minutes=15), project="Project Alpha", objectives=[])
    history.append(timestamp=datetime.now() - timedelta(minutes=12), project="Project Alpha", objectives=[])
    history.append(timestamp=datetime.now() - timedelta(minutes=6), project="Project Beta", objectives=[])
    history.append(timestamp=datetime.now() - timedelta(minutes=3), project="Project Beta", objectives=[])
    history.append(timestamp=datetime.now(), project="Project Beta", objectives=[])

    agent_mgr = FakeAgentManager()
    obs = ProjectTransitionObserver(
        history=history,
        agent_manager=agent_mgr,
        min_entries_per_segment=3,
        min_segment_duration=timedelta(minutes=10),
    )

    obs.handle_processed()

    assert agent_mgr.calls == ["Project Alpha"]


def test_does_not_trigger_when_previous_segment_too_short():
    history = ProjectHistory(max_len=20)
    # short Alpha segment
    history.append(timestamp=datetime.now() - timedelta(minutes=5), project="Project Alpha", objectives=[])
    # now Beta
    history.append(timestamp=datetime.now() - timedelta(minutes=2), project="Project Beta", objectives=[])
    history.append(timestamp=datetime.now(), project="Project Beta", objectives=[])

    agent_mgr = FakeAgentManager()
    obs = ProjectTransitionObserver(
        history=history,
        agent_manager=agent_mgr,
        min_entries_per_segment=2,
        min_segment_duration=timedelta(minutes=8),
    )

    obs.handle_processed()

    assert agent_mgr.calls == []


def test_only_triggers_once_for_same_boundary():
    history = ProjectHistory(max_len=20)
    # Alpha old segment
    history.append(timestamp=datetime.now() - timedelta(minutes=14), project="Project Alpha", objectives=[])
    history.append(timestamp=datetime.now() - timedelta(minutes=11), project="Project Alpha", objectives=[])
    history.append(timestamp=datetime.now() - timedelta(minutes=9), project="Project Alpha", objectives=[])
    # Beta now
    history.append(timestamp=datetime.now() - timedelta(minutes=3), project="Project Beta", objectives=[])
    history.append(timestamp=datetime.now(), project="Project Beta", objectives=[])

    agent_mgr = FakeAgentManager()
    obs = ProjectTransitionObserver(
        history=history,
        agent_manager=agent_mgr,
        min_entries_per_segment=3,
        min_segment_duration=timedelta(minutes=5),
    )

    obs.handle_processed()
    obs.handle_processed()  # second call, no new data

    assert agent_mgr.calls == ["Project Alpha"]