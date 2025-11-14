from __future__ import annotations

import asyncio
import types
import importlib
import sys


def _install_fake_fastmcp(monkeypatch):
    # Provide a fake FastMCP used by server
    fastmcp_mod = types.ModuleType("mcp.server.fastmcp")

    class FakeFastMCP:
        def __init__(self, name, lifespan=None):
            self.name = name
            self.tools = []

        def tool(self):
            def decorator(fn):
                self.tools.append(fn)
                return fn
            return decorator

        def run(self):  # pragma: no cover
            pass

        def get_context(self):  # pragma: no cover
            return None

    fastmcp_mod.FastMCP = FakeFastMCP
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fastmcp_mod)


def test_run_code_task_docstring_instructions_present(monkeypatch):
    _install_fake_fastmcp(monkeypatch)
    server = importlib.import_module("precursor.mcp_servers.coder.server")
    doc = server.run_code_task.__doc__ or ""
    assert "OpenHands" in doc
    assert "scratchpad" in doc.lower()
    assert "do not resubmit" in doc.lower()


def test_run_code_task_success_flow_with_artifact(monkeypatch, tmp_path):
    _install_fake_fastmcp(monkeypatch)
    server = importlib.import_module("precursor.mcp_servers.coder.server")

    # Fake dspy: LM, configure, context, ChainOfThought (summarizer only)
    class FakeLM:
        def __init__(self, *_args, **_kwargs): ...
    def fake_configure(lm): ...
    class FakeContext:
        def __init__(self, lm): ...
        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): return False
    class FakeSummarizer:
        def __init__(self, _sig): ...
        def __call__(self, **kwargs):
            return types.SimpleNamespace(short_summary="Fixed a bug", full_summary="Step 1... Step 2...")
    monkeypatch.setattr(server.dspy, "LM", FakeLM)
    monkeypatch.setattr(server.dspy, "configure", fake_configure)
    monkeypatch.setattr(server.dspy, "context", lambda lm: FakeContext(lm))
    monkeypatch.setattr(server.dspy, "ChainOfThought", lambda sig: FakeSummarizer(sig))

    # Replace FindRepository to short-circuit discovery
    class FakeFindRepo:
        def __call__(self, project_name, project_context, task_context):
            return "/tmp/autometrics-site"
    monkeypatch.setattr(server, "FindRepository", lambda: FakeFindRepo())

    # Repo full name
    monkeypatch.setattr(server, "get_repo_full_name", lambda path: "XenonMolecule/autometrics-site")

    # OpenHands task result
    traj_path = str(tmp_path / "traj.json")
    (tmp_path / "traj.json").write_text('{"ok": true}', encoding="utf-8")
    async def fake_run_openhands_task_with_pr_async(project_name, repo, task, github_token=None):
        return {
            "sid": "123",
            "final_state": "FINISHED",
            "pr_url": "https://github.com/XenonMolecule/autometrics-site/pull/42",
            "pr_create_url": "https://github.com/XenonMolecule/autometrics-site/pull/new/branch",
            "trajectory_path": traj_path,
        }
    monkeypatch.setattr(server, "run_openhands_task_with_pr_async", fake_run_openhands_task_with_pr_async)

    recorded = {}
    def fake_store_artifact(project_name, task, short_description, uri, step_by_step_summary=None):
        recorded.update(
            project_name=project_name,
            task=task,
            short_description=short_description,
            uri=uri,
            step_by_step_summary=step_by_step_summary,
        )
    monkeypatch.setattr(server, "store_artifact", fake_store_artifact)

    async def run():
        out = await server.run_code_task(
            project_name="AutoMetrics Release",
            task="Fix bug in metric aggregation",
        )
        # store_artifact called exactly once with expected fields
        assert recorded.get("project_name") == "AutoMetrics Release"
        assert recorded.get("task") == "Fix bug in metric aggregation"
        assert recorded.get("short_description") == "Fixed a bug"
        assert recorded.get("uri") == "https://github.com/XenonMolecule/autometrics-site/pull/42"
        assert "Step 1" in (recorded.get("step_by_step_summary") or "")

        # Output string should include PR URL, short summary, and "Do NOT resubmit"
        assert "Fixed a bug" in out
        assert "pull/42" in out
        assert "do not resubmit" in out.lower()

    asyncio.run(run())


def test_run_code_task_error_flow(monkeypatch):
    _install_fake_fastmcp(monkeypatch)
    server = importlib.import_module("precursor.mcp_servers.coder.server")

    # Minimal dspy stubs
    class FakeLM:
        def __init__(self, *_args, **_kwargs): ...
    class FakeContext:
        def __init__(self, lm): ...
        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): return False
    monkeypatch.setattr(server.dspy, "LM", FakeLM)
    monkeypatch.setattr(server.dspy, "configure", lambda lm: None)
    monkeypatch.setattr(server.dspy, "context", lambda lm: FakeContext(lm))
    # Summarizer returns defaults
    class FakeSummarizer:
        def __init__(self, _sig): ...
        def __call__(self, **kwargs):
            return types.SimpleNamespace(short_summary="Attempt failed", full_summary="Error occurred")
    monkeypatch.setattr(server.dspy, "ChainOfThought", lambda sig: FakeSummarizer(sig))

    # Repo finder shortcut
    class FakeFindRepo:
        def __call__(self, project_name, project_context, task_context):
            return "/tmp/fake-repo"
    monkeypatch.setattr(server, "FindRepository", lambda: FakeFindRepo())
    monkeypatch.setattr(server, "get_repo_full_name", lambda path: "User/fake-repo")

    async def fake_run_openhands_task_with_pr_async(*args, **kwargs):
        return {"final_state": "ERROR", "trajectory_path": ""}
    monkeypatch.setattr(server, "run_openhands_task_with_pr_async", fake_run_openhands_task_with_pr_async)

    # Allow store_artifact; we won't assert it's skipped because implementation
    # attempts to record regardless of final_state.
    monkeypatch.setattr(server, "store_artifact", lambda *a, **k: None)

    async def run():
        out = await server.run_code_task(
            project_name="Proj",
            task="Some task",
        )
        assert "ERROR" in out
        assert "User/fake-repo" in out

    asyncio.run(run())


