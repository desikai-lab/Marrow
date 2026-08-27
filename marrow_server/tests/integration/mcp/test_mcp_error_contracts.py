from typing import Any

import pytest
from models import TaskInput
from services.task_command_service import add_tasks_logic
from utils.error_middleware import mcp_error_handler
from utils.exceptions import BaseBacklogError

pytestmark = pytest.mark.integration


@mcp_error_handler
async def _add_tasks_tool(project: str, tasks: list[TaskInput]) -> str | dict[str, Any]:
    return await add_tasks_logic(tasks, project)


@mcp_error_handler
async def _raises_domain_error(project: str, tasks: list[TaskInput]) -> str | dict[str, Any]:
    raise BaseBacklogError("Forced domain error for test")


@mcp_error_handler
async def _raises_system_error(project: str, tasks: list[TaskInput]) -> str | dict[str, Any]:
    raise RuntimeError("Forced system error for test")


async def test_mcp_error_handler_success_result_passes_through_unchanged(tmp_project):
    task = TaskInput(
        title="CONTRACT-TEST: Happy Path Task",
        type="TD",
        priority="medium",
        problem="Test problem",
        solution="Test solution",
    )
    result = await _add_tasks_tool(tmp_project, [task])
    assert isinstance(result, dict)
    assert len(result["created_task_ids"]) == 1
    assert result["created_task_ids"][0].startswith("TD")
    assert "Successfully added" in result["message"]


async def test_mcp_error_handler_domain_error_returns_structured_error_dict(tmp_project):
    result = await _raises_domain_error(tmp_project, [])
    assert isinstance(result, dict)
    assert result["status"] == "error"
    assert result["error_type"] == "BaseBacklogError"
    assert "Forced domain error for test" in result["message"]


async def test_mcp_error_handler_system_error_returns_system_error_dict(tmp_project):
    result = await _raises_system_error(tmp_project, [])
    assert isinstance(result, dict)
    assert result["status"] == "error"
    assert result["error_type"] == "SystemError"
    assert "SystemError" in result["error_type"]


async def test_mcp_error_handler_real_domain_error_duplicate_task_returns_error_dict(tmp_project):
    task = TaskInput(
        title="CONTRACT-TEST: Duplicate Task",
        type="TD",
        priority="low",
        problem="Test duplicate problem",
        solution="Test duplicate solution",
    )
    # First write succeeds
    result1 = await _add_tasks_tool(tmp_project, [task])
    assert isinstance(result1, dict)

    # Second write triggers duplicate check inside add_tasks_logic, raising ValidationError.
    # Decorator should catch it and return structured dict instead of raising.
    result2 = await _add_tasks_tool(tmp_project, [task])
    assert isinstance(result2, dict)
    assert result2["status"] == "error"
    assert result2["error_type"] == "ValidationError"
    assert "duplicate" in result2["message"].lower()
