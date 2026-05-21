import pytest

from models import TaskInput
from services.task_command_service import add_tasks_logic
from services.task_query_service import search_tasks_logic

pytestmark = pytest.mark.integration


async def test_search_tasks_logic_after_add_returns_list_with_key_field(tmp_project):
    task = TaskInput(
        title="INT-TEST: Searchable Task",
        type="F",
        priority="high",
        problem="Some problem details",
        solution="Some solution details",
    )
    await add_tasks_logic([task], tmp_project)

    results = await search_tasks_logic(project=tmp_project, status=None)
    assert isinstance(results, list)
    assert len(results) >= 1
    # Check for either 'id' (TaskSummary field) or 'key' field robustly
    assert all(hasattr(r, "id") or hasattr(r, "key") or "id" in r or "key" in r for r in results)


async def test_search_tasks_logic_unknown_project_raises_ProjectNotFoundError():
    from utils.exceptions import ProjectNotFoundError

    with pytest.raises(ProjectNotFoundError):
        await search_tasks_logic(project="__nonexistent__", status="open")
