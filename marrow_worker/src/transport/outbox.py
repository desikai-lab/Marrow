"""
WorkerOutbox — SQLite-backed persistent outbox for skeleton delivery.
Ensures that chunk payloads survive worker restarts. Delivery is attempted
immediately; on failure, rows remain PENDING and are flushed on next startup
or by the background flush loop.
"""
import asyncio
import json
import logging
import sqlite3
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    operation   TEXT    NOT NULL CHECK(operation IN ('upsert', 'delete')),
    file_path   TEXT    NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    payload     TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending', 'failed')),
    created_at  TEXT    NOT NULL,
    last_error  TEXT
);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox(status);
"""

_FAILED_ROW_WARN_THRESHOLD = 100

DeliverFn = Callable[[int, str, str, dict], Awaitable[None]]


class WorkerOutbox:
    """SQLite-backed persistent outbox for the marrow_worker."""

    def __init__(
        self,
        db_path: str,
        flush_interval: int = 60,
        flush_concurrency: int = 3,
    ) -> None:
        self._db_path = db_path
        self._flush_interval = flush_interval
        self._flush_concurrency = flush_concurrency
        self._conn: sqlite3.Connection | None = None

    async def setup(self) -> None:
        """Open the DB, enable WAL mode, and create the schema."""
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        logger.info("[Outbox] Ready at %s", self._db_path)

    async def enqueue(
        self,
        operation: str,
        file_path: str,
        chunk_count: int,
        payload: dict,
    ) -> int:
        """Write a PENDING row and return its row_id."""
        assert self._conn, "WorkerOutbox.setup() must be called before enqueue()"
        now = datetime.now(UTC).isoformat()
        cur = self._conn.execute(
            "INSERT INTO outbox (operation, file_path, chunk_count, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (operation, file_path, chunk_count, json.dumps(payload), now),
        )
        self._conn.commit()
        row_id = cur.lastrowid
        logger.debug("[Outbox] Enqueued row %d: %s %s", row_id, operation, file_path)
        return row_id

    async def mark_done(self, row_id: int) -> None:
        """Delete the outbox row on successful delivery."""
        assert self._conn
        self._conn.execute("DELETE FROM outbox WHERE id = ?", (row_id,))
        self._conn.commit()
        logger.debug("[Outbox] Row %d delivered and removed.", row_id)

    async def mark_failed(self, row_id: int, error: str) -> None:
        """Mark row as permanently failed (4xx). Never auto-retried."""
        assert self._conn
        self._conn.execute(
            "UPDATE outbox SET status = 'failed', last_error = ? WHERE id = ?",
            (error, row_id),
        )
        self._conn.commit()
        logger.error("[Outbox] Row %d marked FAILED: %s", row_id, error)
        self._warn_if_too_many_failed()

    async def flush_pending(self, deliver_fn: DeliverFn) -> None:
        """Retry all PENDING rows. Called on startup and by background loop."""
        assert self._conn
        rows = self._conn.execute(
            "SELECT id, operation, file_path, chunk_count, payload "
            "FROM outbox WHERE status = 'pending' ORDER BY id ASC"
        ).fetchall()
        if not rows:
            return
        logger.info("[Outbox] Flushing %d pending row(s)...", len(rows))
        for row_id, operation, file_path, chunk_count, payload_json in rows:
            payload = json.loads(payload_json)
            try:
                await deliver_fn(row_id, operation, file_path, payload)
            except Exception as e:
                logger.warning("[Outbox] Flush failed for row %d (%s): %s", row_id, file_path, e)

    async def flush_pending_batched(self, deliver_fn: DeliverFn) -> None:
        """
        Retry all PENDING rows with bounded concurrency (max 3 at a time).
        Uses a semaphore to avoid overloading the server with a burst of requests.
        Errors per row are caught individually — a failed row does not block others.
        """
        assert self._conn
        rows = self._conn.execute(
            "SELECT id, operation, file_path, chunk_count, payload "
            "FROM outbox WHERE status = 'pending' ORDER BY id ASC"
        ).fetchall()
        if not rows:
            return
        logger.info("[Outbox] Batched flush: %d pending row(s)...", len(rows))

        sem = asyncio.Semaphore(self._flush_concurrency)

        async def _deliver_one(row_id, operation, file_path, payload_json):
            async with sem:
                payload = json.loads(payload_json)
                try:
                    await deliver_fn(row_id, operation, file_path, payload)
                except Exception as e:
                    logger.warning(
                        "[Outbox] Batch flush failed for row %d (%s): %s",
                        row_id, file_path, e,
                    )

        await asyncio.gather(*[
            _deliver_one(row_id, op, fp, payload_json)
            for row_id, op, fp, _chunk_count, payload_json in rows
        ])

    async def background_flush_loop(self, deliver_fn: DeliverFn) -> None:
        """Runs forever, flushing pending rows every flush_interval seconds."""
        logger.info("[Outbox] Background flush loop started (interval=%ds)", self._flush_interval)
        try:
            while True:
                await asyncio.sleep(self._flush_interval)
                await self.flush_pending_batched(deliver_fn)
        except asyncio.CancelledError:
            logger.info("[Outbox] Background flush loop cancelled.")

    async def close(self) -> None:
        """Close the SQLite connection cleanly."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("[Outbox] Connection closed.")

    def _warn_if_too_many_failed(self) -> None:
        assert self._conn
        count = self._conn.execute(
            "SELECT COUNT(*) FROM outbox WHERE status = 'failed'"
        ).fetchone()[0]
        if count >= _FAILED_ROW_WARN_THRESHOLD:
            logger.warning(
                "[Outbox] WARNING: %d FAILED rows in outbox. "
                "Inspect %s for details.", count, self._db_path
            )
