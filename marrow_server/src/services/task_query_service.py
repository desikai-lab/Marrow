import os

from config import PROJECTS_ROOT
from domain.responses import TaskDetailResult, TaskSummary
from storage.blobs import read_blob
from storage.repositories import TaskRepository
from utils.exceptions import (
    ArtifactNotFoundError,
    ProjectNotFoundError,
    TaskNotFoundError,
)


async def search_tasks_logic(
    project: str, status: str | None = None, priority: str | None = None, type: str | None = None
) -> list[TaskSummary]:
    """
    Experimental task search tool via LanceDB.
    """

    project_root = os.path.join(PROJECTS_ROOT, project)
    if not os.path.exists(project_root):
        raise ProjectNotFoundError(f"Project '{project}' not found")

    repo = TaskRepository(project_root)
    # Invoke search in LanceDB
    # Note: 'type' argument renamed to avoid conflict with builtin
    results = await repo.search(status=status, priority=priority, type=type, project=project)

    # Format for response (analogous to legacy search_tasks)
    return [
        TaskSummary(
            id=r.key,
            title=r.title,
            status=r.status,
            priority=r.priority,
            project=r.project,
        )
        for r in results
    ]


async def get_task_details_logic(project: str, task_id: str) -> TaskDetailResult:
    """
    Experimental tool for retrieving task details (LanceDB + Blobs).
    Returns full task data, including problem and solution.
    """

    project_root = os.path.join(PROJECTS_ROOT, project)
    if not os.path.exists(project_root):
        raise ProjectNotFoundError(f"Project '{project}' not found")

    # 1. Search for file path in the index
    repo = TaskRepository(project_root)
    index_entry = await repo.get_by_key(task_id)
    if not index_entry:
        raise TaskNotFoundError(f"Task '{task_id}' not found in LanceDB index")

    # 2. Read physical blob
    blob_path = os.path.join(project_root, index_entry.file_path)
    if not os.path.exists(blob_path):
        raise ArtifactNotFoundError(
            f"Index points to missing file '{index_entry.file_path}'",
            details={"task_id": task_id, "file_path": index_entry.file_path},
        )

    try:
        import asyncio

        full_data = await asyncio.to_thread(read_blob, blob_path)
        full_data["key"] = index_entry.key
        full_data["id"] = index_entry.id
        return TaskDetailResult(**full_data)
    except Exception:
        raise
