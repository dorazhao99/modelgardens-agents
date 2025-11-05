# tests/components/test_current_project_classifier.py
from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any, Dict, List
import types

import pytest


@pytest.fixture
def classifier_test_env(tmp_path, monkeypatch):
    """
    Test env that:

    1. Creates a temp projects.yaml with 3 projects (one 'agent_enabled: false')
    2. Points PRECURSOR_PROJECTS_FILE to it
    3. Redirects scratchpad DB to a temp dir
    4. Replaces scratchpad.render.render_project_scratchpad with a deterministic function
    5. Installs a FAKE dspy that CAPTURES kwargs and PRINTS them
    6. Reloads the module under test AFTER stubbing dspy so the module uses the fake
    """
    # ------------------------------------------
    # 1) temp dirs
    # ------------------------------------------
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    projects_yaml = config_dir / "projects.yaml"
    projects_yaml.write_text(
        """projects:
  - name: "Project Alpha"
    description: "LLM reasoning engine"
    agent_enabled: true
  - name: "Project Beta"
    description: "Data pipeline for embeddings"
    agent_enabled: true
  - name: "Project Gamma"
    description: "Internal dashboard"
    agent_enabled: false
""",
        encoding="utf-8",
    )

    # env var for the loader
    monkeypatch.setenv("PRECURSOR_PROJECTS_FILE", str(projects_yaml))

    # ------------------------------------------
    # 2) patch scratchpad store data dir
    # ------------------------------------------
    import precursor.scratchpad.store as store

    def _fake_get_data_dir() -> Path:
        return data_dir

    monkeypatch.setattr(store, "_get_data_dir", _fake_get_data_dir)

    # ------------------------------------------
    # 3) patch scratchpad.render to return predictable content
    # ------------------------------------------
    import precursor.scratchpad.render as render_mod

    def fake_render_project_scratchpad(project_name: str) -> str:
        # we'll be able to see whether Gamma shows up
        return f"# {project_name}\nFake scratchpad for {project_name}.\n"

    monkeypatch.setattr(render_mod, "render_project_scratchpad", fake_render_project_scratchpad)

    # ------------------------------------------
    # 4) install fake dspy
    # ------------------------------------------
    calls: Dict[str, Any] = {}

    fake_dspy = types.SimpleNamespace()

    class FakeSignature:
        def __init__(self, *args, **kwargs):
            pass

    class FakeModule:
        def __init__(self, *args, **kwargs):
            pass

    class FakeImage:
        pass

    def fake_input_field(**kwargs):
        return None

    def fake_output_field(**kwargs):
        return None

    class FakeChainOfThought:
        def __init__(self, sig):
            self.sig = sig

        def __call__(self, **kwargs):
            # THIS is what we expect to run
            print("[FAKE DSPY] ChainOfThought called with keys:", list(kwargs.keys()))
            # print the scratchpads too, to debug filtering
            sp = kwargs.get("project_scratchpads", "")
            print("[FAKE DSPY] project_scratchpads blob:\n", sp)
            calls["kwargs"] = kwargs
            # pretend classifier chose Alpha
            return types.SimpleNamespace(project="Project Alpha")

    fake_dspy.Signature = FakeSignature
    fake_dspy.Module = FakeModule
    fake_dspy.Image = FakeImage
    fake_dspy.InputField = fake_input_field
    fake_dspy.OutputField = fake_output_field
    fake_dspy.ChainOfThought = FakeChainOfThought

    # install into sys.modules BEFORE importing module under test
    monkeypatch.setitem(os.sys.modules, "dspy", fake_dspy)

    # ------------------------------------------
    # 5) now import/reload the module under test
    # ------------------------------------------
    import precursor.components.current_project_classifier as cpc
    cpc = importlib.reload(cpc)

    yield {
        "config_dir": config_dir,
        "projects_yaml": projects_yaml,
        "data_dir": data_dir,
        "calls": calls,
        "module": cpc,
    }


def test_classifier_returns_prediction(classifier_test_env):
    cpc = classifier_test_env["module"]

    clf = cpc.CurrentProjectClassifier(include_scratchpads=True)
    res = clf.forward(
        recent_objectives="work on alpha engine",
        recent_propositions="alpha.md was edited",
        calendar_events="Alpha standup",
        screenshot=None,
        recent_project_predictions=["Project Alpha"],
    )

    assert res.project == "Project Alpha"


def test_classifier_passes_all_expected_fields(classifier_test_env):
    cpc = classifier_test_env["module"]
    calls: Dict[str, Any] = classifier_test_env["calls"]

    clf = cpc.CurrentProjectClassifier(include_scratchpads=True)
    clf.forward(
        recent_objectives="extend Alpha reasoning",
        recent_propositions="tuning Alpha model",
        calendar_events="Alpha sync tomorrow",
        screenshot=None,
        recent_project_predictions=[],
    )

    # if this KeyErrors again, we know FAKE DSPY didn't run
    assert "kwargs" in calls, "fake dspy ChainOfThought was never called"
    kwargs = calls["kwargs"]

    expected = {
        "recent_objectives",
        "recent_propositions",
        "calendar_events",
        "screenshot",
        "recent_project_predictions",
        "true_projects",
        "project_scratchpads",
    }
    assert expected.issubset(kwargs.keys())

    blob = kwargs["project_scratchpads"]
    # These must be there — real helper should include ALL projects, even disabled
    assert "--- Scratchpad for Project Alpha ---" in blob
    assert "--- Scratchpad for Project Beta ---" in blob
    assert "--- Scratchpad for Project Gamma ---" in blob  # <-- the important one


def test_classifier_builds_true_projects_including_disabled(classifier_test_env):
    cpc = classifier_test_env["module"]
    calls: Dict[str, Any] = classifier_test_env["calls"]

    clf = cpc.CurrentProjectClassifier(include_scratchpads=False)
    clf.forward(
        recent_objectives="testing",
        recent_propositions="mocking",
        calendar_events="none",
        screenshot=None,
        recent_project_predictions=[],
    )

    assert "kwargs" in calls, "fake dspy ChainOfThought was never called"
    kwargs = calls["kwargs"]
    true_projects = kwargs["true_projects"]

    assert any("Project Alpha" in s for s in true_projects)
    assert any("Project Beta" in s for s in true_projects)
    # the disabled one should still be present
    assert any("Project Gamma" in s for s in true_projects)


def test_classifier_works_without_scratchpads(classifier_test_env):
    cpc = classifier_test_env["module"]
    calls: Dict[str, Any] = classifier_test_env["calls"]

    clf = cpc.CurrentProjectClassifier(include_scratchpads=False)
    clf.forward(
        recent_objectives="whatever",
        recent_propositions="",
        calendar_events="",
        screenshot=None,
        recent_project_predictions=[],
    )

    assert "kwargs" in calls, "fake dspy ChainOfThought was never called"
    kwargs = calls["kwargs"]
    assert "project_scratchpads" in kwargs
    assert kwargs["project_scratchpads"] == ""