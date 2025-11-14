from __future__ import annotations

import asyncio
import types
import importlib
import os


class FakeGum:
    def __init__(self, user_name, _model):
        self.user_name = user_name
        self.connected = False
        self.closed = False
        self._query_calls = []

    async def connect_db(self):
        self.connected = True

    async def close_db(self):
        self.closed = True

    async def query(self, query, start_time=None, end_time=None, limit=3):
        self._query_calls.append((query, start_time, end_time, limit))
        # default empty; individual tests can monkeypatch
        return []

    # Simple async context manager to mimic _session() used by server code
    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def _session(self):
        return self._Session()


def test_gum_lifespan_connects_db_with_user_name(monkeypatch):
    server = importlib.import_module("precursor.mcp_servers.gum.server")

    # Patch the imported symbol 'gum' (class) directly to our FakeGum
    monkeypatch.setattr(server, "gum", FakeGum)

    # Ensure USER_NAME is set
    monkeypatch.setenv("USER_NAME", "Unit Test User")

    async def run():
        # Use the lifespan context manager directly
        async with server.app_lifespan(server.mcp) as ctx:
            gum_instance = ctx.gum_instance
            assert isinstance(gum_instance, FakeGum)
            assert gum_instance.user_name == "Unit Test User"
            assert gum_instance.connected is True
        # After context, close_db may have been attempted; ignore failures

    asyncio.run(run())


def test_get_user_context_formats_results(monkeypatch):
    server = importlib.import_module("precursor.mcp_servers.gum.server")

    fake = FakeGum("Unit Test User", None)

    class Prop:
        def __init__(self):
            self.text = "Refactor the controller to remove duplication"
            self.reasoning = "Improves maintainability"
            self.confidence = 0.85
            self.id = 42

    async def fake_query(q, start_time=None, end_time=None, limit=3):
        return [(Prop(), 0.92)]

    fake.query = fake_query

    # Monkeypatch mcp.get_context() to supply our gum instance
    class DummyCtx:
        request_context = types.SimpleNamespace(
            lifespan_context=types.SimpleNamespace(gum_instance=fake)
        )

    monkeypatch.setattr(server.mcp, "get_context", lambda: DummyCtx())

    # Mock related observations
    class Obs:
        def __init__(self):
            self.observer_name = "Screen"
            self.content = "Edited controller.py"

    async def fake_get_related_observations(session, proposition_id, limit=1):
        return [Obs()]

    monkeypatch.setattr(server, "get_related_observations", fake_get_related_observations)

    async def run():
        out = await server.get_user_context(
            query="refactor", start_hh_mm_ago="01:00", end_hh_mm_ago="00:10"
        )
        # Bullet line with text, plus fields
        assert "• Refactor the controller to remove duplication" in out
        assert "Reasoning:" in out
        assert "Confidence:" in out
        assert "Relevance Score:" in out
        assert "Supporting Observations:" in out
        assert "[Screen] Edited controller.py" in out

    asyncio.run(run())


