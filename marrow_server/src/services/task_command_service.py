import asyncio
import os
from typing import Any

from config import PROJECTS_ROOT
from domain.responses import TaskUpdateDetail, TaskUpdateResult
from models import TaskInput
from storage.blobs import write_blob
from storage.entities import TaskRecord
from storage.uow import UnitOfWork
from tools.utils.filesystem_utils import get_now_iso
from utils.exceptions import ProjectNotFoundError, ValidationError


async def update_task_logic(
    project: str, task_id: str, updates: dict[str, Any]
) -> TaskUpdateResult:
    """
    Experimental task update tool (Atomic 2PC).
    """

    project_root = os.path.join(PROJECTS_ROOT, project)
    if not os.path.exists(project_root):
        raise ProjectNotFoundError(f"Project '{project}' not found")

    try:
        # Advanced agent: Use UoW with Rollback and Validation
        uow = UnitOfWork(project_root)
        record = await uow.update_task_atomically(task_id, updates)
        return TaskUpdateResult(
            status="success",
            task=TaskUpdateDetail(id=record.key, status=record.status, updated=record.updated),
        )
    except ValueError as ve:
        raise ValidationError(str(ve))


async def complete_tasks_logic(task_ids: list[str], project: str) -> str:
    """
    Batch-close tasks atomically (single lock, bulk LanceDB upsert, auto-unblock).
    """
    if not task_ids:
        return "No task IDs provided."
    project_root = os.path.join(PROJECTS_ROOT, project)
    if not os.path.isdir(project_root):
        raise ProjectNotFoundError(f"Project '{project}' not found")
    uow = UnitOfWork(project_root)
    result = await uow.move_tasks_batch_atomically(
        task_ids, new_status="closed", resolution="Closed via complete_tasks batch tool."
    )
    completed = result["completed"]
    unblocked = result["unblocked"]
    summary = f"Completed {len(completed)} task(s): {', '.join(completed)}."
    if unblocked:
        summary += f" Unblocked {len(unblocked)} task(s): {', '.join(unblocked)}."
    return summary


async def add_tasks_logic(tasks_input: list[TaskInput], project: str) -> str:
    """
    Experimental tool for adding tasks via Decoupled Storage.
    Uses TaskInput from models.py.
    """

    project_root = os.path.join(PROJECTS_ROOT, project)
    if not os.path.exists(project_root):
        raise ProjectNotFoundError(f"Project '{project}' not found")

    from storage.db import get_table_lock

    async with get_table_lock("task_index"):
        # 0. Title uniqueness check (B19: Duplicates forbidden)
        from tools.validators.backlog_validation import validate_task_title_unique

        uow = UnitOfWork(project_root)
        # Fetch data as list of dicts for legacy compatible validation
        existing_tasks = [{"title": r.title} for r in await uow.tasks.search()]

        # 1. Fetch next free ID directly from LanceDB (BS-2.8: Autoincrement)
        next_id = await uow.tasks.get_next_id()

        now = get_now_iso()

        for ti in tasks_input:
            # B19: Title uniqueness check
            validate_task_title_unique(ti.title, existing_tasks, project)

            t_id = f"{ti.type}{next_id}"
            blocked_by = ti.blocked_by if ti.blocked_by else []
            if isinstance(blocked_by, str):
                blocked_by = [blocked_by]

            # Prepare blob data
            blob_data = ti.model_dump()
            blob_data["key"] = t_id
            blob_data["id"] = next_id
            blob_data["project"] = project
            blob_data["updated"] = now
            blob_data["status"] = ti.status  # Temporary: extra logic for blocked might go here

            # --- Writing Blob (Phase 1) ---
            new_blob_path = await asyncio.to_thread(write_blob, project_root, blob_data)

            # --- Updating Index (Phase 2) ---
            record = TaskRecord(
                id=next_id,
                key=t_id,
                title=blob_data["title"],
                type=blob_data["type"],
                status=blob_data["status"],
                priority=blob_data["priority"],
                file_path=os.path.relpath(new_blob_path, project_root).replace("\\", "/"),
                updated=blob_data["updated"],
                project=project,
                problem=blob_data.get("problem"),
                solution=blob_data.get("solution"),
                blocked_by=blocked_by,
                where=blob_data.get("where", []),
            )
            await uow.tasks.upsert(record)

            # Add to list for same-batch check
            existing_tasks.append({"title": ti.title})

            next_id += 1

        return f"Successfully added {len(tasks_input)} task(s) to project {project} (Decoupled). Next ID: {next_id}"
