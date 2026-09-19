import pytest

from tools.artifacts import (
    read_artifact_logic,
    read_project_artifact_logic,
    read_project_artifact_logic_async,
    read_project_artifacts_logic,
)
from tools.utils.filesystem_utils import resolve_artifact_project_path
from utils.exceptions import ArtifactNotFoundError

PROJECT = "CoreProject"
DOC = "docs/sample.md"
DOC_TEXT = "line 1\nline 2\nline 3\nline 4\n"


@pytest.fixture
def project_root(tmp_path, monkeypatch):
    monkeypatch.setattr("config.PROJECTS_ROOT", str(tmp_path))
    doc = tmp_path / PROJECT / "artifacts" / "docs" / "sample.md"
    doc.parent.mkdir(parents=True)
    doc.write_bytes(DOC_TEXT.encode("utf-8"))
    return tmp_path


def test_read_project_artifact_logic_lines_mode_returns_requested_slice(project_root):
    project_path = resolve_artifact_project_path(PROJECT, DOC)
    result = read_project_artifact_logic(project_path, mode="lines", start_line=2, end_line=3)
    assert result == "line 2\nline 3"


def test_read_project_artifact_logic_missing_file_raises_artifact_not_found_error(project_root):
    project_path = resolve_artifact_project_path(PROJECT, "docs/missing.md")
    with pytest.raises(ArtifactNotFoundError, match="docs/missing.md"):
        read_project_artifact_logic(project_path, mode="full")


def test_read_artifact_logic_valid_path_delegates_to_core_and_returns_slice(project_root):
    result = read_artifact_logic(PROJECT, DOC, mode="lines", start_line=1, end_line=2)
    assert result == "line 1\nline 2"


def test_read_artifact_logic_traversal_path_raises_artifact_not_found_error(project_root):
    with pytest.raises(ArtifactNotFoundError):
        read_artifact_logic(PROJECT, "../../outside.md", mode="full")


@pytest.mark.asyncio
async def test_read_project_artifact_logic_async_lines_mode_returns_same_slice_as_sync(
    project_root,
):
    project_path = resolve_artifact_project_path(PROJECT, DOC)
    result = await read_project_artifact_logic_async(
        project_path, mode="lines", start_line=3, end_line=4
    )
    assert result == "line 3\nline 4"


def test_read_project_artifacts_logic_existing_path_returns_path_and_content(project_root):
    reads = [{"path": DOC, "mode": "lines", "start_line": 2, "end_line": 2}]
    assert read_project_artifacts_logic(PROJECT, reads) == [{"path": DOC, "content": "line 2"}]


def test_read_project_artifacts_logic_missing_path_returns_error_item_with_not_found_message(
    project_root,
):
    results = read_project_artifacts_logic(PROJECT, [{"path": "docs/nope.md"}])
    assert results == [{"path": "docs/nope.md", "error": "Artifact docs/nope.md not found."}]
