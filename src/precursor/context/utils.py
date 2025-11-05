# src/precursor/context/utils.py
"""
Context-building helpers for components that need:
- a screenshot of the current screen
- a rich "what is the user doing" context from gum + calendar

These stay separate from the actual LM components so that the components
can stay testable and not hard-import mss/pynput/PIL on import.
"""

from __future__ import annotations

from typing import Optional, Tuple, Any

from datetime import datetime, timedelta

import mss
from PIL import Image
from pynput.mouse import Controller as MouseController

import dspy  # only to wrap screenshot into dspy.Image

from precursor.config.loader import get_user_profile
from precursor.config.loader import get_user_name

# ---------------------------------------------------------------------------
# screenshot helpers
# ---------------------------------------------------------------------------

def _point_in_rect(x: int, y: int, rect: dict) -> bool:
    return (
        rect["left"] <= x < rect["left"] + rect["width"]
        and rect["top"] <= y < rect["top"] + rect["height"]
    )


def _monitor_for_mouse(monitors: list[dict], x: int, y: int) -> dict:
    """
    Given physical monitors (mss.monitors[1:]), find the one that contains the point.
    """
    for m in monitors:
        if _point_in_rect(x, y, m):
            return m
    # fallback to the first real monitor
    return monitors[0]


def grab_screen_at_mouse(region: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
    """
    Capture the screen of the monitor currently under the mouse cursor.

    Returns a PIL.Image.Image (RGB).
    """
    mouse = MouseController()
    x, y = mouse.position

    with mss.mss() as sct:
        physical = sct.monitors[1:]
        mon = _monitor_for_mouse(physical, int(x), int(y))

        if region is not None:
            rx, ry, rw, rh = region
            mon = {
                "left": mon["left"] + rx,
                "top": mon["top"] + ry,
                "width": rw,
                "height": rh,
            }

        frame = sct.grab(mon)
        return Image.frombytes("RGB", (frame.width, frame.height), frame.rgb)


def grab_screen_dspy_image() -> dspy.Image:
    """
    Convenience: capture and wrap as dspy.Image.
    """
    pil = grab_screen_at_mouse()
    return dspy.Image.from_PIL(pil)


# ---------------------------------------------------------------------------
# gum + calendar → context string
# ---------------------------------------------------------------------------

async def build_user_activity_context(
    *,
    gum_client: Any,
    calendar_client: Any,
    current_context: str,
    calendar_horizon_days: int = 1,
) -> str:
    """
    Build the long string we feed to the LM:
    - user name
    - recent user details (gum)
    - calendar events (next N days)
    - current context update (what the caller passed in)
    """
    user_name = getattr(gum_client, "user_name", get_user_name())
    user_description = get_user_profile()

    # gum.recent() — may return a structured list
    try:
        user_details = await gum_client.recent()
    except Exception:
        user_details = []

    # calendar — we match your original usage
    try:
        calendar_events = calendar_client.query_str(
            start_delta=timedelta(days=0),
            end_delta=timedelta(days=calendar_horizon_days),
        )
    except Exception:
        calendar_events = ""

    def _format_user_details(items: Any) -> str:
        lines: list[str] = []
        if not items:
            return ""
        if not isinstance(items, list):
            items = [items]
        for it in items:
            text = ""
            created_at = ""
            confidence = ""
            reasoning = ""
            if isinstance(it, dict):
                text = it.get("text") or str(it)
                created_at = it.get("created_at") or ""
                confidence = it.get("confidence") or ""
                reasoning = it.get("reasoning") or ""
            else:
                text = getattr(it, "text", str(it))
                created_at = getattr(it, "created_at", "")
                confidence = getattr(it, "confidence", "")
                reasoning = getattr(it, "reasoning", "")
            if isinstance(created_at, datetime):
                created_at = created_at.isoformat()
            lines.append(f"- {text}")
            meta_bits = []
            if confidence != "":
                meta_bits.append(f"confidence: {confidence}")
            if created_at:
                meta_bits.append(f"created_at: {created_at}")
            if meta_bits:
                lines.append("  - " + " | ".join(meta_bits))
            if reasoning:
                lines.append(f"  - reasoning: {reasoning}")
        return "\n".join(lines)

    user_details_str = _format_user_details(user_details)

    context_str = (
        f"User: {user_name}\n"
        f"Ground Truth User Description: {user_description}\n"
        f"User Details:\n{user_details_str}\n"
        f"Calendar Events: {calendar_events}\n"
        f"Current Context Update: {current_context}"
    )
    return context_str