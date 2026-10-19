from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from models import TaskInput
from operations import tasks as tasks_ops
from pydantic import Field
from utils.error_middleware import mcp_error_handler


def use_task_tools(mcp: FastMCP) -> None:
    """Register the task tools on `mcp`."""

    @mcp.tool()
    @mcp_error_handler
    async def add_tasks(
        project: Annotated[str, Field(description="Project name (e.g. 'YourProject', 'MCP')")],
        tasks: Annotated[list[TaskInput], Field(description="List of new tasks")],
    ) -> str | dict[str, Any]:
        """[TASK TOOLS] Adds a list of tasks to the project backlog."""
        return await tasks_ops.add_tasks(project, tasks)

    @mcp.tool()
    @mcp_error_handler
    async def search_tasks(
        project: Annotated[str, Field(description="Project name")],
        status: Annotated[str | None, Field(description="Status filter")] = "open",
        priority: Annotated[str | None, Field(description="Priority filter")] = None,
        type: Annotated[str | None, Field(description="Type filter")] = None,
    ) -> list[Any]:
        """[TASK TOOLS] Queries the task backlog in LanceDB with optional filters and returns
        matching task summaries ranked by creation order.

        All parameters are optional filters — omit to retrieve all tasks with default status.
        Default status filter is 'open'; pass status=None to retrieve tasks of all statuses.
        Do NOT call get_task_details on every result — use this tool for status checks and
        task selection, then call get_task_details on the single selected task for full content.

        Allowed `status` values:    open | in_progress | blocked | done | None (no filter)
        Allowed `priority` values:  low | medium | high | critical | None (no filter)
        Allowed `type` values:      feature | bug | task | td | None (no filter)

        Returns: list of task summary objects — each with task_id, title, status, priority,
                 type, and blocked_by. Full problem/solution content is excluded; call
                 get_task_details for that.
        Raises:  404 if project is not found.
        """
        return await tasks_ops.search_tasks(project, status, priority, type)

    @mcp.tool()
    @mcp_error_handler
    async def get_task_details(
        project: Annotated[str, Field(description="Project name")],
        task_id: Annotated[str, Field(description="Task ID")],
    ) -> Any:
        """[TASK TOOLS] Returns full task details."""
        return await tasks_ops.get_task_details(project, task_id)

    @mcp.tool()
    @mcp_error_handler
    async def update_task(
        project: Annotated[str, Field(description="Project name")],
        task_id: Annotated[str, Field(description="Task ID")],
        updates: Annotated[dict[str, Any], Field(description="Updates dict")],
    ) -> Any:
        """[TASK TOOLS] Partially updates mutable fields on an existing task (status, priority,
        title, solution, etc.) using a merge strategy — only keys present in `updates` are
        changed; all other fields remain intact. Use this for in-progress changes (e.g.
        updating priority or editing the solution).

        Do NOT use to close a task — call complete_tasks instead, which atomically closes
        and auto-unblocks dependents.
        Do NOT use to create tasks — call add_tasks instead.

        Allowed `updates` keys:
          status        : open | in_progress | blocked | done
          priority      : low | medium | high | critical
          title         : str
          problem       : str
          solution      : str
          blocked_by    : list[task_id]

        Returns: updated task object with all current field values.
        Raises:  404 if task_id not found in project.
        """
        return await tasks_ops.update_task(project, task_id, updates)

    @mcp.tool()
    @mcp_error_handler
    async def complete_tasks(
        project: Annotated[str, Field(description="Project name")],
        task_ids: Annotated[
            list[str],
            Field(description="List of task keys to complete, e.g. ['TD4000078', 'TD4000080']"),
        ],
    ) -> str | dict[str, Any]:
        """[TASK TOOLS] Atomically closes one or more tasks and auto-unblocks dependents."""
        return await tasks_ops.complete_tasks(project, task_ids)
