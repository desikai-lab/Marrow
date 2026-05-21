import pytest

from services.artifact_command_service import save_project_artifacts_logic
from tools import read_project_artifacts_logic

pytestmark = pytest.mark.integration


async def test_read_project_artifacts_logic_existing_path_returns_content(tmp_project):
    # Arrange: write a known artifact
    path = "integration/readable_artifact.md"
    await save_project_artifacts_logic(
        tmp_project,
        [{"path": path, "mode": "replace_file", "content": "# Readable\n\nContent here."}],
    )
    # Act
    reads = [{"path": path}]
    results = read_project_artifacts_logic(tmp_project, reads)
    # Assert
    assert isinstance(results, list)
    assert len(results) == 1
    item = results[0]
    assert "content" in item or hasattr(item, "content")


async def test_read_project_artifacts_logic_nonexistent_path_returns_error_item(tmp_project):
    reads = [{"path": "integration/__does_not_exist__.md"}]
    results = read_project_artifacts_logic(tmp_project, reads)
    assert isinstance(results, list)
    assert len(results) == 1
    item = results[0] if isinstance(results[0], dict) else results[0].model_dump()
    assert "error" in item or item.get("status") == "error"
