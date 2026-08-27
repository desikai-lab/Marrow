import pytest
from models import TaskInput
from services.task_command_service import add_tasks_logic
from utils.exceptions import ValidationError

pytestmark = pytest.mark.integration


async def test_add_tasks_logic_single_task_returns_success_message(tmp_project):
    task = TaskInput(
        title="INT-TEST: Alpha Task",
        type="TD",
        priority="medium",
        problem="Some problem details",
        solution="Some solution details",
    )
    result = await add_tasks_logic([task], tmp_project)
    assert isinstance(result, dict)
    assert len(result["created_task_ids"]) == 1
    assert result["created_task_ids"][0].startswith("TD")
    assert result["next_available_id"] >= 2
    assert "Successfully added 1 task(s)" in result["message"]


async def test_add_tasks_logic_batch_tasks_returns_all_created_ids(tmp_project):
    tasks = [
        TaskInput(title="INT-TEST: Batch Task 1", type="F", priority="low", problem="P1", solution="S1"),
        TaskInput(title="INT-TEST: Batch Task 2", type="B", priority="high", problem="P2", solution="S2"),
    ]
    result = await add_tasks_logic(tasks, tmp_project)
    assert isinstance(result, dict)
    assert len(result["created_task_ids"]) == 2
    assert result["created_task_ids"][0].startswith("F")
    assert result["created_task_ids"][1].startswith("B")
    assert result["next_available_id"] >= 3
    assert "Successfully added 2 task(s)" in result["message"]


async def test_add_tasks_logic_duplicate_title_raises_ValidationError(tmp_project):
    task = TaskInput(
        title="INT-TEST: Duplicate Task",
        type="TD",
        priority="low",
        problem="Some problem details",
        solution="Some solution details",
    )
    await add_tasks_logic([task], tmp_project)  # first add succeeds
    with pytest.raises(ValidationError):
        await add_tasks_logic([task], tmp_project)  # duplicate → raises


async def test_add_tasks_logic_unknown_project_raises_ProjectNotFoundError():
    from utils.exceptions import ProjectNotFoundError

    task = TaskInput(
        title="Orphan Task",
        type="TD",
        priority="low",
        problem="Some problem details",
        solution="Some solution details",
    )
    with pytest.raises(ProjectNotFoundError):
        await add_tasks_logic([task], "__nonexistent_project__")
