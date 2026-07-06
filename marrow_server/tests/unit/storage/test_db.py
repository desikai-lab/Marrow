import asyncio
import logging
from pathlib import Path

import pytest

from storage.db import TableLockContext, get_db, get_table, get_table_lock
from utils.exceptions import StorageTimeoutError


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


@pytest.mark.asyncio
async def test_table_lock_context_fast_path_acquires_immediately_and_logs_debug(
    caplog, tmp_project_root
):
    caplog.set_level(logging.DEBUG, logger="marrow.db")
    async with TableLockContext("test_table_fast"):
        pass
    debug_logs = [r.message for r in caplog.records if r.levelname == "DEBUG"]
    assert any("acquired" in msg for msg in debug_logs)
    assert any("released" in msg for msg in debug_logs)


@pytest.mark.asyncio
async def test_table_lock_context_warns_at_fifty_percent_then_still_acquires(
    caplog, tmp_project_root
):
    caplog.set_level(logging.WARNING, logger="marrow.db")
    lock = get_table_lock("test_table_warn")
    await lock.acquire()

    async def release_later():
        await asyncio.sleep(0.3)
        lock.release()

    asyncio.create_task(release_later())

    async with TableLockContext("test_table_warn", timeout=0.4):
        pass

    warning_logs = [r.message for r in caplog.records if r.levelname == "WARNING"]
    assert any("still waiting on 'test_table_warn'" in msg for msg in warning_logs)


@pytest.mark.asyncio
async def test_table_lock_context_raises_storage_timeout_error_on_full_timeout(tmp_project_root):
    lock = get_table_lock("test_table_timeout")
    await lock.acquire()

    try:
        with pytest.raises(StorageTimeoutError) as exc_info:
            async with TableLockContext("test_table_timeout", timeout=0.2):
                pass
        assert exc_info.value.details["table_name"] == "test_table_timeout"
        assert exc_info.value.details["timeout"] == 0.2
    finally:
        lock.release()


@pytest.mark.asyncio
async def test_table_lock_context_does_not_release_unheld_lock_on_timeout(tmp_project_root):
    lock = get_table_lock("test_table_no_release")
    await lock.acquire()

    try:
        with pytest.raises(StorageTimeoutError):
            async with TableLockContext("test_table_no_release", timeout=0.1):
                pass

        assert lock.locked()
    finally:
        lock.release()


@pytest.mark.asyncio
async def test_table_lock_context_reuses_existing_asyncio_lock_from_get_table_lock(
    tmp_project_root,
):
    lock = get_table_lock("test_table_reuse")
    ctx = TableLockContext("test_table_reuse")
    assert ctx._lock is lock
