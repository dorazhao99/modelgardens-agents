# tests/components/conftest.py
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest


@pytest.fixture
def classifier_test_env(tmp_path, monkeypatch):
    """
    Per-test sandbox for current_project_classifier.

    We do:
    1. make a temp projects.yaml that uses **agent_enabled**
    2. point PRECURSOR_PROJECTS_FILE at it
    3. patch scratchpad store data dir
    4. patch precursor.projects.utils to return our fake projects
    5. patch precursor.scratchpad.utils.render_all_scratchpads_for_projects
    6. install a fake dspy with Signature/InputField/OutputField/Module/ChainOfThought/Image
    """

    # ------------------------------------------------------------------
    # 1) write fake projects.yaml (with agent_enabled)
    # ------------------------------------------------------------------
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

    # tell the real loader to use THIS file
    monkeypatch.setenv("PRECURSOR_PROJECTS_FILE", str(projects_yaml))

    # ------------------------------------------------------------------
    # 2) patch scratchpad store sqlite dir
    # ------------------------------------------------------------------
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    import precursor.scratchpad.store as store

    def _fake_get_data_dir() -> Path:
        return data_dir

    monkeypatch.setattr(store, "_get_data_dir", _fake_get_data_dir)

    # ------------------------------------------------------------------
    # 3) patch precursor.projects.utils so classifier sees **agent_enabled**
    # ------------------------------------------------------------------
    import precursor.projects.utils as proj_utils

    fake_projects: List[Dict[str, Any]] = [
        {
            "name": "Project Alpha",
            "description": "LLM reasoning engine",
            "agent_enabled": True,
        },
        {
            "name": "Project Beta",
            "description": "Data pipeline for embeddings",
            "agent_enabled": True,
        },
        {
            "name": "Project Gamma",
            "description": "Internal dashboard",
            "agent_enabled": False,
        },
    ]

    def fake_load_projects_normalized() -> List[Dict[str, Any]]:
        # exactly what the classifier wants: list of dicts
        return fake_projects

    def fake_projects_to_labeled_list(projects: List[Dict[str, Any]]) -> List[str]:
        # turn agent-enabled projects into "Name: desc"
        out: List[str] = []
        for p in projects:
            if not p.get("agent_enabled", True):
                continue
            name = p["name"]
            desc = p.get("description") or ""
            if desc:
                out.append(f"{name}: {desc}")
            else:
                out.append(name)
        return out

    def fake_get_project_names(only_enabled: bool = True) -> List[str]:
        names: List[str] = []
        for p in fake_projects:
            if only_enabled and not p.get("agent_enabled", True):
                continue
            names.append(p["name"])
        return names

    monkeypatch.setattr(proj_utils, "load_projects_normalized", fake_load_projects_normalized)
    monkeypatch.setattr(proj_utils, "projects_to_labeled_list", fake_projects_to_labeled_list)
    monkeypatch.setattr(proj_utils, "get_project_names", fake_get_project_names)

    # ------------------------------------------------------------------
    # 4) patch precursor.scratchpad.utils.render_all_scratchpads_for_projects
    # ------------------------------------------------------------------
    import precursor.scratchpad.utils as sp_utils

    def fake_render_all_scratchpads_for_projects(
        projects: List[Dict[str, Any]],
        *,
        max_chars_per_project: int = 1200,
    ) -> str:
        chunks: List[str] = []
        for p in projects:
            if not p.get("agent_enabled", True):
                continue
            name = p["name"]
            body = f"# {name}\nFake scratchpad for {name}.\n"
            body = body[:max_chars_per_project]
            chunks.append(f"--- Scratchpad for {name} ---\n{body}")
        return "\n\n".join(chunks)

    monkeypatch.setattr(sp_utils, "render_all_scratchpads_for_projects", fake_render_all_scratchpads_for_projects)

    # ------------------------------------------------------------------
    # 5) install fake dspy BEFORE importing the classifier in tests
    # ------------------------------------------------------------------
    calls: Dict[str, Any] = {}

    class FakeSignature:
        """Bare-minimum stand-in so `class X(dspy.Signature)` works."""
        pass

    def _return_arg_kind(kind: str):
        def _make_field(**kwargs):
            return (kind, kwargs)
        return _make_field

    InputField = _return_arg_kind("input")
    OutputField = _return_arg_kind("output")

    class FakeImage:
        """We just need a type-like object here."""
        pass

    class FakeModule:
        def __init__(self, *args, **kwargs):
            # real dspy.Module does bookkeeping, we don't need it
            pass

    class FakeChainOfThought:
        def __init__(self, sig):
            self.sig = sig

        def __call__(self, **kwargs):
            # capture what the classifier sends us
            calls["kwargs"] = kwargs
            # return something with `.project`
            return SimpleNamespace(project="Project Alpha")

    fake_dspy = SimpleNamespace(
        Signature=FakeSignature,
        InputField=InputField,
        OutputField=OutputField,
        Image=FakeImage,
        Module=FakeModule,
        ChainOfThought=FakeChainOfThought,
    )

    monkeypatch.setitem(sys.modules, "dspy", fake_dspy)

    # hand back the things tests might want to inspect
    yield {
        "config_dir": config_dir,
        "projects_yaml": projects_yaml,
        "data_dir": data_dir,
        "calls": calls,
        "fake_projects": fake_projects,
    }