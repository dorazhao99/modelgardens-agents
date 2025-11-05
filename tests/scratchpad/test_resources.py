# tests/scratchpad/test_resources.py
from __future__ import annotations


def test_resource_label_normalizes_to_project_resources(scratchpad_test_env):
    from precursor.scratchpad.scratchpad_tools import append_to_scratchpad
    from precursor.scratchpad.scratchpad_tools import get_refreshed_scratchpad

    project = "Test Project Alpha"

    append_to_scratchpad(
        project_name=project,
        section="files",  # intentionally lower / non-canonical
        proposal_text="data/raw/users.csv",
        confidence=4,
    )

    rendered = get_refreshed_scratchpad(project)
    assert "## Project Resources" in rendered
    assert "### Files" in rendered
    assert "users.csv" in rendered


def test_edit_resource_by_subsection_and_index(scratchpad_test_env):
    from precursor.scratchpad.scratchpad_tools import (
        append_to_scratchpad,
        edit_in_scratchpad,
        get_refreshed_scratchpad,
    )

    project = "Test Project Alpha"

    append_to_scratchpad(
        project_name=project,
        section="Project Resources",
        proposal_text="repo-one (uri: git@example.com/repo-one.git)",
        confidence=5,
        subsection="Repos",
    )
    append_to_scratchpad(
        project_name=project,
        section="Project Resources",
        proposal_text="repo-two (uri: git@example.com/repo-two.git)",
        confidence=5,
        subsection="Repos",
    )

    # edit the second repo
    edit_in_scratchpad(
        project_name=project,
        section="Project Resources",
        index=1,
        new_proposition_text="repo-two (archived)",
        new_confidence=7,
        subsection="Repos",
    )

    rendered = get_refreshed_scratchpad(project)
    assert "repo-two (archived) (confidence: 7)" in rendered
    # keep the first one intact
    assert "repo-one (uri: git@example.com/repo-one.git) (confidence: 5)" in rendered