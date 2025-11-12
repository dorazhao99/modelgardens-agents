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


def test_add_with_metadata_and_decode(scratchpad_test_env):
    import precursor.scratchpad.store as store

    project = "Test Project Alpha"
    store.init_db()

    meta = {"uri": "drive://abc", "long_summary": "Outlined results"}
    store.add_entry(project, "Notes", "Created release doc", 7, metadata=meta)

    rows = store.list_entries(project)
    assert len(rows) == 1
    r = rows[0]
    # ensure decoded metadata present
    assert r["metadata"] == meta
    # ensure raw column is not exposed
    assert "metadata_json" not in r


def test_update_entry_metadata_only(scratchpad_test_env):
    import precursor.scratchpad.store as store

    project = "Test Project Alpha"
    store.init_db()

    entry_id = store.add_entry(project, "Notes", "Keep message same", 3, metadata={"a": 1})

    # Update metadata, keep message unchanged
    store.update_entry(entry_id, new_message="Keep message same", new_metadata={"uri": "drive://abc", "reviewed": True})

    rows = store.list_entries(project, section="Notes")
    assert len(rows) == 1
    r = rows[0]
    assert r["id"] == entry_id
    assert r["message"] == "Keep message same"
    assert r["metadata"] == {"uri": "drive://abc", "reviewed": True}


def test_update_by_display_index_passes_new_metadata(scratchpad_test_env):
    import precursor.scratchpad.store as store

    project = "Test Project Alpha"
    store.init_db()

    store.add_entry(project, "Suggestions", "s1", 1, metadata={"x": 1})
    store.add_entry(project, "Suggestions", "s2", 1, metadata={"x": 2})
    store.add_entry(project, "Suggestions", "s3", 1, metadata={"x": 3})

    ok = store.update_entry_by_display_index(
        project, "Suggestions", display_index=1, new_message="s2", new_metadata={"x": 999}
    )
    assert ok

    rows = store.list_entries(project, section="Suggestions")
    # second entry should now have updated metadata
    assert rows[1]["message"] == "s2"
    assert rows[1]["metadata"] == {"x": 999}


def test_get_entry_by_display_index_returns_metadata(scratchpad_test_env):
    import precursor.scratchpad.store as store

    project = "Test Project Alpha"
    store.init_db()

    store.add_entry(project, "Notes", "n1", 2, metadata={"k": "v"})
    row = store.get_entry_by_display_index(project, "Notes", display_index=0)
    assert row is not None
    assert row["message"] == "n1"
    assert row["metadata"] == {"k": "v"}
    assert "metadata_json" not in row