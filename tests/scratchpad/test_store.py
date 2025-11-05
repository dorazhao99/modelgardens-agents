# tests/scratchpad/test_store.py
from __future__ import annotations


def test_add_and_list_entries_basic(scratchpad_test_env):
    import precursor.scratchpad.store as store

    project = "Test Project Alpha"
    store.init_db()

    store.add_entry(project, "Notes", "first note", confidence=3)
    store.add_entry(project, "Notes", "second note", confidence=5)

    rows = store.list_entries(project, section="Notes")
    assert len(rows) == 2
    assert rows[0]["message"] == "first note"
    assert rows[1]["message"] == "second note"


def test_display_index_mapping_matches_order(scratchpad_test_env):
    import precursor.scratchpad.store as store

    project = "Test Project Alpha"
    store.init_db()

    store.add_entry(project, "Suggestions", "sug 1", confidence=2)
    store.add_entry(project, "Suggestions", "sug 2", confidence=4)
    store.add_entry(project, "Suggestions", "sug 3", confidence=6)

    row = store.get_entry_by_display_index(project, "Suggestions", display_index=1)
    assert row is not None
    assert row["message"] == "sug 2"


def test_soft_delete_hides_from_listing(scratchpad_test_env):
    import precursor.scratchpad.store as store

    project = "Test Project Alpha"
    store.init_db()

    e1 = store.add_entry(project, "Notes", "to be deleted", confidence=1)
    store.add_entry(project, "Notes", "should remain", confidence=1)

    store.delete_entry(e1)

    rows = store.list_entries(project, section="Notes")
    messages = [r["message"] for r in rows]
    assert "to be deleted" not in messages
    assert "should remain" in messages


def test_resource_order_stable_per_subsection(scratchpad_test_env):
    import precursor.scratchpad.store as store

    project = "Test Project Alpha"
    store.init_db()

    store.add_entry(project, "Project Resources", "file_a.py", confidence=2, subsection="Files")
    store.add_entry(project, "Project Resources", "file_b.py", confidence=2, subsection="Files")
    store.add_entry(project, "Project Resources", "file_c.py", confidence=2, subsection="Files")

    rows = store.list_entries(project, section="Project Resources")
    files = [r for r in rows if (r.get("subsection") or "Other") == "Files"]
    messages = [r["message"] for r in files]
    assert messages == ["file_a.py", "file_b.py", "file_c.py"]