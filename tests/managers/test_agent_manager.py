# tests/managers/test_agent_manager.py
from __future__ import annotations

from typing import Any, List

from precursor.managers.agent_manager import AgentManager


def _fake_settings(
    *,
    value_weight: float = 2.0,
    feasibility_weight: float = 1.5,
    user_preference_alignment_weight: float = 0.5,
    safety_threshold: int = 7,
    deployment_threshold: float = 0.8,
    max_deployed_tasks: int = 3,
) -> dict:
    return {
        "value_weight": value_weight,
        "feasibility_weight": feasibility_weight,
        "user_preference_alignment_weight": user_preference_alignment_weight,
        "safety_threshold": safety_threshold,
        "deployment_threshold": deployment_threshold,
        "max_deployed_tasks": max_deployed_tasks,
    }


class FakeTaskPipeline:
    def __init__(self) -> None:
        self.calls: List[dict[str, Any]] = []

    def __call__(
        self,
        *,
        user_profile: str,
        project_name: str,
        project_scratchpad: str,
        project_description: str | None = None,
        user_agent_goals: str | None = None,
    ) -> dict:
        # record minimal call info
        self.calls.append(
            {
                "user_profile": user_profile,
                "project_name": project_name,
                "project_scratchpad": project_scratchpad,
                "project_description": project_description,
                "user_agent_goals": user_agent_goals,
            }
        )

        assessments = [
            {
                "task_description": "high-value action",
                "reasoning": "because reasons",
                "value_score": 10,
                "safety_score": 8,
                "feasibility_score": 9,
                "user_preference_alignment_score": 8,
            },
            {
                "task_description": "meh action",
                "reasoning": "ok",
                "value_score": 3,
                "safety_score": 8,
                "feasibility_score": 3,
                "user_preference_alignment_score": 5,
            },
        ]

        return {
            "future_goals": ["Goal A"],
            "goal_to_milestones": {"Goal A": ["M1"]},
            "agent_tasks": [a["task_description"] for a in assessments],
            "task_assessments": assessments,
        }


def test_agent_manager_calls_task_pipeline(monkeypatch):
    # settings: choose a deployment threshold that allows the top task to pass
    monkeypatch.setattr(
        "precursor.config.loader.get_settings",
        lambda: _fake_settings(deployment_threshold=0.8),
        raising=True,
    )
    # patch the real scratchpad render to return a deterministic string
    def fake_render(name: str) -> str:
        return f"--- Scratchpad for {name} ---\n## Next Steps\n[1] do a thing"

    monkeypatch.setattr(
        "precursor.scratchpad.render.render_project_scratchpad",
        fake_render,
        raising=True,
    )

    fake_pipeline = FakeTaskPipeline()
    mgr = AgentManager(task_pipeline=fake_pipeline)

    result = mgr.run_for_project(
        "Sim Project",
        user_profile="Test User",
        project_description="A test project",
    )

    # pipeline was actually called
    assert len(fake_pipeline.calls) == 1
    assert "Scratchpad for Sim Project" in fake_pipeline.calls[0]["project_scratchpad"]

    # result is the dict shape agent_manager returns
    assert result["project"] == "Sim Project"
    # all tasks and assessments come back
    assert len(result["agent_tasks"]) == 2
    assert len(result["task_assessments"]) == 2
    # candidates filtered by threshold
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["task_description"] == "high-value action"
    assert result["candidates"][0]["feasibility_score"] == 9


def test_agent_manager_returns_empty_when_scratchpad_empty(monkeypatch):
    monkeypatch.setattr(
        "precursor.config.loader.get_settings",
        lambda: _fake_settings(),
        raising=True,
    )
    # simulate a project that has no scratchpad yet
    def fake_render(name: str) -> str:
        return "   "  # whitespace → treated as empty

    monkeypatch.setattr(
        "precursor.scratchpad.render.render_project_scratchpad",
        fake_render,
        raising=True,
    )

    fake_pipeline = FakeTaskPipeline()
    mgr = AgentManager(task_pipeline=fake_pipeline)

    result = mgr.run_for_project("Empty Project")

    # we short-circuit and don't call pipeline
    assert len(fake_pipeline.calls) == 0

    assert result["project"] == "Empty Project"
    assert result["agent_tasks"] == []
    assert result["task_assessments"] == []
    assert result["candidates"] == []


def test_agent_manager_filters_below_safety_threshold(monkeypatch):
    # Configure thresholds so only safety can exclude the task
    monkeypatch.setattr(
        "precursor.config.loader.get_settings",
        lambda: _fake_settings(safety_threshold=8, deployment_threshold=0.5),
        raising=True,
    )
    # patch scratchpad
    monkeypatch.setattr(
        "precursor.scratchpad.render.render_project_scratchpad",
        lambda name: f"scratchpad for {name}",
        raising=True,
    )

    class Pipeline(FakeTaskPipeline):
        def __call__(self, **kwargs):
            assessments = [
                {
                    "task_description": "unsafe but valuable",
                    "reasoning": "n/a",
                    "value_score": 10,
                    "safety_score": 7,  # below threshold=8
                    "feasibility_score": 10,
                    "user_preference_alignment_score": 10,
                }
            ]
            return {
                "future_goals": [],
                "goal_to_milestones": {},
                "agent_tasks": [a["task_description"] for a in assessments],
                "task_assessments": assessments,
            }

    mgr = AgentManager(task_pipeline=Pipeline())
    res = mgr.run_for_project("Proj", user_profile="u")
    assert res["candidates"] == []


def test_agent_manager_filters_below_deployment_threshold(monkeypatch):
    # Use defaults: deployment_threshold ~ 0.9; craft ratio just below
    monkeypatch.setattr(
        "precursor.config.loader.get_settings",
        lambda: _fake_settings(deployment_threshold=0.9, safety_threshold=7),
        raising=True,
    )
    monkeypatch.setattr(
        "precursor.scratchpad.render.render_project_scratchpad",
        lambda name: "ok",
        raising=True,
    )

    # With weights 2.0,1.5,0.5 max_score=40
    # value=9, feas=9, align=8 -> true=35.5 -> ratio=0.8875 < 0.9
    class Pipeline(FakeTaskPipeline):
        def __call__(self, **kwargs):
            assessments = [
                {
                    "task_description": "just misses threshold",
                    "reasoning": "n/a",
                    "value_score": 9,
                    "safety_score": 9,
                    "feasibility_score": 9,
                    "user_preference_alignment_score": 8,
                }
            ]
            return {
                "future_goals": [],
                "goal_to_milestones": {},
                "agent_tasks": [a["task_description"] for a in assessments],
                "task_assessments": assessments,
            }

    mgr = AgentManager(task_pipeline=Pipeline())
    res = mgr.run_for_project("Proj", user_profile="u")
    assert res["candidates"] == []


def test_agent_manager_respects_max_deployed_and_weighted_tiebreak(monkeypatch):
    # Set alignment weight to 0 to simplify equal true scores; max 2 tasks
    monkeypatch.setattr(
        "precursor.config.loader.get_settings",
        lambda: _fake_settings(
            value_weight=2.0,
            feasibility_weight=1.0,
            user_preference_alignment_weight=0.0,
            deployment_threshold=0.5,
            safety_threshold=7,
            max_deployed_tasks=2,
        ),
        raising=True,
    )
    monkeypatch.setattr(
        "precursor.scratchpad.render.render_project_scratchpad",
        lambda name: "ok",
        raising=True,
    )

    # All three have equal true score = 18 with weights (2.0, 1.0, 0.0)
    # B: higher value should come first in tie-break; then A; then C
    assessments = [
        {
            "task_description": "A-mid-value",
            "reasoning": "n/a",
            "value_score": 8,   # 18
            "safety_score": 9,
            "feasibility_score": 2,
            "user_preference_alignment_score": 0,
        },
        {
            "task_description": "B-high-value",
            "reasoning": "n/a",
            "value_score": 9,   # 16 + feas 2 = 18
            "safety_score": 9,
            "feasibility_score": 0,
            "user_preference_alignment_score": 0,
        },
        {
            "task_description": "C-low-value",
            "reasoning": "n/a",
            "value_score": 7,   # 14 + feas 4 = 18
            "safety_score": 9,
            "feasibility_score": 4,
            "user_preference_alignment_score": 0,
        },
    ]

    class Pipeline(FakeTaskPipeline):
        def __call__(self, **kwargs):
            return {
                "future_goals": [],
                "goal_to_milestones": {},
                "agent_tasks": [a["task_description"] for a in assessments],
                "task_assessments": assessments,
            }

    mgr = AgentManager(task_pipeline=Pipeline())
    res = mgr.run_for_project("Proj", user_profile="u")

    # Only top 2 tasks remain, ordered by value (highest weight)
    assert [c["task_description"] for c in res["candidates"]] == [
        "B-high-value",
        "A-mid-value",
    ]