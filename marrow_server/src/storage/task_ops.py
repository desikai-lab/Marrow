from typing import TYPE_CHECKING
from storage.repositories.task_repository import TaskRepository

if TYPE_CHECKING:
    from storage.entities import TaskRecord

def upsert_task(project_root: str, task: 'TaskRecord'):
    """Consistent task upsert into the index via repository."""
    repo = TaskRepository(project_root)
    repo.upsert(task)
