import asyncio
import logging
from typing import Any

from config import EMBEDDING_MODEL_TEXT, MAX_EMBED_CHARS
from utils.metrics import track_time

from storage.artifact_chunker import ChunkerFactory
from storage.db import get_artifact_table, get_chunk_table, schedule_index_rebuild
from storage.embeddings import embeddings_manager
from storage.entities import ArtifactChunkRecord, ArtifactRecord

logger = logging.getLogger("marrow.artifact_repository")


class ArtifactRepository:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.table = get_artifact_table(project_root)

    async def _ensure_vector(self, record: ArtifactRecord, content: str) -> ArtifactRecord:
        if getattr(record, "vector", None) is None and content:
            logger.debug(f"Generating vector for artifact {record.path}...")
            text_to_embed = content[:MAX_EMBED_CHARS]
            record.vector = await asyncio.to_thread(
                embeddings_manager.generate_vector, text_to_embed, model_name=EMBEDDING_MODEL_TEXT
            )
        return record

    def _row_to_record(self, row: dict[str, Any]) -> ArtifactRecord:
        return ArtifactRecord(
            path=row.get("path"), updated=row.get("updated"), vector=row.get("vector")
        )

    async def upsert(self, path: str, content: str, updated: str) -> None:
        await asyncio.to_thread(self.table.delete, f"path = '{path}'")
        record = ArtifactRecord(path=path, updated=updated)
        record = await self._ensure_vector(record, content)

        if record.vector is not None:
            await asyncio.to_thread(self.table.add, [record.to_index_row()])
            schedule_index_rebuild(self.table)
            logger.info(f"Artifact {path} indexed successfully.")
        else:
            logger.warning(f"Could not generate vector for artifact {path}, skipping index.")

    async def delete(self, path: str) -> None:
        await asyncio.to_thread(self.table.delete, f"path = '{path}'")
        logger.info(f"Artifact {path} deleted from index.")

    async def rename(self, old_path: str, new_path: str) -> None:
        results = await asyncio.to_thread(
            self.table.search().where(f"path = '{old_path}'", prefilter=True).limit(1).to_list
        )
        if results:
            row = results[0]
            row["path"] = new_path
            await asyncio.to_thread(self.table.delete, f"path = '{old_path}'")
            await asyncio.to_thread(self.table.add, [row])
            logger.info(f"Artifact renamed in index: {old_path} -> {new_path}")
        else:
            logger.warning(f"Artifact {old_path} not found in index for renaming.")

    @track_time(layer="repository")
    async def semantic_search(self, query_text: str, limit: int = 5) -> list[dict[str, Any]]:
        query_vector = await asyncio.to_thread(
            embeddings_manager.generate_vector, query_text, model_name=EMBEDDING_MODEL_TEXT
        )
        if query_vector is None:
            return []

        results = await asyncio.to_thread(self.table.search(query_vector).limit(limit).to_list)
        return [
            {"record": self._row_to_record(r), "distance": r.get("_distance", 0.0)} for r in results
        ]


class ArtifactChunkRepository:
    def __init__(self, project_root: str):
        self.project_root = project_root
        # Handle is cached in db._connections; safe singleton access
        self.table = get_chunk_table(project_root)

    async def upsert_chunks(self, path: str, content: str, updated: str, ext: str = ".md") -> None:
        await asyncio.to_thread(self.table.delete, f"path = '{path}'")
        chunker = ChunkerFactory.get(ext)
        records = []

        for chunk in chunker.chunk(content, MAX_EMBED_CHARS):
            vector = await asyncio.to_thread(
                embeddings_manager.generate_vector, chunk.text, model_name=EMBEDDING_MODEL_TEXT
            )
            if vector is not None:
                record_dto = ArtifactChunkRecord(
                    path=path,
                    section=chunk.section,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    updated=updated,
                    vector=vector,
                )
                records.append(record_dto.to_index_row())

        if records:
            await asyncio.to_thread(self.table.add, records)
            schedule_index_rebuild(self.table)
            logger.info(f"Generated and indexed {len(records)} chunks for artifact {path}.")
        else:
            logger.warning(f"No chunks vectorised for artifact {path}.")

    async def rename(self, old_path: str, new_path: str) -> int:
        """Metadata-only path rename across ALL chunk rows for old_path.
        Insert-before-delete: favors transient duplication over data loss.
        Returns the number of chunk rows renamed (0 if none found).
        """
        results = await asyncio.to_thread(
            self.table.search().where(f"path = '{old_path}'", prefilter=True).to_list
        )
        if not results:
            logger.warning(
                f"No chunks found for {old_path} during rename; caller should fall back to full upsert."
            )
            return 0

        new_rows = [dict(row, path=new_path) for row in results]
        await asyncio.to_thread(self.table.add, new_rows)

        try:
            await asyncio.to_thread(self.table.delete, f"path = '{old_path}'")
        except Exception as e:
            logger.error(
                f"Rename {old_path} -> {new_path}: new rows added, but failed to delete "
                f"old rows: {e}. Old rows are now ghosts — will be pruned by TD4000174 "
                f"maintenance pass, or the next full `reindex-chunks` run."
            )

        schedule_index_rebuild(self.table)
        logger.info(f"Renamed {len(new_rows)} chunk(s) in index: {old_path} -> {new_path}")
        return len(new_rows)

    async def count_rows(self) -> int:
        """Row count for the empty-table short-circuit used by GhostPruner
        (see storage/ghost_pruner.py, ADR-0043)."""
        return await asyncio.to_thread(self.table.count_rows)

    async def get_all_indexed_paths(self, project: str) -> list[str]:
        """Returns unique paths currently indexed in this project's artifact-
        chunk table. `project` is accepted for GhostPruningRepository protocol
        parity (see storage/ghost_pruner.py); it is not used to filter rows
        because this table already holds exactly one project's data (scoped
        via project_root at __init__) and carries no `project` column,
        unlike SkeletonChunkRecord.
        """
        results = await asyncio.to_thread(self.table.search().to_list)
        seen: set[str] = set()
        paths: list[str] = []
        for r in results:
            p = r["path"]
            if p not in seen:
                seen.add(p)
                paths.append(p)
        return paths

    async def delete_chunks_by_path(self, path: str, project: str) -> int:
        """Deletes all chunk rows for `path`. `project` accepted for protocol
        parity, unused for the same reason as get_all_indexed_paths above.
        Returns the number of rows deleted.
        """
        results = await asyncio.to_thread(
            self.table.search().where(f"path = '{path}'", prefilter=True).to_list
        )
        count = len(results)
        await asyncio.to_thread(self.table.delete, f"path = '{path}'")
        logger.info(f"Pruned {count} ghost chunk(s) for artifact {path}.")
        return count


    @track_time(layer="repository")
    async def semantic_search(self, query_text: str, limit: int = 5) -> list[dict[str, Any]]:
        query_vector = await asyncio.to_thread(
            embeddings_manager.generate_vector, query_text, model_name=EMBEDDING_MODEL_TEXT
        )
        if query_vector is None:
            return []

        results = await asyncio.to_thread(self.table.search(query_vector).limit(limit).to_list)
        formatted = []
        for r in results:
            formatted.append(
                {
                    "path": r.get("path", ""),
                    "section": r.get("section", ""),
                    "start_line": r.get("start_line", 1),
                    "end_line": r.get("end_line", 1),
                    "distance": round(r.get("_distance", 0), 4),
                }
            )
        return formatted
