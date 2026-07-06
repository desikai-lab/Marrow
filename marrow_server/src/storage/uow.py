import asyncio
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from domain.validators.status_change import StatusChangeValidator
from utils.exceptions import DomainProtectionError, TaskNotFoundError

from storage.blobs import read_blob, write_blob
from storage.entities import TaskRecord
from storage.repositories import ArtifactChunkRepository, ArtifactRepository, TaskRepository

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

        # Create a Backup for Rollback
        history_dir = Path(self.project_root) / ".history" / task_key
        history_dir.mkdir(parents=True, exist_ok=True)
        backup_path = history_dir / f"{task_key}.md.bak"

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

        # key → original absolute path (for rollback)
        original_paths: dict[str, str] = {}

        async with TableLockContext(self.tasks.table.name):
            # Phase A — Validate all (fail-fast)
            validated = []  # list of (record, full_data, abs_file_path)
            for key in task_keys:
                record = await self.tasks.get_by_key(key)
                if not record:
                    raise TaskNotFoundError(f"Task '{key}' not found")
                abs_path = os.path.join(self.project_root, record.file_path)
                full_data = await asyncio.to_thread(read_blob, abs_path)
                StatusChangeValidator(
                    full_data, {"status": new_status, "resolution": resolution}
                ).validate()
                validated.append((record, full_data, abs_path))
                original_paths[key] = abs_path

            # Phase B — Backup + write new blobs
            prepared = []  # list of (old_abs_path, new_record)
            now = datetime.now().isoformat()
            for record, full_data, abs_path in validated:
                # backup
                history_dir = Path(self.project_root) / ".history" / record.key
                history_dir.mkdir(parents=True, exist_ok=True)
                backup_path = history_dir / f"{record.key}.md.bak"
                await asyncio.to_thread(shutil.copy2, abs_path, backup_path)
                # build updated data
                updated_data = {**full_data, "status": new_status, "updated": now}
                if resolution:
                    updated_data["resolution"] = resolution
                updated_data["key"] = record.key
                updated_data["id"] = record.id
                updated_data["project"] = record.project
                # write new blob
                new_blob_path = await asyncio.to_thread(write_blob, self.project_root, updated_data)
                new_record = TaskRecord(
                    id=record.id,
                    key=record.key,
                    title=updated_data.get("title", ""),
                    type=updated_data.get("type", "F"),
                    status=updated_data.get("status", new_status),
                    priority=updated_data.get("priority", "medium"),
                    file_path=str(Path(new_blob_path).relative_to(self.project_root)).replace(
                        "\\", "/"
                    ),
                    updated=now,
                    project=record.project,
                    problem=updated_data.get("problem"),
                    solution=updated_data.get("solution"),
                    blocked_by=updated_data.get("blocked_by", []),
                    where=updated_data.get("where", []),
                    comments=updated_data.get("comments"),
                    resolution=updated_data.get("resolution"),
                )
                prepared.append((str(Path(abs_path).absolute()), new_record))

            try:
                # Phase C — Bulk LanceDB upsert
                ids = [r.id for _, r in prepared]
                id_list = ", ".join(str(i) for i in ids)
                await asyncio.to_thread(self.tasks.table.delete, f"id IN ({id_list})")
                await asyncio.to_thread(
                    self.tasks.table.add, [r.to_index_row() for _, r in prepared]
                )

                # Phase D — Delete old blobs
                for old_abs_path, _ in prepared:
                    if os.path.exists(old_abs_path):
                        await asyncio.to_thread(os.remove, old_abs_path)

            except Exception:
                # Rollback: restore backed-up blobs for all prepared entries
                for _, new_rec in prepared:
                    new_abs = os.path.join(self.project_root, new_rec.file_path)
                    key = new_rec.key
                    bak = Path(self.project_root) / ".history" / key / f"{key}.md.bak"
                    orig = original_paths.get(key)
                    if bak.exists() and orig:
                        await asyncio.to_thread(shutil.copy2, str(bak), orig)
                    if os.path.exists(new_abs) and new_abs != orig:
                        try:
                            await asyncio.to_thread(os.remove, new_abs)
                        except OSError:
                            pass
                raise

            # Phase E — Auto-unblock pass
            completed_keys: set[str] = set(task_keys)
            unblocked = []
            active_tasks = await self.tasks.search(status="open")
            for t in active_tasks:
                if not t.blocked_by:
                    continue
                remaining = [b for b in t.blocked_by if b not in completed_keys]
                if len(remaining) != len(t.blocked_by):
                    t_abs = os.path.join(self.project_root, t.file_path)
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
