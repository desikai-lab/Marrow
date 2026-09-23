import asyncio
import logging
from typing import Any

from config import EMBEDDING_MODEL_TEXT, MAX_EMBED_CHARS
from utils.metrics import track_time

from storage.db import (
    get_artifact_table,
    get_chunk_table,
    get_keyword_table,
    schedule_index_rebuild,
)
from storage.embeddings import embeddings_manager
from storage.entities import ArtifactChunkRecord, ArtifactRecord

logger = logging.getLogger("marrow.artifact_repository")


def _build_scope_filter(scopes: list[str]) -> str:
    """Builds a LanceDB SQL WHERE expression matching any chunk whose `path`
    lies strictly under one of the given directory scopes (OR semantics).
    Every scope is escaped so that quote/wildcard characters in it are treated
    as literal data, never as SQL/LIKE syntax (REQ-06). Pure function, no I/O.
    """
    clauses = []
    for scope in scopes:
        # Escape order matters: backslash first, then quote, then LIKE metachars.
        esc = scope.replace("\\", "\\\\").replace("'", "''").replace("%", "\\%").replace("_", "\\_")
        clauses.append(f"path LIKE '{esc}/%' ESCAPE '\\'")
    return "(" + " OR ".join(clauses) + ")"


def _reciprocal_rank_fusion(
    vector_results: list[dict[str, Any]],
    keyword_results: list[dict[str, Any]],
    limit: int,
    k: int = 60,
) -> list[dict[str, Any]]:
    """Merges vector and keyword search results using Reciprocal Rank Fusion (RRF).
    Calculates RRF score = 1/(k + rank_v) + 1/(k + rank_k).
    Result items contain 'match': 'vector' | 'keyword' | 'both'.
    """
    scores: dict[tuple[str, int, int], float] = {}
    item_map: dict[tuple[str, int, int], dict[str, Any]] = {}
    lane_map: dict[tuple[str, int, int], set[str]] = {}

    for rank, item in enumerate(vector_results, start=1):
        key = (item["path"], item["start_line"], item["end_line"])
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
        item_map[key] = item
        lane_map.setdefault(key, set()).add("vector")

    for rank, item in enumerate(keyword_results, start=1):
        key = (item["path"], item["start_line"], item["end_line"])
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
        if key not in item_map:
            item_map[key] = item
        lane_map.setdefault(key, set()).add("keyword")

    fused = []
    for key, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]:
        lanes = lane_map[key]
        match_type = "both" if len(lanes) == 2 else next(iter(lanes))
        entry = dict(item_map[key])
        entry["match"] = match_type
        fused.append(entry)

    return fused


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

    async def upsert_chunks(self, path: str, content: str, updated: str, ext: str = ".md") -> list:
        from tools.utils.project_settings import load_project_settings

        from storage.artifact_chunker import ChunkerFactory

        await asyncio.to_thread(self.table.delete, f"path = '{path}'")
        chunker = ChunkerFactory.get(ext)
        settings = load_project_settings(self.project_root)
        records = []

        chunks = list(
            chunker.chunk(content, MAX_EMBED_CHARS, overlap_pct=settings.chunk_overlap_pct)
        )
        for chunk in chunks:
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

        return chunks  # CHANGED from None -- application layer needs these for keyword extraction

    async def save_keyword_records(self, path: str, records: list) -> None:
        """Infrastructure-only: writes already-prepared keyword records to the
        separate artifact_chunk_keywords table. Performs no extraction --
        callers (application layer) are responsible for producing
        fully-formed ArtifactChunkKeywordRecord instances before calling this.
        Delete-then-insert, same convention as upsert_chunks' own table writes.
        """
        kw_table = get_keyword_table(self.project_root)
        await asyncio.to_thread(kw_table.delete, f"path = '{path}'")
        rows = [r.to_index_row() for r in records]
        if rows:
            await asyncio.to_thread(kw_table.add, rows)
            schedule_index_rebuild(kw_table)

    async def change_path(self, old_path: str, new_path: str) -> int:
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

        # F4000249: keep artifact_chunk_keywords path in lockstep, best-effort
        try:
            kw_table = get_keyword_table(self.project_root)
            kw_rows = await asyncio.to_thread(
                kw_table.search().where(f"path = '{old_path}'", prefilter=True).to_list
            )
            if kw_rows:
                await asyncio.to_thread(kw_table.add, [dict(r, path=new_path) for r in kw_rows])
                await asyncio.to_thread(kw_table.delete, f"path = '{old_path}'")
        except Exception as e:
            logger.warning(
                "Keyword-table path change failed for %s -> %s: %s", old_path, new_path, e
            )

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

        # F4000249: prune keyword rows for this path, best-effort
        try:
            await asyncio.to_thread(get_keyword_table(self.project_root).delete, f"path = '{path}'")
        except Exception as e:
            logger.warning("Keyword-table prune failed for %s: %s", path, e)

        return count

    async def _keyword_lane_search(
        self, query_text: str, limit: int = 5, scopes: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Queries the artifact_chunk_keywords table using LanceDB FTS (BM25)."""
        kw_table = get_keyword_table(self.project_root)
        search = kw_table.search(query_text, query_type="fts", use_tantivy=False)
        if scopes:
            search = search.where(_build_scope_filter(scopes), prefilter=True)
        raw_rows = await asyncio.to_thread(search.limit(limit).to_list)

        results = []
        for r in raw_rows:
            results.append(
                {
                    "path": r.get("path", ""),
                    "section": r.get("section", ""),
                    "start_line": r.get("start_line", 1),
                    "end_line": r.get("end_line", 1),
                    "distance": 0.0,
                }
            )
        return results

    @track_time(layer="repository")
    async def semantic_search(
        self, query_text: str, limit: int = 5, scopes: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Performs search against artifact chunks.
        If LITERAL_EXTRACTION flag is ON, runs both vector search and BM25 keyword
        search concurrently, fusing results via RRF.
        If flag is OFF, runs standard vector search only.
        """
        from tools.utils.project_settings import load_project_settings

        settings = load_project_settings(self.project_root)

        # 1. Vector lane search
        query_vector = await asyncio.to_thread(
            embeddings_manager.generate_vector, query_text, model_name=EMBEDDING_MODEL_TEXT
        )
        vector_results = []
        if query_vector is not None:
            query = self.table.search(query_vector)
            if scopes:
                query = query.where(_build_scope_filter(scopes), prefilter=True)

            raw_vector_results = await asyncio.to_thread(query.limit(limit).to_list)
            for r in raw_vector_results:
                vector_results.append(
                    {
                        "path": r.get("path", ""),
                        "section": r.get("section", ""),
                        "start_line": r.get("start_line", 1),
                        "end_line": r.get("end_line", 1),
                        "distance": round(r.get("_distance", 0.0), 4),
                    }
                )

        if not settings.literal_extraction:
            return vector_results

        # 2. Keyword lane search (if flag ON, best-effort)
        keyword_results = []
        try:
            keyword_results = await self._keyword_lane_search(
                query_text, limit=limit, scopes=scopes
            )
        except Exception as e:
            logger.warning(
                "Keyword lane search failed for '%s': %s (vector lane intact)", query_text, e
            )

        return _reciprocal_rank_fusion(vector_results, keyword_results, limit=limit)
