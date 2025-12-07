from __future__ import annotations

from typing import Any, List, Optional
from PIL import Image as PILImage
import logging
import dspy

logger = logging.getLogger(__name__)


def goals_to_text(goals: List[Any]) -> str:
    lines: List[str] = []
    for g in goals:
        name = getattr(g, "name", "Goal")
        desc = getattr(g, "description", "")
        weight = getattr(g, "weight", None)
        if weight is not None:
            lines.append(f"- {name}: {desc} (weight: {weight})")
        else:
            lines.append(f"- {name}: {desc}")
    return "\n".join(lines)


def goals_to_objective_strings(goals: List[Any]) -> List[str]:
    results: List[str] = []
    for g in goals:
        name = getattr(g, "name", "Goal")
        desc = getattr(g, "description", "")
        weight = getattr(g, "weight", None)
        pieces = [name]
        if desc:
            pieces.append(desc)
        if weight is not None:
            pieces.append(f"weight={weight}")
        results.append(" | ".join(pieces))
    return results


def ensure_screenshot_image(img: Optional[dspy.Image]) -> dspy.Image:
    """
    Ensure a valid dspy.Image is available.
    If no screenshot is provided, emit a major warning and create a minimal fallback.

    NOTE:
    The fallback is a **1x1 white pixel**, which is highly out-of-distribution
    for any LLM using visual input. This should only happen in testing or
    degenerate simulator modes — never in production.
    """
    if img is not None:
        return img

    logger.warning(
        "[ensure_screenshot_image] Missing screenshot for context event. "
        "Generating 1x1 white pixel fallback — this is highly out-of-distribution "
        "for any LLM using visual inputs. Upstream observer likely failed to capture "
        "a real screenshot."
    )

    tiny = PILImage.new("RGB", (1, 1), color=(255, 255, 255))
    return dspy.Image.from_PIL(tiny)