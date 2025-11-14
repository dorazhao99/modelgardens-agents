from __future__ import annotations

import importlib


def test_store_artifact_idempotent_and_preserves_metadata(scratchpad_test_env):
    artifacts = importlib.import_module("precursor.core_tools.artifacts")
    store = importlib.import_module("precursor.scratchpad.store")

    project = "Test Project Alpha"
    store.init_db()

    msg1 = artifacts.store_artifact(
        project_name=project,
        task="Open PR to update docs",
        short_description="Updated README for clarity",
        uri="https://github.com/example/repo/pull/1",
        step_by_step_summary="Edited README, previewed changes, opened PR",
    )
    msg2 = artifacts.store_artifact(
        project_name=project,
        task="Open PR to update docs",
        short_description="Updated README for clarity",
        uri="https://github.com/example/repo/pull/1",
        step_by_step_summary="Edited README, previewed changes, opened PR",
    )

    # First call records, second call is idempotent (already recorded)
    assert "Recorded artifact entry" in msg1
    assert "already recorded" in msg2.lower()

    rows = store.list_entries(project, section="Agent Completed Tasks (Pending Review)")
    assert len(rows) == 1
    r = rows[0]
    assert "metadata_json" not in r
    md = r.get("metadata") or {}
    assert md.get("task") == "Open PR to update docs"
    assert md.get("uri") == "https://github.com/example/repo/pull/1"
    assert "Updated README for clarity" in (md.get("short_description") or "")
    assert "Edited README" in (md.get("step_by_step_summary") or "")


