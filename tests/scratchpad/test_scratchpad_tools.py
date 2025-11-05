# tests/scratchpad/test_scratchpad_tools.py
from __future__ import annotations


def test_append_splits_numbered_list_and_renders(scratchpad_test_env):
    from precursor.scratchpad.scratchpad_tools import (
        append_to_scratchpad,
        get_refreshed_scratchpad,
    )

    project = "Test Project Alpha"

    append_to_scratchpad(
        project_name=project,
        section="Notes",
        proposal_text="1. First note\n2. Second note",
        confidence=3,
    )

    rendered = get_refreshed_scratchpad(project)
    assert "[0] First note (confidence: 3)" in rendered
    assert "[1] Second note (confidence: 3)" in rendered


def test_edit_replaces_and_appends_extras(scratchpad_test_env):
    from precursor.scratchpad.scratchpad_tools import (
        append_to_scratchpad,
        edit_in_scratchpad,
        get_refreshed_scratchpad,
    )

    project = "Test Project Alpha"

    append_to_scratchpad(
        project_name=project,
        section="Suggestions",
        proposal_text="Try batching writes",
        confidence=4,
    )

    edit_in_scratchpad(
        project_name=project,
        section="Suggestions",
        index=0,
        new_proposition_text="Use connection pool\nAdd metrics",
        new_confidence=6,
    )

    rendered = get_refreshed_scratchpad(project)
    # first replaced
    assert "[0] Use connection pool (confidence: 6)" in rendered
    # extra appended
    assert "[1] Add metrics (confidence: 6)" in rendered


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


def test_append_bullet_list_ignores_blanks(scratchpad_test_env):
    from precursor.scratchpad.scratchpad_tools import (
        append_to_scratchpad,
        get_refreshed_scratchpad,
    )

    project = "Test Project Alpha"

    append_to_scratchpad(
        project_name=project,
        section="Notes",
        proposal_text="- item one\n\n- item two",
        confidence=5,
    )

    rendered = get_refreshed_scratchpad(project)
    assert "[0] item one (confidence: 5)" in rendered
    assert "[1] item two (confidence: 5)" in rendered