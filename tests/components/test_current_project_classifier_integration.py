# tests/components/test_current_project_classifier_integration.py
from __future__ import annotations

from pathlib import Path
import importlib

import pytest


@pytest.fixture
def classifier_integration_env(tmp_path, monkeypatch):
    """
    Real-ish integration fixture:

    - writes a temp projects.yaml with Alpha (enabled), Beta (enabled), Gamma (disabled)
    - points PRECURSOR_PROJECTS_FILE at it
    - wires scratchpad DB to tmp
    - seeds a scratchpad entry for Alpha so we know at least one project renders
    """
    # config
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    projects_yaml = config_dir / "projects.yaml"
    projects_yaml.write_text(
        """projects:
  - name: "Project Alpha"
    description: "LLM reasoning engine"
    agent_enabled: true
  - name: "Project Beta"
    description: "ETL / data pipeline"
    agent_enabled: true
  - name: "Project Gamma"
    description: "Internal dashboard (disabled but should still show in classifier context)"
    agent_enabled: false
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("PRECURSOR_PROJECTS_FILE", str(projects_yaml))

    # scratchpad DB -> tmp
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    import precursor.scratchpad.store as store

    def _fake_get_data_dir() -> Path:
        return data_dir

    monkeypatch.setattr(store, "_get_data_dir", _fake_get_data_dir)

    # seed one real entry so render has something
    store.init_db()
    store.add_entry("Project Alpha", "Notes", "alpha note", confidence=5)

    # import real module AFTER env is set
    import precursor.components.current_project_classifier as cpc
    cpc = importlib.reload(cpc)

    return {
        "module": cpc,
        "projects_yaml": projects_yaml,
        "data_dir": data_dir,
    }


def test_real_scratchpad_helper_is_used_and_includes_disabled(classifier_integration_env, monkeypatch):
    """
    Call the *real* render_all_scratchpads_for_projects and check that:

    - Alpha scratchpad shows up (we seeded it)
    - The blob includes a section header for Project Gamma even though agent_enabled: false
      (this is the behavior we want to enforce).
    """
    cpc = classifier_integration_env["module"]

    # light fake dspy to capture the kwargs the component sends to the model
    calls = {}

    import types
    import dspy

    class FakeChain:
        def __init__(self, sig):
            self.sig = sig

        def __call__(self, **kwargs):
            # capture everything
            calls["kwargs"] = kwargs
            # return something shaped like a dspy response
            return types.SimpleNamespace(project="Project Alpha")

    monkeypatch.setattr(dspy, "ChainOfThought", FakeChain)

    clf = cpc.CurrentProjectClassifier(include_scratchpads=True, max_scratchpad_chars=2000)
    clf.forward(
        recent_objectives="check alpha",
        recent_propositions="",
        calendar_events="",
        screenshot=None,
        recent_project_predictions=[],
    )

    assert "kwargs" in calls, "classifier never called the model"
    blob = calls["kwargs"]["project_scratchpads"]

    # sanity: we got a real blob
    assert blob.strip() != ""

    # alpha must be there (we added a note)
    assert "--- Scratchpad for Project Alpha ---" in blob
    assert "alpha note" in blob

    # THIS is the important part: even though Gamma had agent_enabled: false,
    # we still want to see it in the rendered context. If the real helper
    # filters it out, this assertion will fail and tell us to go fix the helper.
    assert "--- Scratchpad for Project Gamma ---" in blob, (
        "Disabled projects should still be included in classifier context; "
        "render_all_scratchpads_for_projects is probably filtering them out."
    )