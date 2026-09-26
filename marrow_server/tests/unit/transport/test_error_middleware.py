"""
Unit tests for the mcp_error_handler decorator and domain exceptions.

Run: pytest tests/test_error_middleware.py -v
"""

import logging
from unittest.mock import MagicMock, patch

import utils.error_middleware as error_middleware_module
from utils.error_middleware import (
    DebugArtifactLogHandler,
    _handle_domain_error,
    _handle_system_error,
    mcp_error_handler,
)
from utils.exceptions import (
    ArtifactNotFoundError,
    BaseBacklogError,
    DomainProtectionError,
    InvalidPathError,
    ProjectNotFoundError,
    TaskNotFoundError,
    ValidationError,
)

# ---------------------------------------------------------------------------
# Helper: build a decorated dummy that raises a given exception
# ---------------------------------------------------------------------------


def _raises(exc: Exception):
    @mcp_error_handler
    def dummy():
        raise exc

    return dummy


# ---------------------------------------------------------------------------
# 1. Domain exceptions are caught and returned as structured dicts
# ---------------------------------------------------------------------------


class TestDomainErrorsCaught:
    def test_mcp_error_handler_artifact_not_found_returns_structured_error(self):
        result = _raises(ArtifactNotFoundError("file.md not found"))()
        assert result["status"] == "error"
        assert result["error_type"] == "ArtifactNotFoundError"
        assert "file.md" in result["message"]

    def test_mcp_error_handler_project_not_found_returns_correct_error_type(self):
        result = _raises(ProjectNotFoundError("MyProject not found"))()
        assert result["error_type"] == "ProjectNotFoundError"

    def test_mcp_error_handler_task_not_found_includes_task_id_in_message(self):
        result = _raises(TaskNotFoundError("Ф42 not found"))()
        assert result["error_type"] == "TaskNotFoundError"
        assert "Ф42" in result["message"]

    def test_mcp_error_handler_domain_protection_error_preserves_details(self):
        result = _raises(
            DomainProtectionError("Forbidden", details={"protected_file": "memory/decisions.md"})
        )()
        assert result["error_type"] == "DomainProtectionError"
        assert result["details"]["protected_file"] == "memory/decisions.md"

    def test_mcp_error_handler_validation_error_returns_correct_error_type(self):
        result = _raises(ValidationError("Duplicate title"))()
        assert result["error_type"] == "ValidationError"

    def test_mcp_error_handler_invalid_path_returns_correct_error_type(self):
        result = _raises(InvalidPathError("../secret"))()
        assert result["error_type"] == "InvalidPathError"

    def test_mcp_error_handler_base_error_returns_error_status(self):
        result = _raises(BaseBacklogError("generic domain error"))()
        assert result["status"] == "error"
        assert result["error_type"] == "BaseBacklogError"


# ---------------------------------------------------------------------------
# 2. System (unknown) exceptions are caught and sanitised
# ---------------------------------------------------------------------------


class TestSystemErrorsCaught:
    def test_mcp_error_handler_runtime_error_returns_system_error_without_paths(self):
        result = _raises(RuntimeError("Something unexpected"))()
        assert result["status"] == "error"
        assert result["error_type"] == "SystemError"
        # Must not expose raw paths
        assert "D:\\" not in result.get("message", "")
        assert "C:\\" not in result.get("message", "")

    def test_mcp_error_handler_stdlib_value_error_returns_system_error(self):
        result = _raises(ValueError("raw stdlib error"))()
        assert result["error_type"] == "SystemError"

    def test_mcp_error_handler_file_not_found_returns_system_error(self):
        result = _raises(FileNotFoundError("some/internal/path"))()
        assert result["error_type"] == "SystemError"


# ---------------------------------------------------------------------------
# 3. Normal return passes through unchanged
# ---------------------------------------------------------------------------


class TestPassthrough:
    def test_mcp_error_handler_dict_return_passes_through_unchanged(self):
        @mcp_error_handler
        def dummy():
            return {"status": "ok", "data": [1, 2, 3]}

        assert dummy() == {"status": "ok", "data": [1, 2, 3]}

    def test_mcp_error_handler_list_return_passes_through_unchanged(self):
        @mcp_error_handler
        def dummy():
            return ["a", "b"]

        assert dummy() == ["a", "b"]

    def test_mcp_error_handler_string_return_passes_through_unchanged(self):
        @mcp_error_handler
        def dummy():
            return "success"

        assert dummy() == "success"

    def test_mcp_error_handler_none_return_passes_through_unchanged(self):
        @mcp_error_handler
        def dummy():
            return None

        assert dummy() is None


# ---------------------------------------------------------------------------
# 4. Decorator preserves function metadata (important for FastMCP)
# ---------------------------------------------------------------------------


class TestMetadataPreserved:
    def test_mcp_error_handler_preserves_function_name(self):
        @mcp_error_handler
        def my_tool():
            """My docstring."""

        assert my_tool.__name__ == "my_tool"

    def test_mcp_error_handler_preserves_function_docstring(self):
        @mcp_error_handler
        def my_tool():
            """My docstring."""

        assert my_tool.__doc__ == "My docstring."


# ---------------------------------------------------------------------------
# 5. Details field is omitted when empty
# ---------------------------------------------------------------------------


class TestDetailsField:
    def test_mcp_error_handler_omits_details_key_when_empty(self):
        result = _raises(ArtifactNotFoundError("missing"))()
        assert "details" not in result  # details={} → omitted

    def test_mcp_error_handler_includes_details_when_not_empty(self):
        result = _raises(DomainProtectionError("blocked", details={"reason": "protected"}))()
        assert result["details"]["reason"] == "protected"


class TestDebugArtifactLogHandler:
    def _make_record(self, project=None, debug_traceback=None):
        record = logging.LogRecord(
            name="utils.error_middleware",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="msg",
            args=(),
            exc_info=None,
            func="some_tool",
        )
        record.project = project
        record.debug_traceback = debug_traceback
        return record

    def test_emit_missing_project_field_is_noop(self):
        handler = DebugArtifactLogHandler()
        record = self._make_record(project=None, debug_traceback="Traceback...")
        with patch("utils.error_middleware.get_artifacts_path") as mock_get_path:
            handler.emit(record)
        mock_get_path.assert_not_called()

    def test_emit_missing_traceback_field_is_noop(self):
        handler = DebugArtifactLogHandler()
        record = self._make_record(project="MyProject", debug_traceback=None)
        with patch("utils.error_middleware.get_artifacts_path") as mock_get_path:
            handler.emit(record)
        mock_get_path.assert_not_called()

    def test_emit_valid_fields_appends_traceback_to_debug_log(self):
        handler = DebugArtifactLogHandler()
        record = self._make_record(
            project="MyProject",
            debug_traceback="Traceback (most recent call last):\nValueError: boom",
        )
        mock_pp = MagicMock()
        mock_pp.exists.return_value = True
        mock_pp.read.return_value = "existing content\n"
        with patch(
            "utils.error_middleware.get_artifacts_path", return_value=mock_pp
        ) as mock_get_path:
            handler.emit(record)
        mock_get_path.assert_called_once_with("MyProject", "Debug.log")
        mock_pp.read.assert_called_once()
        written = mock_pp.write.call_args[0][0]
        assert written.startswith("existing content\n")
        assert "ValueError: boom" in written
        assert "some_tool" in written

    def test_emit_no_existing_file_writes_fresh_entry(self):
        handler = DebugArtifactLogHandler()
        record = self._make_record(project="MyProject", debug_traceback="tb")
        mock_pp = MagicMock()
        mock_pp.exists.return_value = False
        with patch("utils.error_middleware.get_artifacts_path", return_value=mock_pp):
            handler.emit(record)
        mock_pp.read.assert_not_called()
        written = mock_pp.write.call_args[0][0]
        assert "tb" in written

    def test_emit_write_failure_swallowed_via_handleError(self):
        handler = DebugArtifactLogHandler()
        record = self._make_record(project="MyProject", debug_traceback="tb")
        mock_pp = MagicMock()
        mock_pp.exists.return_value = False
        mock_pp.write.side_effect = RuntimeError("disk full")
        with patch("utils.error_middleware.get_artifacts_path", return_value=mock_pp):
            with patch.object(DebugArtifactLogHandler, "handleError") as mock_handle_error:
                handler.emit(record)  # must not raise
        mock_handle_error.assert_called_once_with(record)


class TestProjectKwargPlumbing:
    def test_handle_domain_error_external_debug_true_passes_project_and_traceback_via_extra(self):
        with patch.object(error_middleware_module, "EXTERNAL_DEBUG", True):
            with patch.object(error_middleware_module, "logger") as mock_logger:
                _handle_domain_error(BaseBacklogError("boom"), "some_tool", project="MyProject")
        _, kwargs = mock_logger.warning.call_args
        extra = kwargs["extra"]
        assert extra["project"] == "MyProject"
        assert "debug_traceback" in extra

    def test_handle_domain_error_external_debug_false_passes_extra_none(self):
        with patch.object(error_middleware_module, "EXTERNAL_DEBUG", False):
            with patch.object(error_middleware_module, "logger") as mock_logger:
                _handle_domain_error(BaseBacklogError("boom"), "some_tool", project="MyProject")
        _, kwargs = mock_logger.warning.call_args
        assert kwargs["extra"] is None

    def test_handle_system_error_external_debug_true_passes_project_and_traceback_via_extra(self):
        with patch.object(error_middleware_module, "EXTERNAL_DEBUG", True):
            with patch.object(error_middleware_module, "logger") as mock_logger:
                _handle_system_error(RuntimeError("boom"), "some_tool", project="MyProject")
        _, kwargs = mock_logger.error.call_args
        extra = kwargs["extra"]
        assert extra["project"] == "MyProject"
        assert "debug_traceback" in extra

    def test_handle_system_error_external_debug_false_passes_extra_none(self):
        with patch.object(error_middleware_module, "EXTERNAL_DEBUG", False):
            with patch.object(error_middleware_module, "logger") as mock_logger:
                _handle_system_error(RuntimeError("boom"), "some_tool", project="MyProject")
        _, kwargs = mock_logger.error.call_args
        assert kwargs["extra"] is None

    def test_async_wrapper_extracts_project_from_kwargs_for_domain_error(self):
        @mcp_error_handler
        async def tool(project: str):
            raise ArtifactNotFoundError("missing")

        with patch.object(error_middleware_module, "_handle_domain_error") as mock_handle:
            mock_handle.return_value = {"status": "error"}
            import asyncio

            asyncio.get_event_loop().run_until_complete(tool(project="MyProject"))
        mock_handle.assert_called_once()
        assert mock_handle.call_args[0][2] == "MyProject"

    def test_sync_wrapper_extracts_project_from_kwargs_for_system_error(self):
        @mcp_error_handler
        def tool(project: str):
            raise RuntimeError("boom")

        with patch.object(error_middleware_module, "_handle_system_error") as mock_handle:
            mock_handle.return_value = {"status": "error"}
            tool(project="MyProject")
        mock_handle.assert_called_once()
        assert mock_handle.call_args[0][2] == "MyProject"

    def test_sync_wrapper_no_project_kwarg_passes_none(self):
        @mcp_error_handler
        def tool():
            raise RuntimeError("boom")

        with patch.object(error_middleware_module, "_handle_system_error") as mock_handle:
            mock_handle.return_value = {"status": "error"}
            tool()
        assert mock_handle.call_args[0][2] is None
