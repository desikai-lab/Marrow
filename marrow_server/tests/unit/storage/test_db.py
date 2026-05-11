from pathlib import Path

from storage.db import get_db, get_table


def test_init_db_fresh_project_creates_all_required_directories(tmp_project_root):
    """Verifies creation of all necessary directories."""
    base = Path(tmp_project_root) / ".db"
    assert (base / "index.lancedb").exists()
    assert (base / "blobs" / "active").exists()
    assert (base / "blobs" / "paused").exists()
    assert (base / "blobs" / "done").exists()


def test_get_table_initialised_db_returns_task_index_table(tmp_project_root):
    """Verifies table existence and type."""
    table = get_table(tmp_project_root)
    assert table is not None
    # table.name might be task_index
    response = get_db(tmp_project_root).list_tables()
    tables = getattr(response, "tables", response)
    assert "task_index" in tables


def test_get_db_same_project_root_returns_same_connection_instance(tmp_project_root):
    """Verifies that get_db returns the same connection instance."""
    db1 = get_db(tmp_project_root)
    db2 = get_db(tmp_project_root)
    assert db1 is db2


def test_get_table_repeated_calls_return_valid_non_null_objects(tmp_project_root):
    """Verifies that get_table for the same project returns a valid object."""
    # Note: LanceDB table objects might be different on each open_table call,
    # but in our implementation get_table calls open_table.
    # We check functional validity.
    t1 = get_table(tmp_project_root)
    t2 = get_table(tmp_project_root)
    # The current db.py caches the connection, not the table object itself.
    # This is acceptable behavior.
    assert t1 is not None and t2 is not None
