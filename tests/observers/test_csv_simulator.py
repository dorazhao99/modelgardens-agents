# tests/observers/test_csv_simulator.py
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import dspy
from PIL import Image as PILImage

from precursor.observers.csv_simulator import (
    CSVSimulatorObserver,
    CSVSimulatorConfig,
)
from precursor.context.events import ContextEvent


def _write_csv(tmp_path: Path, rows: list[dict]) -> Path:
    csv_path = tmp_path / "context_log.csv"
    fieldnames = [
        "timestamp",
        "screenshot_path",
        "user_name",
        "user_details",
        "calendar_events",
        "recent_observations",
        "context_update",
        "goals",
        "reasoning",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    return csv_path


def test_row_to_event_minimal(tmp_path):
    # make a simple csv row: no screenshot, json user_details
    row = {
        "timestamp": "20251020_144855",
        "screenshot_path": "",
        "user_name": "Sim User",
        "user_details": json.dumps([{"text": "working on docs", "confidence": 8}]),
        "calendar_events": "Standup at 10",
        "recent_observations": "[]",
        "context_update": "Editing a Google Doc",
        "goals": "[]",
        "reasoning": "",
    }
    csv_path = _write_csv(tmp_path, [row])

    cfg = CSVSimulatorConfig(csv_path=str(csv_path), mode="asap")
    sim = CSVSimulatorObserver(config=cfg)

    # call the internal converter directly
    event: ContextEvent = sim._row_to_event(row)

    assert isinstance(event, ContextEvent)
    assert event.context_update == "Editing a Google Doc"
    assert event.user_name == "Sim User"
    assert event.calendar_events == "Standup at 10"
    # we said: user_details == recent_propositions (single source of truth)
    assert event.recent_propositions[0]["text"] == "working on docs"
    assert event.recent_propositions[0]["confidence"] == 8
    # timestamp parsed
    assert event.timestamp.tzinfo is timezone.utc
    assert event.timestamp.year == 2025


def test_row_to_event_loads_screenshot(tmp_path):
    # create a tiny image to point to
    img_path = tmp_path / "shot.png"
    img = PILImage.new("RGB", (3, 3), color=(255, 0, 0))
    img.save(img_path)

    row = {
        "timestamp": "20251020_144855",
        "screenshot_path": str(img_path),
        "user_name": "Sim User",
        "user_details": json.dumps([{"text": "planning event"}]),
        "calendar_events": "",
        "recent_observations": "[]",
        "context_update": "Looking at spreadsheet",
        "goals": "[]",
        "reasoning": "",
    }
    csv_path = _write_csv(tmp_path, [row])

    cfg = CSVSimulatorConfig(csv_path=str(csv_path), mode="asap")
    sim = CSVSimulatorObserver(config=cfg)

    event = sim._row_to_event(row)

    assert event.screenshot is not None
    assert isinstance(event.screenshot, dspy.Image)


def test_run_calls_handler_in_order(tmp_path):
    # two rows — we’ll just make sure handler gets two calls in the same order
    rows = [
        {
            "timestamp": "20251020_144855",
            "screenshot_path": "",
            "user_name": "User A",
            "user_details": json.dumps([{"text": "first"}]),
            "calendar_events": "",
            "recent_observations": "[]",
            "context_update": "first update",
            "goals": "[]",
            "reasoning": "",
        },
        {
            "timestamp": "20251020_145155",
            "screenshot_path": "",
            "user_name": "User A",
            "user_details": json.dumps([{"text": "second"}]),
            "calendar_events": "",
            "recent_observations": "[]",
            "context_update": "second update",
            "goals": "[]",
            "reasoning": "",
        },
    ]
    csv_path = _write_csv(tmp_path, rows)

    cfg = CSVSimulatorConfig(csv_path=str(csv_path), mode="asap")
    sim = CSVSimulatorObserver(config=cfg)

    seen: list[ContextEvent] = []

    async def _run():
        await sim.run(lambda ev: seen.append(ev))

    # run the async bit
    import asyncio

    asyncio.run(_run())

    assert len(seen) == 2
    assert seen[0].context_update == "first update"
    assert seen[1].context_update == "second update"