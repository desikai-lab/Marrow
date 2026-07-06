from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from services.skeleton_command_service import SkeletonCommandService
from storage.repositories.skeleton_repository import SkeletonRepository


@pytest.fixture
def service():
    return SkeletonCommandService()


@pytest.mark.asyncio
@patch("services.skeleton_command_service.SkeletonRepository")
@patch("services.skeleton_command_service.os.path.join")
@patch("services.skeleton_command_service.PROJECTS_ROOT", "/mock/projects")
async def test_delete_skeleton_command_service_delegates_to_repository(
    mock_join, mock_repo_class, service
):
    mock_repo = MagicMock(spec=SkeletonRepository)
    mock_repo.delete_file_chunks = AsyncMock(return_value=1)
    mock_repo_class.return_value = mock_repo
    mock_join.return_value = "/mock/projects/test_proj"

    await service.delete("foo.py", "test_proj")

    mock_repo_class.assert_called_once_with("/mock/projects/test_proj")
    mock_repo.delete_file_chunks.assert_called_once()


@pytest.mark.asyncio
@patch("storage.repositories.skeleton_repository.get_skeleton_table")
async def test_delete_file_chunks_existing_path_removes_correct_records(mock_get_table):
    mock_table = MagicMock()
    mock_get_table.return_value = mock_table
    repo = SkeletonRepository("/mock/projects/test_proj")

    # Mock search chain for count
    mock_table.search.return_value.where.return_value.limit.return_value.to_list.return_value = [
        1,
        2,
        3,
    ]

    count = await repo.delete_file_chunks("foo.py", "test_proj")

    assert count == 3
    # Check that delete was called with the correct predicate
    mock_table.delete.assert_called_once_with("path = 'foo.py' AND project = 'test_proj'")
