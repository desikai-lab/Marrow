import os
from typing import List, Dict, Any, Optional
from config import PROJECTS_ROOT, DECOUPLED_STORAGE_ENABLED
from storage.repositories import TaskRepository
from storage.blobs import read_blob
from utils.exceptions import (
    StorageDisabledError, ProjectNotFoundError, TaskNotFoundError, ArtifactNotFoundError
)

async def search_tasks_logic(
    project: str,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Experimental task search tool via LanceDB.
    Works only when DECOUPLED_STORAGE_ENABLED=true.
    """
    if not DECOUPLED_STORAGE_ENABLED:
        raise StorageDisabledError("Decoupled storage is disabled. Set DECOUPLED_STORAGE_ENABLED=true in .env")

    project_root = os.path.join(PROJECTS_ROOT, project)
    if not os.path.exists(project_root):
        raise ProjectNotFoundError(f"Project '{project}' not found")

    repo = TaskRepository(project_root)
    # Invoke search in LanceDB
    # Note: 'type' argument renamed to avoid conflict with builtin
    results = await repo.search(
        status=status,
        priority=priority,
        type=type,
        project=project
    )
    
    # Format for response (analogous to legacy search_tasks)
    return [
        {
            "id": r.key, 
            "title": r.title,
            "status": r.status,
            "priority": r.priority,
            "project": r.project
        }
        for r in results
    ]

async def get_task_details_logic(project: str, task_id: str) -> Dict[str, Any]:
    """
    Experimental tool for retrieving task details (LanceDB + Blobs).
    Returns full task data, including problem and solution.
    """
    if not DECOUPLED_STORAGE_ENABLED:
        raise StorageDisabledError("Decoupled storage is disabled")

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
            details={"task_id": task_id, "file_path": index_entry.file_path}
        )
        
    try:
        import asyncio
        full_data = await asyncio.to_thread(read_blob, blob_path)
        full_data["key"] = index_entry.key
        full_data["id"] = index_entry.id
        return full_data
    except Exception:
        raise
