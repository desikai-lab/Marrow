"""
Unit tests for WorkerOutbox (src/transport/outbox.py).
All tests use an in-memory SQLite DB for isolation.
"""

import asyncio

from src.transport.outbox import WorkerOutbox


def run(coro):
    """Sync wrapper consistent with existing worker test style."""
    return asyncio.run(coro)


def make_outbox() -> WorkerOutbox:
    outbox = WorkerOutbox(db_path=":memory:", flush_interval=60)
    run(outbox.setup())
    return outbox


def make_outbox_batched(concurrency: int = 3) -> WorkerOutbox:
    outbox = WorkerOutbox(db_path=":memory:", flush_interval=60, flush_concurrency=concurrency)
    run(outbox.setup())
    return outbox


# ---------------------------------------------------------------------------
# FR-01: Row created as PENDING before any delivery attempt
# ---------------------------------------------------------------------------
def test_enqueue_creates_pending_row():
    outbox = make_outbox()
    payload = {"project_name": "test", "path": "foo/bar.py", "chunks": []}
    row_id = run(outbox.enqueue("upsert", "foo/bar.py", 3, payload))
    assert row_id is not None and row_id > 0
    row = outbox._conn.execute("SELECT status FROM outbox WHERE id = ?", (row_id,)).fetchone()
    assert row is not None
    assert row[0] == "pending"


# ---------------------------------------------------------------------------
# FR-02: Row deleted after successful delivery
# ---------------------------------------------------------------------------
def test_mark_done_removes_row():
    outbox = make_outbox()
    payload = {"project_name": "test", "path": "foo/bar.py", "chunks": []}
    row_id = run(outbox.enqueue("upsert", "foo/bar.py", 0, payload))
    run(outbox.mark_done(row_id))
    row = outbox._conn.execute("SELECT id FROM outbox WHERE id = ?", (row_id,)).fetchone()
    assert row is None


# ---------------------------------------------------------------------------
# FR-10 & FR-08: 4xx → mark FAILED, last_error stored
# ---------------------------------------------------------------------------
def test_mark_failed_persists_error():
    outbox = make_outbox()
    payload = {"project_name": "test", "path": "foo/bar.py", "chunks": []}
    row_id = run(outbox.enqueue("upsert", "foo/bar.py", 0, payload))
    run(outbox.mark_failed(row_id, "HTTP 422: Unprocessable Entity"))
    row = outbox._conn.execute(
        "SELECT status, last_error FROM outbox WHERE id = ?", (row_id,)
    ).fetchone()
    assert row[0] == "failed"
    assert "422" in row[1]


# ---------------------------------------------------------------------------
# FR-04 & FR-05: flush_pending calls deliver_fn and removes row on success
# ---------------------------------------------------------------------------
def test_flush_pending_delivers_and_clears():
    outbox = make_outbox()
    payload = {"project_name": "test", "path": "foo/bar.py", "chunks": []}
    row_id = run(outbox.enqueue("upsert", "foo/bar.py", 2, payload))

    calls = []

    async def mock_deliver(rid, operation, file_path, payload_dict):
        calls.append((rid, operation, file_path))
        await outbox.mark_done(rid)  # simulate successful delivery

    run(outbox.flush_pending(mock_deliver))
    assert len(calls) == 1
    assert calls[0] == (row_id, "upsert", "foo/bar.py")
    row = outbox._conn.execute("SELECT id FROM outbox WHERE id = ?", (row_id,)).fetchone()
    assert row is None


# ---------------------------------------------------------------------------
# FR-03: Row stays PENDING when deliver_fn raises a network error
# ---------------------------------------------------------------------------
def test_flush_pending_leaves_on_network_error():
    outbox = make_outbox()
    payload = {"project_name": "test", "path": "foo/bar.py", "chunks": []}
    row_id = run(outbox.enqueue("upsert", "foo/bar.py", 2, payload))

    async def failing_deliver(rid, operation, file_path, payload_dict):
        raise ConnectionError("network down")

    run(outbox.flush_pending(failing_deliver))  # must not raise
    row = outbox._conn.execute("SELECT status FROM outbox WHERE id = ?", (row_id,)).fetchone()
    assert row is not None
    assert row[0] == "pending"  # still pending, not deleted


# ---------------------------------------------------------------------------
# FR-06: delete operation also enqueues correctly (operation field)
# ---------------------------------------------------------------------------
def test_delete_operation_enqueued_correctly():
    outbox = make_outbox()
    payload = {"project_name": "test", "path": "old/file.py"}
    row_id = run(outbox.enqueue("delete", "old/file.py", 0, payload))
    row = outbox._conn.execute(
        "SELECT operation, chunk_count FROM outbox WHERE id = ?", (row_id,)
    ).fetchone()
    assert row[0] == "delete"
    assert row[1] == 0


# ---------------------------------------------------------------------------
# PERF-FIX-4: Batched flush delivers all pending rows
# ---------------------------------------------------------------------------
def test_flush_pending_batched_delivers_all():
    outbox = make_outbox_batched()
    run(outbox.enqueue("upsert", "f1.py", 1, {"p": 1}))
    run(outbox.enqueue("upsert", "f2.py", 1, {"p": 2}))

    delivered = []

    async def mock_deliver(rid, op, fp, payload):
        delivered.append(fp)
        await outbox.mark_done(rid)

    run(outbox.flush_pending_batched(mock_deliver))
    assert len(delivered) == 2
    assert "f1.py" in delivered
    assert "f2.py" in delivered

    rows = outbox._conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
    assert rows == 0


# ---------------------------------------------------------------------------
# PERF-FIX-4: One failure in batch does not block others
# ---------------------------------------------------------------------------
def test_flush_pending_batched_one_failure_does_not_block():
    outbox = make_outbox_batched()
    run(outbox.enqueue("upsert", "fail.py", 1, {"p": 1}))
    run(outbox.enqueue("upsert", "pass.py", 1, {"p": 2}))

    delivered = []

    async def selective_deliver(rid, op, fp, payload):
        if fp == "fail.py":
            raise ValueError("Boom")
        delivered.append(fp)
        await outbox.mark_done(rid)

    run(outbox.flush_pending_batched(selective_deliver))
    assert "pass.py" in delivered
    assert "fail.py" not in delivered

    # fail.py should still be in DB
    rows = outbox._conn.execute("SELECT file_path FROM outbox").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "fail.py"


# ---------------------------------------------------------------------------
# PERF-FIX-4: Respects concurrency limit
# ---------------------------------------------------------------------------
def test_flush_pending_batched_respects_concurrency():
    outbox = make_outbox_batched(concurrency=2)
    for i in range(5):
        run(outbox.enqueue("upsert", f"file{i}.py", 1, {}))

    active_count = 0
    max_active = 0

    async def throttled_deliver(rid, op, fp, payload):
        nonlocal active_count, max_active
        active_count += 1
        max_active = max(max_active, active_count)
        await asyncio.sleep(0.1)  # hold the slot
        active_count -= 1
        await outbox.mark_done(rid)

    run(outbox.flush_pending_batched(throttled_deliver))

    assert max_active == 2
    rows = outbox._conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
    assert rows == 0
