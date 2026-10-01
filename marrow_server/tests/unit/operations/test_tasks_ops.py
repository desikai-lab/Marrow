from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from operations import tasks as ops
from utils.exceptions import ProjectNotFoundError


def _model(dumped):
    m = MagicMock()
    m.model_dump.return_value = dumped
    return m


async def test_add_tasks_valid_input_calls_logic_with_tasks_then_project():
    with patch("operations.tasks.add_tasks_logic", new=AsyncMock(return_value="ok")) as logic:
        assert await ops.add_tasks("P", ["t"]) == "ok"
    logic.assert_awaited_once_with(["t"], "P")


async def test_search_tasks_defaults_pass_open_and_return_model_dumps():
    rows = AsyncMock(return_value=[_model({"task_id": "F1"})])
    with patch("operations.tasks.search_tasks_logic", new=rows):
        assert await ops.search_tasks("P") == [{"task_id": "F1"}]
    rows.assert_awaited_once_with("P", "open", None, None)


async def test_get_task_details_returns_model_dump():
    with patch(
        "operations.tasks.get_task_details_logic", new=AsyncMock(return_value=_model({"a": 1}))
    ):
        assert await ops.get_task_details("P", "F1") == {"a": 1}


async def test_update_task_passes_arguments_and_returns_model_dump():
    logic = AsyncMock(return_value=_model({"priority": "high"}))
    with patch("operations.tasks.update_task_logic", new=logic):
        assert await ops.update_task("P", "F1", {"priority": "high"}) == {"priority": "high"}
    logic.assert_awaited_once_with("P", "F1", {"priority": "high"})


async def test_complete_tasks_calls_logic_with_ids_then_project():
    with patch(
        "operations.tasks.complete_tasks_logic", new=AsyncMock(return_value="done")
    ) as logic:
        assert await ops.complete_tasks("P", ["F1"]) == "done"
    logic.assert_awaited_once_with(["F1"], "P")


async def test_search_tasks_domain_error_propagates_unchanged():
    with patch(
        "operations.tasks.search_tasks_logic", new=AsyncMock(side_effect=ProjectNotFoundError("x"))
    ):
        with pytest.raises(ProjectNotFoundError):
            await ops.search_tasks("P")
