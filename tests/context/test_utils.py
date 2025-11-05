# tests/context/test_utils.py
from __future__ import annotations

import types
from datetime import datetime
from typing import Any

import pytest


@pytest.fixture
def fake_screen_env(monkeypatch):
    """
    Provide a fake mss + fake mouse so grab_screen_at_mouse doesn't need
    a real display. We return a 10x10 black image worth of bytes.
    """
    import precursor.context.utils as utils

    # --- fake mouse ---
    class FakeMouse:
        @property
        def position(self):
            # somewhere inside our fake monitor
            return (50, 50)

    monkeypatch.setattr(utils, "MouseController", lambda: FakeMouse())

    # --- fake mss ---
    class FakeFrame:
        width = 10
        height = 10
        # 10*10*3 = 300 bytes
        rgb = b"\x00" * 300

    class FakeMSS:
        def __enter__(self):
            # monitors[0] = virtual; monitors[1:] = physical
            self.monitors = [
                {"left": 0, "top": 0, "width": 200, "height": 200},  # virtual
                {"left": 0, "top": 0, "width": 200, "height": 200},  # monitor 1
            ]
            return self

        def __exit__(self, *exc):
            return False

        def grab(self, mon: dict):
            # ignore mon, always return a 10x10 black frame
            return FakeFrame()

    monkeypatch.setattr(utils.mss, "mss", lambda: FakeMSS())

    return utils


def test_point_in_rect_basic():
    import precursor.context.utils as utils

    rect = {"left": 0, "top": 0, "width": 100, "height": 50}
    assert utils._point_in_rect(0, 0, rect)
    assert utils._point_in_rect(99, 49, rect)
    assert not utils._point_in_rect(100, 10, rect)
    assert not utils._point_in_rect(10, 50, rect)


def test_monitor_for_mouse_picks_correct():
    import precursor.context.utils as utils

    monitors = [
        {"left": 0, "top": 0, "width": 200, "height": 200},
        {"left": 200, "top": 0, "width": 200, "height": 200},
    ]
    # point in first
    m1 = utils._monitor_for_mouse(monitors, 50, 50)
    assert m1["left"] == 0

    # point in second
    m2 = utils._monitor_for_mouse(monitors, 210, 20)
    assert m2["left"] == 200

    # point outside all → fall back to first
    m3 = utils._monitor_for_mouse(monitors, 9999, 9999)
    assert m3["left"] == 0


def test_grab_screen_at_mouse_returns_pil(fake_screen_env):
    # we patched everything in fake_screen_env
    img = fake_screen_env.grab_screen_at_mouse()
    # should be a 10x10 PIL image
    assert img.size == (10, 10)
    assert img.mode == "RGB"


def test_grab_screen_dspy_image_wraps_pil(fake_screen_env, monkeypatch):
    # patch dspy.Image so we know it's called with a PIL
    called = {}

    class FakeDspyImage:
        @classmethod
        def from_PIL(cls, pil):
            called["pil"] = pil
            return cls()

    monkeypatch.setattr(fake_screen_env, "dspy", types.SimpleNamespace(Image=FakeDspyImage))

    out = fake_screen_env.grab_screen_dspy_image()
    assert isinstance(out, FakeDspyImage)
    assert "pil" in called
    assert called["pil"].size == (10, 10)


@pytest.mark.asyncio
async def test_build_user_activity_context_includes_everything(monkeypatch):
    import precursor.context.utils as utils

    # --- fake loader bits you added ---
    monkeypatch.setattr(utils, "get_user_name", lambda: "Loader User")
    monkeypatch.setattr(utils, "get_user_profile", lambda: "Name: Loader User\nDescription: Loader description")

    # --- fake gum client ---
    class FakeGum:
        user_name = "Gum User"

        async def recent(self):
            # match the shape you format in _format_user_details
            return [
                {
                    "text": "recent observation 1",
                    "confidence": 7,
                    "created_at": datetime(2025, 1, 1, 12, 0, 0),
                    "reasoning": "because...",
                }
            ]

    # --- fake calendar client ---
    class FakeCalendar:
        def query_str(self, start_delta, end_delta):
            return "standup with alpha team"

    ctx = await utils.build_user_activity_context(
        gum_client=FakeGum(),
        calendar_client=FakeCalendar(),
        current_context="User opened background-agents repo",
        calendar_horizon_days=1,
    )

    # should contain gum user OR loader user (we took gum.user_name first)
    assert "Gum User" in ctx
    # should contain the ground-truth user description
    assert "Ground Truth User Description: Name: Loader User" in ctx
    # should contain formatted user details
    assert "recent observation 1" in ctx
    # should contain calendar
    assert "standup with alpha team" in ctx
    # should contain the current context
    assert "User opened background-agents repo" in ctx