import asyncio
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from common import path_resolver
from common.path_resolver import (
    HISTORY_TIMESTAMP_FORMAT,
    NAMESPACE_TASKS,
    ResourceKind,
    get_path,
    get_raw_path,
)
from common.project_file_error import ProjectFileError
from common.project_path import ProjectPath
from domain.validators.status_change import StatusChangeValidator
from storage.blobs import read_blob, write_blob
from storage.entities import TaskRecord
from storage.repositories import ArtifactChunkRepository, ArtifactRepository, TaskRepository
from utils.exceptions import DomainProtectionError, TaskNotFoundError

VALID_TRANSITIONS = {
    "open": ["paused", "closed", "analysis", "blocked"],
    "blocked": ["closed", "paused", "open"],
    "paused": ["open", "closed"],
    "analysis": ["open", "closed", "paused"],
    "closed": [],
}

# Files that may never be fully overwritten — only appended/section-patched
PROTECTED_FILES = [
    "memory/decisions.md",
]


class UnitOfWork:
    """Business-transaction orchestrator (Blob + LanceDB)."""

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.tasks = TaskRepository(project_root)
        self.artifacts = ArtifactRepository(project_root)
        self.chunks = ArtifactChunkRepository(project_root)

    def _check_domain_protection(self, path: str) -> None:
        """Raises DomainProtectionError if path points to a protected file."""
        normalized = path.replace("\\", "/").lstrip("/")
        for protected in PROTECTED_FILES:
            if normalized == protected:
                raise DomainProtectionError(
                    f"Direct overwrite of '{path}' is forbidden. Use append_section.",
                    details={"protected_file": path},
                )

    async def update_task_atomically(self, task_key: str, new_data: dict[str, Any]) -> TaskRecord:
        """Atomically updates a task (Blob + LanceDB) with Rollback support."""
        from storage.db import TableLockContext

        async with TableLockContext(self.tasks.table.name):
            current_record = await self.tasks.get_by_key(task_key)
        if not current_record:
            raise TaskNotFoundError(f"Task '{task_key}' not found in index")

        file_path = os.path.join(self.project_root, current_record.file_path)
        try:
            current_full_data = await asyncio.to_thread(read_blob, file_path)
        except FileNotFoundError:
            # Fallback to index data when the blob file is missing
            current_full_data = {
                "id": current_record.id,
                "key": current_record.key,
                "title": current_record.title,
                "type": current_record.type,
                "status": current_record.status,
                "priority": current_record.priority,
                "project": current_record.project,
            }

        # Create a Backup for Rollback (per-item timestamped history)
        history_dir = path_resolver.get_history_raw_dir(
            self.project_root, current_record.file_path, path_resolver.NAMESPACE_TASKS
        )
        os.makedirs(history_dir, exist_ok=True)
        timestamp = datetime.now().strftime(path_resolver.HISTORY_TIMESTAMP_FORMAT)
        backup_path = os.path.join(history_dir, f"{timestamp}.md")

        if os.path.exists(file_path):
            await asyncio.to_thread(shutil.copy2, file_path, backup_path)

        updated_data = {**current_full_data, **new_data}
        updated_data["updated"] = datetime.now().isoformat()
        updated_data["key"] = task_key
        updated_data["id"] = current_record.id
        updated_data["project"] = current_record.project

        old_abs_path = str(Path(file_path).absolute())

        try:
            # Phase 1: Write Blob
            new_blob_path = await asyncio.to_thread(write_blob, self.project_root, updated_data)
            new_abs_path = str(new_blob_path.absolute())

            record = TaskRecord(
                id=current_record.id,
                key=task_key,
                title=updated_data.get("title", ""),
                type=updated_data.get("type", "F"),
                status=updated_data.get("status", "open"),
                priority=updated_data.get("priority", "medium"),
                file_path=str(Path(new_blob_path).relative_to(self.project_root)).replace(
                    "\\", "/"
                ),
                updated=updated_data["updated"],
                project=current_record.project,
                problem=updated_data.get("problem"),
                solution=updated_data.get("solution"),
                blocked_by=updated_data.get("blocked_by", []),
                where=updated_data.get("where", []),
                comments=updated_data.get("comments"),
                resolution=updated_data.get("resolution"),
            )

            # Phase 2: Update Index via Repository
            await self.tasks.upsert(record)

            # Success! Cleanup: delete the old blob file if the status changed and the file was relocated
            if old_abs_path != new_abs_path and os.path.exists(old_abs_path):
                await asyncio.to_thread(os.remove, old_abs_path)

            return record

        except Exception as e:
            # Phase 3: Rollback
            if os.path.exists(backup_path):
                await asyncio.to_thread(shutil.copy2, backup_path, file_path)
            raise e

    async def move_task_status_atomically(
        self, task_key: str, new_status: str, resolution: str | None = None
    ) -> TaskRecord:
        """Moves a task to a new status with transition validation."""
        current = await self.tasks.get_by_key(task_key)
        if not current:
            raise TaskNotFoundError(f"Task '{task_key}' not found")

        old_status = current.status.lower()
        ns_lower = new_status.lower()

        allowed = VALID_TRANSITIONS.get(old_status, [])
        if old_status in VALID_TRANSITIONS and ns_lower not in allowed:
            if old_status != ns_lower:
                raise ValueError(f"Invalid transition from '{old_status}' to '{new_status}'")

        return await self.update_task_atomically(
            task_key, {"status": new_status, "resolution": resolution}
        )

    async def move_tasks_batch_atomically(
        self, task_keys: list[str], new_status: str, resolution: str | None = None
    ) -> dict:
        """Batch status move: single lock, bulk LanceDB upsert, single auto-unblock pass."""
        from storage.db import TableLockContext

        async with TableLockContext(self.tasks.table.name):
            validated = await self._validate_and_load_tasks(task_keys, new_status, resolution)
            original_paths = {record.key: orig_pp for record, _, orig_pp in validated}
            prepared, backup_paths = await self._backup_and_prepare_updates(
                validated, new_status, resolution
            )
            try:
                await self._commit_index_and_cleanup(prepared, original_paths)
            except Exception:
                await self._rollback(prepared, original_paths, backup_paths)
                raise

            # Phase E — Auto-unblock pass
            completed_keys: set[str] = set(task_keys)
            unblocked = []
            active_tasks = await self.tasks.search(status="open")
            now = datetime.now().isoformat()
            for t in active_tasks:
                if not t.blocked_by:
                    continue
                remaining = [b for b in t.blocked_by if b not in completed_keys]
                if len(remaining) != len(t.blocked_by):
                    t_abs = get_raw_path(self.project_root, t.file_path, ResourceKind.ROOT)
                    t_data = await asyncio.to_thread(read_blob, t_abs)
                    t_data["blocked_by"] = remaining
                    t_data["updated"] = now
                    new_t_blob = await asyncio.to_thread(write_blob, self.project_root, t_data)
                    t.blocked_by = remaining
                    t.file_path = str(new_t_blob.relative_to(self.project_root)).replace("\\", "/")
                    await self.tasks.upsert(t)
                    await asyncio.to_thread(os.remove, t_abs)
                    unblocked.append(t.key)

            return {"completed": list(task_keys), "unblocked": unblocked}

    async def _validate_and_load_tasks(
        self, task_keys: list[str], new_status: str, resolution: str | None,
    ) -> list[tuple[TaskRecord, dict, ProjectPath]]:
        """Phase A -- fail-fast validation of every task before any write happens."""
        validated = []
        for key in task_keys:
            record = await self.tasks.get_by_key(key)
            if not record:
                raise TaskNotFoundError(f"Task '{key}' not found")
            orig_pp = get_path(self.project_root, record.file_path, ResourceKind.ROOT)
            abs_path = get_raw_path(self.project_root, record.file_path, ResourceKind.ROOT)
            full_data = await asyncio.to_thread(read_blob, abs_path)
            StatusChangeValidator(
                full_data, {"status": new_status, "resolution": resolution}
            ).validate()
            validated.append((record, full_data, orig_pp))
        return validated

    async def _backup_and_prepare_updates(
        self, validated: list[tuple[TaskRecord, dict, ProjectPath]],
        new_status: str, resolution: str | None,
    ) -> tuple[list[tuple[str, TaskRecord]], dict[str, ProjectPath]]:
        """Phase B driver -- backs up each original and writes its replacement blob."""
        prepared = []
        backup_paths: dict[str, ProjectPath] = {}
        now = datetime.now().isoformat()
        for record, full_data, orig_pp in validated:
            backup_paths[record.key] = await self._backup_original(record, orig_pp)
            new_record = await self._write_updated_blob(record, full_data, new_status, resolution, now)
            prepared.append((record.key, new_record))
        return prepared, backup_paths

    async def _backup_original(self, record: TaskRecord, orig_pp: ProjectPath) -> ProjectPath:
        """Creates one timestamped backup of the current blob content via ProjectPath."""
        timestamp = datetime.now().strftime(HISTORY_TIMESTAMP_FORMAT)
        backup_rel = os.path.join(NAMESPACE_TASKS, record.file_path, f"{timestamp}.md")
        backup_pp = get_path(self.project_root, backup_rel, ResourceKind.HISTORY)
        if await orig_pp.exists_async():
            await orig_pp.copy_async(backup_pp)
        else:
            abs_path = get_raw_path(self.project_root, record.file_path, ResourceKind.ROOT)
            full_data = await asyncio.to_thread(read_blob, abs_path)
            await backup_pp.write_async(json.dumps(full_data))
        return backup_pp

    async def _write_updated_blob(
        self, record: TaskRecord, full_data: dict, new_status: str,
        resolution: str | None, now: str,
    ) -> TaskRecord:
        """Builds the updated blob content, writes it, and returns the new TaskRecord."""
        updated_data = {**full_data, "status": new_status, "updated": now}
        if resolution:
            updated_data["resolution"] = resolution
        updated_data["key"] = record.key
        updated_data["id"] = record.id
        updated_data["project"] = record.project
        new_blob_path = await asyncio.to_thread(write_blob, self.project_root, updated_data)
        return TaskRecord(
            id=record.id,
            key=record.key,
            title=updated_data.get("title", ""),
            type=updated_data.get("type", "F"),
            status=updated_data.get("status", new_status),
            priority=updated_data.get("priority", "medium"),
            file_path=str(Path(new_blob_path).relative_to(self.project_root)).replace("\\", "/"),
            updated=now,
            project=record.project,
            problem=updated_data.get("problem"),
            solution=updated_data.get("solution"),
            blocked_by=updated_data.get("blocked_by", []),
            where=updated_data.get("where", []),
            comments=updated_data.get("comments"),
            resolution=updated_data.get("resolution"),
        )

    async def _commit_index_and_cleanup(
        self, prepared: list[tuple[str, TaskRecord]], original_paths: dict[str, ProjectPath],
    ) -> None:
        """Phase C -- commits the new index rows, then removes superseded originals."""
        ids = [r.id for _, r in prepared]
        id_list = ", ".join(str(i) for i in ids)
        await asyncio.to_thread(self.tasks.table.delete, f"id IN ({id_list})")
        await asyncio.to_thread(self.tasks.table.add, [r.to_index_row() for _, r in prepared])
        for key, _ in prepared:
            orig_pp = original_paths[key]
            if await orig_pp.exists_async():
                await orig_pp.delete_async()

    async def _rollback(
        self, prepared: list[tuple[str, TaskRecord]], original_paths: dict[str, ProjectPath],
        backup_paths: dict[str, ProjectPath],
    ) -> None:
        """Restores each original blob from its timestamped backup and removes any new
        blob already written, best-effort."""
        for key, new_rec in prepared:
            orig_pp = original_paths.get(key)
            backup_pp = backup_paths.get(key)
            new_pp = get_path(self.project_root, new_rec.file_path, ResourceKind.ROOT)

            if backup_pp is not None and orig_pp is not None and await backup_pp.exists_async():
                content = await backup_pp.read_async()
                await orig_pp.write_async(content)

            if orig_pp is None or new_pp.relative_path != orig_pp.relative_path:
                if await new_pp.exists_async():
                    try:
                        await new_pp.delete_async()
                    except ProjectFileError:
                        pass

