from typing import Any

from models import TaskInput
from services.task_command_service import add_tasks_logic, complete_tasks_logic, update_task_logic
from services.task_query_service import get_task_details_logic, search_tasks_logic


async def add_tasks(project: str, tasks: list[TaskInput]) -> str | dict[str, Any]:
    return await add_tasks_logic(tasks, project)


async def search_tasks(
    project: str,
    status: str | None = "open",
    priority: str | None = None,
    type: str | None = None,
) -> list[Any]:
    results = await search_tasks_logic(project, status, priority, type)
    return [r.model_dump() for r in results]


async def get_task_details(project: str, task_id: str) -> Any:
    return (await get_task_details_logic(project, task_id)).model_dump()


async def update_task(project: str, task_id: str, updates: dict[str, Any]) -> Any:
    return (await update_task_logic(project, task_id, updates)).model_dump()


async def complete_tasks(project: str, task_ids: list[str]) -> str | dict[str, Any]:
    return await complete_tasks_logic(task_ids, project)
