from __future__ import annotations

import types
import importlib
import pytest


def test_toolset_builder_respects_allow_fn_and_namespaces(monkeypatch):
    builder = importlib.import_module("precursor.toolset.builder")

    # Replace dspy.Tool with a tiny fake that preserves the function reference
    class FakeTool:
        def __init__(self, fn):
            self.fn = fn
            self.name = getattr(fn, "__name__", "tool")

    monkeypatch.setattr(builder.dspy, "Tool", FakeTool)

    # Fake server clients with "tools" iterable of functions
    def drive_search_files(): ...
    def coder_run_code_task(): ...

    class DriveClient:
        def __init__(self):
            self.tools = [drive_search_files]

    class CoderClient:
        def __init__(self):
            self.tools = [coder_run_code_task]

    class LoadedServer:
        def __init__(self, id, client):
            self.id = id
            self.client = client

    class Bundle:
        def __init__(self):
            self.servers = [
                LoadedServer("drive", DriveClient()),
                LoadedServer("coder", CoderClient()),
            ]

            def allow(name: str) -> bool:
                # Only allow drive.* tools
                return name.startswith("drive.")

            self.allow_fn = allow

    out = builder.build_toolset(Bundle())
    # Only the drive tool should be present
    assert len(out) == 1
    assert out[0].name == "drive_search_files"

