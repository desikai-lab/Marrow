import asyncio
from pathlib import Path

import lancedb

from storage.entities import (
    ARTIFACT_CHUNK_SCHEMA,
    ARTIFACT_SCHEMA,
    SKELETON_CHUNK_SCHEMA,
    TASK_SCHEMA,
)

_connections: dict = {}  # cache: {db_path: lancedb.DBConnection}
_table_locks: dict[str, asyncio.Lock] = {}
_rebuild_queues: dict[str, asyncio.Queue] = {}

def get_table_lock(table_name: str) -> asyncio.Lock:
    """Returns (or creates) a per-table asyncio.Lock.
    Serialises concurrent writers to eliminate LanceDB file-lock contention.
    """
    if table_name not in _table_locks:
        _table_locks[table_name] = asyncio.Lock()
    return _table_locks[table_name]

def schedule_index_rebuild(table) -> None:
    """Non-blocking signal to rebuild the index. Safe to call from sync or async context."""
    table_name = getattr(table, "name", "unknown")
    if table_name not in _rebuild_queues:
        _rebuild_queues[table_name] = asyncio.Queue(maxsize=1)
    
    # Needs a running loop to put into queue; if no loop (e.g. startup/scripts), skip
    try:
        asyncio.get_running_loop()
        try:
            _rebuild_queues[table_name].put_nowait(table)
        except asyncio.QueueFull:
            pass  # rebuild already pending; drop duplicate
    except RuntimeError:
        pass # No loop running

async def index_rebuild_worker(table_name: str, debounce_s: int = 60) -> None:
    """
    Background task per table. Rebuilds the ANN index after debounce_s seconds
    of write inactivity.

    Strategy: if a commit conflict occurs (concurrent write preempted us), we
    simply abandon this optimize attempt and wait for the next write signal.
    This prevents spending minutes fighting an active write stream.
    """
    import logging
    logger = logging.getLogger("marrow.db")

    # Ensure queue exists
    if table_name not in _rebuild_queues:
        _rebuild_queues[table_name] = asyncio.Queue(maxsize=1)

    queue = _rebuild_queues[table_name]

    while True:
        table = await queue.get()          # block until write activity
        await asyncio.sleep(debounce_s)    # wait for burst to settle
        while not queue.empty():           # drain remaining signals
            queue.get_nowait()

        # If a new write arrived during the debounce, skip and wait again
        # (the write already enqueued a new signal, so the next loop handles it)
        try:
            row_count = table.count_rows()
            if row_count >= 256:
                logger.info("[DB] Optimizing index for '%s' (rows: %d)...", table_name, row_count)
                await asyncio.to_thread(table.optimize)
                logger.info("[DB] Optimization complete (incremental reindex + compaction).")
        except Exception as e:
            err_str = str(e).lower()
            if "conflict" in err_str or "preempted" in err_str or "retryable" in err_str:
                # Writes are still active — abandon and wait for next write signal
                logger.info("[DB] Optimization skipped (concurrent write active); will retry after next write.")
            else:
                logger.warning("[DB] index optimize failed (non-fatal): %s", e)

def get_db(project_root: str) -> lancedb.DBConnection:
    """Returns (or creates) a LanceDB connection for the given project."""
    db_path = str(Path(project_root) / ".db" / "index.lancedb")
    if db_path not in _connections:
        _connections[db_path] = lancedb.connect(db_path)
    return _connections[db_path]


def list_table_names(db: lancedb.DBConnection) -> list[str]:
    """Version-safe wrapper around db.list_tables().

    LanceDB 0.30.0 changed the return type from ``list[str]`` to a
    ``ListTablesResponse`` Pydantic model whose ``.tables`` attribute holds
    the actual list.  Iterating the model directly yields field tuples, which
    breaks ``db.open_table(name)`` with the error:
      'tuple' object cannot be converted to 'PyString'
    This helper normalises both old and new APIs to always return a plain
    ``list[str]``.
    """
    result = db.list_tables()
    # New API (>=0.30.0): Pydantic model with a .tables attribute
    if hasattr(result, "tables"):
        return result.tables
    # Legacy API: plain list or iterable of strings
    return list(result)

def get_table(project_root: str) -> lancedb.table.Table:
    """Returns the task_index table, creating it if it does not exist."""
    db = get_db(project_root)
    tables = list_table_names(db)
    if "task_index" not in tables:
        return db.create_table("task_index", schema=TASK_SCHEMA, exist_ok=True)
    return db.open_table("task_index")

def get_artifact_table(project_root: str) -> lancedb.table.Table:
    """Returns the artifact_index table, creating it if it does not exist."""
    db = get_db(project_root)
    tables = list_table_names(db)
    if "artifact_index" not in tables:
        return db.create_table("artifact_index", schema=ARTIFACT_SCHEMA, exist_ok=True)
    return db.open_table("artifact_index")

def get_chunk_table(project_root: str) -> lancedb.table.Table:
    """Returns the artifact_chunks table, creating it if it does not exist."""
    db = get_db(project_root)
    tables = list_table_names(db)
    if "artifact_chunks" not in tables:
        return db.create_table("artifact_chunks", schema=ARTIFACT_CHUNK_SCHEMA, exist_ok=True)
    return db.open_table("artifact_chunks")

def get_skeleton_table(project_root: str) -> lancedb.table.Table:
    """Returns (or creates) the code_skeleton_index table for SKEL-7."""
    db = get_db(project_root)
    tables = list_table_names(db)
    if "code_skeleton_index" not in tables:
        return db.create_table("code_skeleton_index", schema=SKELETON_CHUNK_SCHEMA, exist_ok=True)
    return db.open_table("code_skeleton_index")


# create_index_if_needed removed in PERF-04 / PERF-02.
# Use schedule_index_rebuild(table) and index_rebuild_worker instead.

def init_db(project_root: str):
    """Full initialization: creates directories and tables."""
    Path(project_root, ".db", "index.lancedb").mkdir(parents=True, exist_ok=True)
    Path(project_root, ".db", "blobs", "active").mkdir(parents=True, exist_ok=True)
    Path(project_root, ".db", "blobs", "paused").mkdir(parents=True, exist_ok=True)
    Path(project_root, ".db", "blobs", "done").mkdir(parents=True, exist_ok=True)
    
    get_table(project_root)
    get_artifact_table(project_root)
    get_chunk_table(project_root)
    get_skeleton_table(project_root)
