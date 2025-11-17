# tests/observers/test_project_transition_observer.py

from datetime import datetime, timedelta

from precursor.context.project_history import ProjectHistory
from precursor.observers.project_transition import ProjectActivityObserver


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
    obs = ProjectActivityObserver(
        history=history,
        agent_manager=agent_mgr,
        mode="departure",
        min_entries_previous_segment=3,
        time_threshold=timedelta(minutes=10),
    )

    obs.handle_processed()

    assert agent_mgr.calls == ["Project Alpha"]


def test_arrival_triggers_on_return_after_absence():
    """
    History (newest first):
      0 min ago: Project Alpha        ← current segment start
      6 min ago: Project Beta
      9 min ago: Project Beta
      12 min ago: Project Beta        ← different project segment in between
      24 min ago: Project Alpha
      27 min ago: Project Alpha
      30 min ago: Project Alpha       ← previous Alpha segment (end at 24)

    We left Alpha 24 minutes ago (end of its previous segment), and just returned to Alpha
    with a current-segment size of 1 → should trigger Alpha when threshold is 15 minutes.
    """
    history = ProjectHistory(max_len=20)
    # chronological appends
    history.append(timestamp=datetime.now() - timedelta(minutes=30), project="Project Alpha", objectives=[])
    history.append(timestamp=datetime.now() - timedelta(minutes=27), project="Project Alpha", objectives=[])
    history.append(timestamp=datetime.now() - timedelta(minutes=24), project="Project Alpha", objectives=[])
    history.append(timestamp=datetime.now() - timedelta(minutes=12), project="Project Beta", objectives=[])
    history.append(timestamp=datetime.now() - timedelta(minutes=9), project="Project Beta", objectives=[])
    history.append(timestamp=datetime.now() - timedelta(minutes=6), project="Project Beta", objectives=[])
    history.append(timestamp=datetime.now(), project="Project Alpha", objectives=[])

    agent_mgr = FakeAgentManager()
    obs = ProjectActivityObserver(
        history=history,
        agent_manager=agent_mgr,
        mode="arrival",
        min_entries_current_segment=1,
        time_threshold=timedelta(minutes=15),
    )

    obs.handle_processed()

    assert agent_mgr.calls == ["Project Alpha"]


def test_arrival_does_not_trigger_when_absence_too_short():
    """
    Return to Alpha but absence < threshold → no trigger.
    """
    history = ProjectHistory(max_len=20)
    # previous Alpha segment
    history.append(timestamp=datetime.now() - timedelta(minutes=8), project="Project Alpha", objectives=[])
    # brief Beta in between
    history.append(timestamp=datetime.now() - timedelta(minutes=3), project="Project Beta", objectives=[])
    # return to Alpha now (absence ~8 - 0 = 8 minutes)
    history.append(timestamp=datetime.now(), project="Project Alpha", objectives=[])

    agent_mgr = FakeAgentManager()
    obs = ProjectActivityObserver(
        history=history,
        agent_manager=agent_mgr,
        mode="arrival",
        min_entries_current_segment=1,
        time_threshold=timedelta(minutes=10),
    )

    obs.handle_processed()

    assert agent_mgr.calls == []


def test_arrival_only_triggers_once_for_same_boundary():
    """
    Arrival should dedupe on the same boundary key.
    """
    history = ProjectHistory(max_len=20)
    # older Alpha
    history.append(timestamp=datetime.now() - timedelta(minutes=20), project="Project Alpha", objectives=[])
    history.append(timestamp=datetime.now() - timedelta(minutes=18), project="Project Alpha", objectives=[])
    # Beta interlude
    history.append(timestamp=datetime.now() - timedelta(minutes=6), project="Project Beta", objectives=[])
    history.append(timestamp=datetime.now() - timedelta(minutes=3), project="Project Beta", objectives=[])
    # return to Alpha now
    history.append(timestamp=datetime.now(), project="Project Alpha", objectives=[])

    agent_mgr = FakeAgentManager()
    obs = ProjectActivityObserver(
        history=history,
        agent_manager=agent_mgr,
        mode="arrival",
        min_entries_current_segment=1,
        time_threshold=timedelta(minutes=10),
    )

    obs.handle_processed()
    obs.handle_processed()  # second call, no new data

    assert agent_mgr.calls == ["Project Alpha"]


def test_does_not_trigger_when_previous_segment_too_short():
    history = ProjectHistory(max_len=20)
    # short Alpha segment
    history.append(timestamp=datetime.now() - timedelta(minutes=5), project="Project Alpha", objectives=[])
    # now Beta
    history.append(timestamp=datetime.now() - timedelta(minutes=2), project="Project Beta", objectives=[])
    history.append(timestamp=datetime.now(), project="Project Beta", objectives=[])

    agent_mgr = FakeAgentManager()
    obs = ProjectActivityObserver(
        history=history,
        agent_manager=agent_mgr,
        mode="departure",
        min_entries_previous_segment=2,
        time_threshold=timedelta(minutes=8),
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
    obs = ProjectActivityObserver(
        history=history,
        agent_manager=agent_mgr,
        mode="departure",
        min_entries_previous_segment=3,
        time_threshold=timedelta(minutes=5),
    )

    obs.handle_processed()
    obs.handle_processed()  # second call, no new data

    assert agent_mgr.calls == ["Project Alpha"]