from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from domain.responses import EmptyArtifactsResult
from models import ReadRequest, WriteRequest
from operations import artifacts as ops
from utils.exceptions import ProjectNotFoundError


async def test_read_project_artifacts_extra_fields_are_flattened_into_request_dict():
    req = ReadRequest(path="a.md", mode="full", extra_fields={"custom": 1})
    with patch("operations.artifacts.read_project_artifacts_logic", return_value=[]) as logic:
        await ops.read_project_artifacts("P", [req])
    sent = logic.call_args.args[1][0]
    assert sent["custom"] == 1 and sent["path"] == "a.md" and "extra_fields" not in sent


async def test_save_project_artifacts_sets_explicit_fields_from_model_fields_set():
    req = WriteRequest(path="a.md", content="x")
    done = MagicMock()
    done.model_dump.return_value = {"path": "a.md", "status": "ok"}
    with patch(
        "operations.artifacts.save_project_artifacts_logic", new=AsyncMock(return_value=[done])
    ) as logic:
        assert await ops.save_project_artifacts("P", [req]) == [{"path": "a.md", "status": "ok"}]
    sent = logic.await_args.args[1][0]
    assert sent["_explicit_fields"] == {"path", "content"} and "extra_fields" not in sent


async def test_semantic_search_empty_result_object_returns_single_dump():
    empty = MagicMock(spec=EmptyArtifactsResult)
    empty.model_dump.return_value = {"message": "m"}
    with patch(
        "operations.artifacts.search_artifact_sections_logic", new=AsyncMock(return_value=empty)
    ):
        assert await ops.semantic_search("P", "q") == {"message": "m"}


async def test_semantic_search_list_results_return_model_dumps():
    row = MagicMock()
    row.model_dump.return_value = {"path": "a.md"}
    with patch(
        "operations.artifacts.search_artifact_sections_logic",
        new=AsyncMock(return_value=[row]),
    ) as logic:
        assert await ops.semantic_search("P", "q", 7, ["docs"]) == [{"path": "a.md"}]
    logic.assert_awaited_once_with("P", "q", 7, scopes=["docs"])


async def test_list_project_artifacts_passes_recursive_keyword():
    with patch("operations.artifacts.list_artifacts_logic", return_value=[]) as logic:
        assert await ops.list_project_artifacts("P", "docs", True) == []
    logic.assert_called_once_with("P", "docs", recursive=True)


async def test_move_project_artifact_passes_arguments():
    with patch(
        "operations.artifacts.move_project_artifact_logic", new=AsyncMock(return_value="moved")
    ) as logic:
        assert await ops.move_project_artifact("P", "a.md", "b.md") == "moved"
    logic.assert_awaited_once_with("P", "a.md", "b.md")


async def test_delete_project_artifact_passes_arguments():
    with patch(
        "operations.artifacts.delete_project_artifact_logic",
        new=AsyncMock(return_value="deleted"),
    ) as logic:
        assert await ops.delete_project_artifact("P", "a.md") == "deleted"
    logic.assert_awaited_once_with("P", "a.md")


async def test_search_project_artifacts_passes_arguments():
    with patch(
        "operations.artifacts.search_project_artifacts_logic",
        new=AsyncMock(return_value=[{"path": "a.md"}]),
    ) as logic:
        assert await ops.search_project_artifacts("P", "q") == [{"path": "a.md"}]
    logic.assert_awaited_once_with("P", "q")


async def test_get_project_artifact_outline_passes_arguments():
    with patch(
        "operations.artifacts.get_project_artifact_outline_logic", return_value="toc"
    ) as logic:
        assert await ops.get_project_artifact_outline("P", "a.md") == "toc"
    logic.assert_called_once_with("P", "a.md")


async def test_list_artifact_history_passes_arguments():
    with patch("operations.artifacts.list_artifact_history_logic", return_value=[]) as logic:
        assert await ops.list_artifact_history("P", "a.md") == []
    logic.assert_called_once_with("P", "a.md")


async def test_restore_project_artifact_passes_arguments():
    with patch(
        "operations.artifacts.restore_project_artifact_logic", return_value="restored"
    ) as logic:
        assert await ops.restore_project_artifact("P", "a.md", "b1") == "restored"
    logic.assert_called_once_with("P", "a.md", "b1")


async def test_delete_project_artifact_domain_error_propagates():
    with patch(
        "operations.artifacts.delete_project_artifact_logic",
        new=AsyncMock(side_effect=ProjectNotFoundError("x")),
    ):
        with pytest.raises(ProjectNotFoundError):
            await ops.delete_project_artifact("P", "a.md")
