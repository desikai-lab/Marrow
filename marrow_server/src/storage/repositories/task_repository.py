import asyncio
import logging
from typing import Any

import pyarrow.compute as pc

from config import EMBEDDING_MODEL_TEXT
from domain.enums import TaskPriority, TaskStatus, TaskType
from storage.db import get_table
from storage.embeddings import embeddings_manager
from storage.entities import TaskRecord
from utils.metrics import track_time

logger = logging.getLogger("marrow.task_repository")


class TaskRepository:
    """Repository for task access via LanceDB."""

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.table = get_table(project_root)

    def _row_to_record(self, row: dict[str, Any]) -> TaskRecord:
        return TaskRecord(
            id=row.get("id"),
            key=row.get("key"),
            title=row.get("title"),
            type=row.get("type"),
            status=row.get("status"),
            priority=row.get("priority"),
            file_path=row.get("file_path"),
            updated=row.get("updated"),
            project=row.get("project"),
            vector=row.get("vector"),
        )

    async def _ensure_vector(self, record: TaskRecord) -> TaskRecord:
        """Generates a vector if one is not already present."""
        if getattr(record, "vector", None) is None:
            text_to_embed = f"{record.title} {getattr(record, 'problem', '') or ''}".strip()
            if text_to_embed:
                logger.debug(f"Generating vector for task {record.key}...")
                record.vector = await asyncio.to_thread(
                    embeddings_manager.generate_vector,
                    text_to_embed,
                    model_name=EMBEDDING_MODEL_TEXT,
                )
        return record

    async def insert(self, record: TaskRecord) -> None:
        """Inserts a new record."""
        record = await self._ensure_vector(record)
        await asyncio.to_thread(self.table.add, [record.to_index_row()])
        from storage.db import schedule_index_rebuild

        schedule_index_rebuild(self.table)

    async def upsert(self, record: TaskRecord) -> None:
        """Updates or inserts a record."""
        await asyncio.to_thread(self.table.delete, f"id = {record.id}")
        record = await self._ensure_vector(record)
        await asyncio.to_thread(self.table.add, [record.to_index_row()])
        from storage.db import schedule_index_rebuild

        schedule_index_rebuild(self.table)

    async def delete(self, task_id: int) -> None:
        """Deletes a record by ID."""
        await asyncio.to_thread(self.table.delete, f"id = {task_id}")

    async def get_next_id(self) -> int:
        """Returns the next available integer ID."""
        if self.table.count_rows() == 0:
            return 1
        arrow_table = await asyncio.to_thread(self.table.to_arrow)
        ids = arrow_table.column("id")
        if len(ids) > 0:
            return int(pc.max(ids).as_py()) + 1
        return 1

    @track_time(layer="repository")
    async def get_by_id(self, task_id: int) -> TaskRecord | None:
        """Finds a task by its integer ID."""
        results = await asyncio.to_thread(
            self.table.search().where(f"id = {task_id}", prefilter=True).limit(1).to_list
        )
        return self._row_to_record(results[0]) if results else None

    @track_time(layer="repository")
    async def get_by_key(self, key: str) -> TaskRecord | None:
        """Finds a task by its string key (e.g. 'F1')."""
        results = await asyncio.to_thread(
            self.table.search().where(f"key = '{key}'", prefilter=True).limit(1).to_list
        )
        return self._row_to_record(results[0]) if results else None

    @track_time(layer="repository")
    async def search(
        self,
        status: TaskStatus | str | None = None,
        priority: TaskPriority | str | None = None,
        type: TaskType | str | None = None,
        project: str | None = None,
    ) -> list[TaskRecord]:
        """Searches tasks by filter criteria."""
        filters = []
        if status:
            filters.append(f"status = '{status}'")
        if priority:
            filters.append(f"priority = '{priority}'")
        if type:
            filters.append(f"type = '{type}'")
        if project:
            filters.append(f"project = '{project}'")
        query = self.table.search()
        if filters:
            where_clause = " AND ".join(filters)
            query = query.where(where_clause, prefilter=True)

        results = await asyncio.to_thread(query.to_list)
        return [self._row_to_record(r) for r in results]

    @track_time(layer="repository")
    async def semantic_search(self, query_text: str, limit: int = 5) -> list[dict[str, Any]]:
        """Semantic search by task meaning.
        Returns dicts with keys 'record: TaskRecord' and 'distance: float'"""
        query_vector = await asyncio.to_thread(
            embeddings_manager.generate_vector, query_text, model_name=EMBEDDING_MODEL_TEXT
        )
        if query_vector is None:
            return []

        results = await asyncio.to_thread(self.table.search(query_vector).limit(limit).to_list)
        return [
            {"record": self._row_to_record(r), "distance": r.get("_distance", 0.0)} for r in results
        ]
