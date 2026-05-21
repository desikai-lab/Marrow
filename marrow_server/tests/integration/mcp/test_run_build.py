import pytest

from tools.builds import run_project_build_logic

pytestmark = pytest.mark.integration


async def test_run_project_build_logic_valid_manifest_returns_BuildResult(tmp_build_manifest):
    project, build_name = tmp_build_manifest
    result = run_project_build_logic(project=project, build_name=build_name)
    # BuildResult has a 'success' bool field
    assert result.success is True


async def test_run_project_build_logic_missing_manifest_returns_failure(tmp_project):
    result = run_project_build_logic(project=tmp_project, build_name="__nonexistent_build__")
    assert result.success is False
    assert result.error is not None
    assert "not found" in result.error.lower()
