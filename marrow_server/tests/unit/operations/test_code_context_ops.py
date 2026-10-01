from unittest.mock import AsyncMock, MagicMock, patch

from operations import code_intel, context


async def test_view_file_source_delegates_to_logic_with_positional_args():
    with patch(
        "operations.code_intel.view_file_source_logic", return_value="# File: a.py"
    ) as logic:
        assert await code_intel.view_file_source("P", "a.py", 1, 2) == "# File: a.py"
    logic.assert_called_once_with("P", "a.py", 1, 2)


async def test_get_project_map_returns_model_dump_with_keyword_args():
    model = MagicMock()
    model.model_dump.return_value = {"tree": {}}
    logic = AsyncMock(return_value=model)
    with patch("operations.code_intel.get_project_map_logic", new=logic):
        assert await code_intel.get_project_map("P", 3, True) == {"tree": {}}
    logic.assert_awaited_once_with("P", depth=3, include_tests=True)


async def test_get_session_context_passes_start_role_to_logic():
    with patch("operations.context.get_session_context_logic", return_value="bundle") as logic:
        assert await context.get_session_context("P", "planning") == "bundle"
    logic.assert_called_once_with("P", "planning")


async def test_search_code_skeletons_passes_keyword_args_and_returns_dumps():
    row = MagicMock()
    row.model_dump.return_value = {"path": "a.py"}
    logic = AsyncMock(return_value=[row])
    with patch("operations.code_intel.search_code_skeletons_logic", new=logic):
        assert await code_intel.search_code_skeletons("P", "q") == [{"path": "a.py"}]
    logic.assert_awaited_once_with(
        "P", "q", chunk_type=None, limit=10, include_tests=False, root_path=None
    )


async def test_get_file_skeleton_returns_model_dumps():
    row = MagicMock()
    row.model_dump.return_value = {"unit": "C"}
    logic = AsyncMock(return_value=[row])
    with patch("operations.code_intel.get_file_skeleton_logic", new=logic):
        assert await code_intel.get_file_skeleton("P", "a.py") == [{"unit": "C"}]
    logic.assert_awaited_once_with("P", "a.py", depth=2, summary_only=False)


async def test_get_guideline_passes_role_to_logic():
    with patch("operations.context.get_guideline_logic", return_value="guide") as logic:
        assert await context.get_guideline("P", "execution") == "guide"
    logic.assert_called_once_with("P", "execution")
