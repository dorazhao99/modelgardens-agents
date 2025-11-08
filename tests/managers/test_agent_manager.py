# tests/managers/test_agent_manager.py
from __future__ import annotations

from typing import Any, List

from precursor.managers.agent_manager import AgentManager


class FakeFeasibilityEstimator:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def __call__(self, *, project_scratchpad: str) -> List[Any]:
        # record the call
        self.calls.append({"project_scratchpad": project_scratchpad})
        # return something that looks like your ActionFeasibility pydantic models
        class FakeObj:
            def __init__(self, action, feasibility, missing_context=None):
                self.action = action
                self.feasibility = feasibility
                self.missing_context = missing_context

            def model_dump(self):
                return {
                    "action": self.action,
                    "feasibility": self.feasibility,
                    "missing_context": self.missing_context,
                }

        return [
            FakeObj("high-value action", 9),
            FakeObj("meh action", 3),
        ]


def test_agent_manager_calls_feasibility(monkeypatch):
    # patch the real scratchpad render to return a deterministic string
    def fake_render(name: str) -> str:
        return f"--- Scratchpad for {name} ---\n## Next Steps\n[1] do a thing"

    monkeypatch.setattr(
        "precursor.scratchpad.render.render_project_scratchpad",
        fake_render,
        raising=True,
    )

    fake_est = FakeFeasibilityEstimator()
    mgr = AgentManager(feasibility_estimator=fake_est, feasibility_threshold=7)

    result = mgr.run_for_project("Sim Project")

    # estimator was actually called
    assert len(fake_est.calls) == 1
    assert "Scratchpad for Sim Project" in fake_est.calls[0]["project_scratchpad"]

    # result is the dict shape agent_manager returns
    assert result["project"] == "Sim Project"
    # all actions come back
    assert len(result["actions"]) == 2
    # candidates filtered by threshold
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["action"] == "high-value action"
    assert result["candidates"][0]["feasibility"] == 9


def test_agent_manager_returns_empty_when_scratchpad_empty(monkeypatch):
    # simulate a project that has no scratchpad yet
    def fake_render(name: str) -> str:
        return "   "  # whitespace → treated as empty

    monkeypatch.setattr(
        "precursor.scratchpad.render.render_project_scratchpad",
        fake_render,
        raising=True,
    )

    fake_est = FakeFeasibilityEstimator()
    mgr = AgentManager(feasibility_estimator=fake_est)

    result = mgr.run_for_project("Empty Project")

    # we short-circuit and don't call estimator
    assert len(fake_est.calls) == 0

    assert result["project"] == "Empty Project"
    assert result["actions"] == []
    assert result["candidates"] == []