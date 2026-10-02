from fastapi import APIRouter, Request
from operations import tasks as ops

from transport.rest.envelope import ok
from transport.rest.schemas import AddTasksBody, CompleteTasksBody, UpdateTaskBody

router = APIRouter(tags=["tasks"])


@router.get("/tasks")
async def search_tasks(
    request: Request,
    project: str,
    status: str | None = "open",
    priority: str | None = None,
    type: str | None = None,
):
    status_filter = None if status == "all" else status
    return ok(request, await ops.search_tasks(project, status_filter, priority, type))


@router.post("/tasks")
async def add_tasks(request: Request, project: str, body: AddTasksBody):
    return ok(request, await ops.add_tasks(project, body.tasks))


@router.post("/tasks/complete")
async def complete_tasks(request: Request, project: str, body: CompleteTasksBody):
    return ok(request, await ops.complete_tasks(project, body.task_ids))


@router.get("/tasks/{task_id}")
async def get_task_details(request: Request, project: str, task_id: str):
    return ok(request, await ops.get_task_details(project, task_id))


@router.patch("/tasks/{task_id}")
async def update_task(request: Request, project: str, task_id: str, body: UpdateTaskBody):
    return ok(request, await ops.update_task(project, task_id, body.updates))
