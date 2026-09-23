import pytest

from services.artifact_command_service import save_project_artifacts_logic

pytestmark = pytest.mark.integration


async def test_save_project_artifacts_logic_new_file_returns_success_status(tmp_project):
    updates = [
        {
            "path": "integration/test_artifact.md",
            "mode": "replace_file",
            "content": "# Test Artifact\n\nCreated by integration tests.",
        }
    ]
    results = await save_project_artifacts_logic(tmp_project, updates)
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].status == "success"
    assert results[0].path == "integration/test_artifact.md"


async def test_save_project_artifacts_logic_invalid_mode_returns_error_status(tmp_project):
    updates = [
        {
            "path": "integration/bad_mode.md",
            "mode": "__invalid_mode__",
            "content": "should not be written",
        }
    ]
    results = await save_project_artifacts_logic(tmp_project, updates)
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].status == "error"
