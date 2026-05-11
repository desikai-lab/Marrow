import asyncio
import logging
from typing import Any

import pyarrow as pa

from storage.db import get_skeleton_table, get_table_lock, list_table_names, schedule_index_rebuild
from storage.entities import SkeletonChunkRecord
from utils.metrics import track_time

logger = logging.getLogger("marrow.skeleton_repository")

# ADR-24: depth -> (allowed chunk_types | None, force_summary_only)
_DEPTH_CONFIG: dict = {
    0: (None,                                                    False),
    1: ({"file", "imports", "namespace", "class"},               True),
    2: ({"file", "imports", "namespace", "class", "method"},     False),
}


class SkeletonRepository:
    """Repository for code skeleton chunks persisted in the code_skeleton_index LanceDB table."""

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.table = get_skeleton_table(project_root)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    @track_time(layer="repository")
    async def upsert_file_chunks(
        self,
        path: str,
        project: str,
        records: list[SkeletonChunkRecord],
        **kwargs,
    ) -> int:
        """
        Delete all existing chunks for (path, project) then bulk-insert the
        new records atomically.  Returns the number of chunks stored.
        """
        async with get_table_lock(self.table.name):
            if records:
                # Ensure (type, name) is unique within this file to avoid merge ambiguity
                seen_keys = set()
                for rec in records:
                    key = (rec.chunk_type, rec.chunk_name)
                    if key in seen_keys:
                        rec.chunk_name = f"{rec.chunk_name}_L{rec.start_line}"
                    seen_keys.add((rec.chunk_type, rec.chunk_name))

                new_data = pa.Table.from_pylist([r.to_index_row() for r in records])
                def do_merge():
                    (
                        self.table
                        .merge_insert(["path", "chunk_type", "chunk_name"])
                        .when_matched_update_all()
                        .when_not_matched_insert_all()
                        .when_not_matched_by_source_delete(f"path = '{path}'")
                        .execute(new_data)
                    )
                await asyncio.to_thread(do_merge)
                schedule_index_rebuild(self.table)
                logger.info(
                    "Stored %d skeleton chunk(s) for %s:%s",
                    len(records), project, path,
                )
            else:
                # If records is empty, we still want to delete existing chunks for this path
                await asyncio.to_thread(self.table.delete, f"path = '{path}'")
                logger.warning("Cleared all chunks for %s:%s (empty input)", project, path)
            return len(records)

    @track_time(layer="repository")
    async def delete_file_chunks(self, path: str, project: str, **kwargs) -> int:
        """
        Removes all skeleton chunks for a given (path, project) pair.
        Called when marrow_worker reports a file deletion or move.
        Returns the number of chunks deleted.
        """
        async with get_table_lock(self.table.name):
            query = (
                self.table.search()
                .where(f"path = '{path}' AND project = '{project}'", prefilter=True)
                .limit(10_000)
            )
            existing = await asyncio.to_thread(query.to_list)
            count = len(existing)
            await asyncio.to_thread(self.table.delete, f"path = '{path}' AND project = '{project}'")
            logger.info("Deleted %d skeleton chunk(s) for %s:%s", count, project, path)
            return count

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    @track_time(layer="repository")
    async def cleanup_old_versions(self, older_than_hours: int = 2) -> None:
        """Remove LanceDB version snapshots and unreferenced files across all project tables.

        Covers all tables in the project DB (task_index, artifact_index, artifact_chunks,
        code_skeleton_index) to prevent fragment accumulation.
        Acquires per-table lock to prevent concurrent write conflicts.
        Raises RuntimeError (joining per-table messages) if any table fails.
        """
        import datetime

        from storage.db import get_db
        delta = datetime.timedelta(hours=older_than_hours)
        db = get_db(self.project_root)
        table_names = list_table_names(db)
        errors = []
        for t_name in table_names:
            table = db.open_table(t_name)
            async with get_table_lock(t_name):
                try:
                    current_version = await asyncio.to_thread(lambda: table.version)
                    if current_version <= 1:
                        logger.debug(
                            "Skipping version cleanup for '%s': only one snapshot exists.",
                            t_name,
                        )
                        continue
                    await asyncio.to_thread(
                        table.cleanup_old_versions,
                        older_than=delta,
                        delete_unverified=True,
                    )
                    logger.debug("Cleaned up versions for table: %s", t_name)
                except Exception as e:
                    msg = f"Failed to cleanup old versions for {t_name}: {e}"
                    logger.error(msg)
                    errors.append(msg)
        if errors:
            raise RuntimeError("\n".join(errors))

    @track_time(layer="repository")
    async def compact_files(self) -> None:
        """Merge small Parquet fragments into larger optimised files across all project tables.

        Covers all tables in the project DB. Acquires per-table lock.
        Raises RuntimeError (joining per-table messages) if any table fails.
        """
        from storage.db import get_db
        db = get_db(self.project_root)
        table_names = list_table_names(db)
        errors = []
        for t_name in table_names:
            table = db.open_table(t_name)
            async with get_table_lock(t_name):
                try:
                    await asyncio.to_thread(table.compact_files)
                    logger.debug("Compacted files for table: %s", t_name)
                except Exception as e:
                    msg = f"Failed to compact files for {t_name}: {e}"
                    logger.error(msg)
                    errors.append(msg)
        if errors:
            raise RuntimeError("\n".join(errors))

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    @track_time(layer="repository")
    async def semantic_search(
        self,
        query_vector: list[float],
        project: str | None = None,
        chunk_type: str | None = None,
        limit: int = 10,
        include_tests: bool = False,
        root_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Vector similarity search with optional prefilters on project and chunk_type.
        Returns a list of dicts (without the raw vector column).
        """
        query = self.table.search(query_vector)

        filters: list[str] = []
        if project:
            filters.append(f"project = '{project}'")
        if chunk_type:
            filters.append(f"chunk_type = '{chunk_type}'")
        if not include_tests:
            filters.append("is_test = false")          # ADR-23: column-based, not path regex
        if root_path:
            safe_root = root_path.replace("'", "''").replace('\\', '/')
            # Robust matching: any path containing the root_path (ADR-24)
            filters.append(f"path LIKE '%{safe_root}%'")
            
        if filters:
            query = query.where(" AND ".join(filters), prefilter=True)

        results = await asyncio.to_thread(query.limit(limit).to_list)
        # strip vector column from output
        return [
            {
                "path":          r["path"],
                "project":       r["project"],
                "chunk_type":    r["chunk_type"],
                "chunk_name":    r["chunk_name"],
                "skeleton_text": r["skeleton_text"],
                "start_line":    r["start_line"],
                "end_line":      r["end_line"],
                "distance":      round(r.get("_distance", 0.0), 4),
            }
            for r in results
        ]

    @track_time(layer="repository")
    async def get_exact_code_units(
        self,
        project: str,
        exact_name: str,
        chunk_type: str | None = None,
        include_tests: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Bypasses semantic search to find code units (classes, methods, properties) by their exact name.
        """
        # SECURITY CRITICAL: Sanitize inputs to prevent SQL Injection in LanceDB/DataFusion .where()
        safe_project = project.replace("'", "''")
        safe_name = exact_name.replace("'", "''")
        
        where_clause = f"project = '{safe_project}' AND chunk_name = '{safe_name}'"
        
        if chunk_type:
            safe_type = chunk_type.replace("'", "''")
            where_clause += f" AND chunk_type = '{safe_type}'"

        if not include_tests:
            where_clause += " AND is_test = false"

        results = await asyncio.to_thread(lambda: self.table.search().where(where_clause).to_list())
        
        return [
            {
                "path":          r["path"],
                "project":       r["project"],
                "chunk_type":    r["chunk_type"],
                "chunk_name":    r["chunk_name"],
                "skeleton_text": r["skeleton_text"],
                "start_line":    r["start_line"],
                "end_line":      r["end_line"]
            }
            for r in results
        ]

    @track_time(layer="repository")
    async def get_file_skeleton_chunks(
        self,
        path: str,
        project: str,
        depth: int = 0,
        summary_only: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Retrieves all skeleton chunks for a file, sorted by start_line.
        depth: 0=all, 1=class/namespace names only, 2=class+method signatures.
        summary_only: strip skeleton_text (honoured only at depth=0).
        """
        posix_path = path.replace('\\', '/')
        results = await asyncio.to_thread(
            lambda: (
                self.table.search()
                .where(f"path LIKE '%{posix_path}' AND project = '{project}'")
                .to_list()
            )
        )
        
        allowed_types, force_summary = _DEPTH_CONFIG.get(depth, (None, False))
        if allowed_types:
            results = [r for r in results if r["chunk_type"] in allowed_types]
        elif summary_only:
            results = [r for r in results if r["chunk_type"] != "property"]
            
        strip_text_flag = force_summary or (depth == 0 and summary_only)
        
        formatted = []
        for r in sorted(results, key=lambda x: x["start_line"]):
            chunk = {
                "path":          r["path"],
                "project":       r["project"],
                "chunk_type":    r["chunk_type"],
                "chunk_name":    r["chunk_name"],
                "start_line":    r["start_line"],
                "end_line":      r["end_line"],
            }

            should_strip = strip_text_flag and r["chunk_type"] != "imports"

            if not should_strip:
                chunk["skeleton_text"] = r["skeleton_text"]
            formatted.append(chunk)
            
        return formatted

    @track_time(layer="repository")
    async def get_all_indexed_paths(self, project: str, include_tests: bool = False) -> list[str]:
        """Returns unique file paths from file-level chunks in the skeleton index."""
        safe_project = project.replace("'", "''")
        where_clause = f"project = '{safe_project}' AND chunk_type = 'file'"
        if not include_tests:
            where_clause += " AND is_test = false"
            
        results = await asyncio.to_thread(
            lambda: (
                self.table.search()
                .where(where_clause)
                .to_list()
            )
        )
        seen: set = set()
        paths = []
        for r in results:
            p = r["path"]
            if p not in seen:
                seen.add(p)
                paths.append(p)
        return paths
