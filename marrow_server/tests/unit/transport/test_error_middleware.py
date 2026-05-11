"""
Unit tests for the mcp_error_handler decorator and domain exceptions.

Run: pytest tests/test_error_middleware.py -v
"""


from utils.error_middleware import mcp_error_handler
from utils.exceptions import (
    ArtifactNotFoundError,
    BaseBacklogError,
    DomainProtectionError,
    InvalidPathError,
    ProjectNotFoundError,
    StorageDisabledError,
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

    def test_mcp_error_handler_storage_disabled_returns_correct_error_type(self):
        result = _raises(StorageDisabledError("Storage off"))()
        assert result["error_type"] == "StorageDisabledError"

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
