import os
from typing import Any

from config import PROJECTS_ROOT
from utils.exceptions import ProjectNotFoundError


async def semantic_search_tasks_logic(project: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
    """
    [EXPERIMENTAL] Semantic task search via vector embeddings.
    """
    
    project_root = os.path.join(PROJECTS_ROOT, project)
    if not os.path.exists(project_root):
        raise ProjectNotFoundError(f"Project '{project}' not found")
        
    try:
        # 1-2. Generate vector and search in LanceDB via repository
        from storage.uow import UnitOfWork
        uow = UnitOfWork(project_root)
        results = await uow.tasks.semantic_search(query, limit)
        
        # 3. Format result
        return [
            {
                "key": r["record"].key,
                "title": r["record"].title,
                "status": r["record"].status,
                "score": r["distance"]
            }
            for r in results
        ]
    except Exception:
        raise

async def search_artifact_sections_logic(project: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Semantic search by artifact sections (chunks) (ASV-7)."""
    from storage.uow import UnitOfWork
    project_root = os.path.join(PROJECTS_ROOT, project)
    if not os.path.exists(project_root):
        raise ProjectNotFoundError(f"Project '{project}' not found")
    uow = UnitOfWork(project_root)
    return await uow.chunks.semantic_search(query, limit)
