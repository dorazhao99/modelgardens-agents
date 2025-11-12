# tests/scratchpad/test_scratchpad_tools.py
from __future__ import annotations


def test_remove_by_index_hides_entry(scratchpad_test_env):
    from precursor.scratchpad.scratchpad_tools import (
        append_to_scratchpad,
        remove_from_scratchpad,
        get_refreshed_scratchpad,
    )

    project = "Test Project Alpha"

    append_to_scratchpad(
        project_name=project,
        section="Notes",
        proposal_text="Temp note to delete",
        confidence=2,
    )

    remove_from_scratchpad(project_name=project, section="Notes", index=0)

    rendered = get_refreshed_scratchpad(project)
    assert "Temp note to delete" not in rendered


def test_edit_updates_confidence(scratchpad_test_env):
    from precursor.scratchpad.scratchpad_tools import (
        append_to_scratchpad,
        edit_in_scratchpad,
        get_refreshed_scratchpad,
    )

    project = "Test Project Alpha"

    append_to_scratchpad(
        project_name=project,
        section="Notes",
        proposal_text="rough observation",
        confidence=2,
    )

    edit_in_scratchpad(
        project_name=project,
        section="Notes",
        index=0,
        new_proposition_text="rough observation (confirmed)",
        new_confidence=8,
    )

    rendered = get_refreshed_scratchpad(project)
    assert "[0] rough observation (confirmed) (confidence: 8)" in rendered