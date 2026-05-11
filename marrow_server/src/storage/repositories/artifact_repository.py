import asyncio
import logging
from typing import Any

from config import EMBEDDING_MODEL_TEXT, MAX_EMBED_CHARS
from storage.artifact_chunker import ChunkerFactory
from storage.db import get_artifact_table, get_chunk_table, schedule_index_rebuild
from storage.embeddings import embeddings_manager
from storage.entities import ArtifactChunkRecord, ArtifactRecord
from utils.metrics import track_time

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
