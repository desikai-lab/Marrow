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


async def test_read_project_artifacts_logic_upperCaseVariant_returnsNotFoundConsistently(
    tmp_project,
):
    path = "integration/casing_test.md"
    await save_project_artifacts_logic(
        tmp_project,
        [{"path": path, "mode": "replace_file", "content": "Normalized read test."}],
    )

    results = read_project_artifacts_logic(
        tmp_project,
        [{"path": path}, {"path": "Integration/Casing_Test.md"}],
    )
    assert len(results) == 2
    # Exact-case request still succeeds.
    exact = results[0]
    assert "error" not in exact, f"Exact-case read unexpectedly failed: {exact.get('error')}"
    assert exact["content"] == "Normalized read test."
    # Mismatched-case request is treated as not-found, same shape as
    # test_read_project_artifacts_logic_nonexistent_path_returns_error_item --
    # no silent case-folding (ADR-49). NOTE: this branch only fails on a
    # case-sensitive filesystem (CI/Linux) -- on Windows/NTFS dev boxes the OS
    # itself resolves the case difference before this code runs, so it will not
    # fail there. This is the accepted trade-off in ADR-49 Consequences, not a
    # flaky test -- do not "fix" this back into a directory walk.
    import sys

    if sys.platform != "win32":
        mismatched = results[1] if isinstance(results[1], dict) else results[1].model_dump()
        assert "error" in mismatched or mismatched.get("status") == "error"
