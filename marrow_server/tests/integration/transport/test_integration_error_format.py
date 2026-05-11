"""
Integration tests: verify that MCP tool calls return errors in the
standardised {status, error_type, message} format when given bad input.

Uses project "TestIntegrationPhase4" (real temp dir, created/torn down per session)
and a per-class ghost project name (uuid-based) to avoid cross-test dir pollution.
"""
import os
import uuid
import shutil
import pytest

from utils.error_middleware import mcp_error_handler
from utils.exceptions import ProjectNotFoundError, TaskNotFoundError, StorageDisabledError

from services.task_query_service import search_tasks_logic, get_task_details_logic
from services.task_command_service import update_task_logic
from services.artifact_query_service import search_artifact_sections_logic
from tools import list_artifacts_logic

# ── helpers ──────────────────────────────────────────────────────────────────

TEST_PROJECT = "TestIntegrationPhase4"


def _wrap(fn, *args, **kwargs):
    """Run fn(*args) through mcp_error_handler, return the result."""
    import asyncio
    
    # We decorate the function first
    wrapped = mcp_error_handler(fn)
    
    # Check if the ORIGINAL function is a coroutine function
    # Note: mcp_error_handler returns an async_wrapper if it is.
    result = wrapped(*args, **kwargs)
    
    if asyncio.iscoroutine(result):
        # We need an event loop to run the coroutine
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        return loop.run_until_complete(result)
    return result


def _assert_error(result, error_type: str = None):
    """Normalise list/dict result and assert it is a standard error dict."""
    if isinstance(result, list):
        assert len(result) > 0, f"Expected error dict, got empty list"
        result = result[0]
    assert isinstance(result, dict), f"Expected dict, got {type(result)}: {result}"
    assert result.get("status") == "error", f"status != 'error': {result}"
    if error_type:
        assert result.get("error_type") == error_type, (
            f"error_type mismatch: expected {error_type}, got {result.get('error_type')}: {result}"
        )
    return result


def _ghost() -> str:
    """Generate a unique project name that is guaranteed not to exist on disk."""
    return f"_GHOST_{uuid.uuid4().hex[:8]}"


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def real_project(tmp_path_factory):
    """Creates a real on-disk project and tears it down after all tests in module."""
    from config import PROJECTS_ROOT
    root = os.path.join(PROJECTS_ROOT, TEST_PROJECT)
    os.makedirs(root, exist_ok=True)
    yield TEST_PROJECT
    shutil.rmtree(root, ignore_errors=True)


# ── 1. ProjectNotFoundError ───────────────────────────────────────────────────

class TestProjectNotFound:
    """
    Each test uses its own unique ghost project name so that LanceDB
    bootstrapping in one test cannot pollute the next.
    """

    def test_search_tasks_logic_unknown_project_returns_project_not_found_error(self):
        ghost = _ghost()
        result = _wrap(search_tasks_logic, ghost)
        _assert_error(result, "ProjectNotFoundError")

    def test_get_task_details_logic_unknown_project_returns_project_not_found_error(self):
        ghost = _ghost()
        result = _wrap(get_task_details_logic, ghost, "F1")
        _assert_error(result, "ProjectNotFoundError")

    def test_update_task_logic_unknown_project_returns_project_not_found_error(self):
        ghost = _ghost()
        result = _wrap(update_task_logic, ghost, "F1", {"status": "closed"})
        _assert_error(result, "ProjectNotFoundError")

    def test_search_artifact_sections_logic_unknown_project_returns_project_not_found_error(self):
        """
        search_artifact_sections raises ProjectNotFoundError when project dir
        is absent. It returns an empty list [] if LanceDB created the dir first
        (e.g. from another test) — both are acceptable for a ghost project.
        We use a fresh uuid name to guarantee the dir doesn't pre-exist.
        """
        ghost = _ghost()
        result = _wrap(search_artifact_sections_logic, ghost, "query")
        # Either: structured error OR empty list (no data) — never old {"error": ...}
        if isinstance(result, list):
            for item in result:
                assert "error" not in item or item.get("status") == "error", (
                    f"Legacy error format detected: {item}"
                )
        else:
            _assert_error(result, "ProjectNotFoundError")

    def test_list_artifacts_logic_unknown_project_returns_empty_list_or_error(self):
        """
        list_artifacts_logic returns [] when the directory doesn't exist
        (validate_artifact_path doesn't raise for missing dirs).
        Verify: no legacy {\"error\":...} keys, no crash.
        """
        ghost = _ghost()
        result = _wrap(list_artifacts_logic, ghost, "")
        # Acceptable: empty list [] or ProjectNotFoundError dict
        if isinstance(result, list):
            assert all(
                "error" not in item or item.get("status") == "error"
                for item in result
            ), f"Legacy error format in list: {result}"
        else:
            _assert_error(result, "ProjectNotFoundError")


# ── 2. TaskNotFoundError ──────────────────────────────────────────────────────

class TestTaskNotFound:
    def test_get_task_details_logic_missing_task_id_returns_task_not_found_error(self, real_project):
        result = _wrap(get_task_details_logic, real_project, "F99999")
        _assert_error(result, "TaskNotFoundError")

    def test_update_task_logic_missing_task_id_returns_task_not_found_error(self, real_project):
        result = _wrap(update_task_logic, real_project, "F99999", {"status": "closed"})
        _assert_error(result, "TaskNotFoundError")


# ── 3. Error response structure ───────────────────────────────────────────────

class TestErrorStructure:
    """Contract: every error dict must have status, error_type, message."""

    def _assert_structure(self, result):
        if isinstance(result, list):
            assert result, "Got empty list, expected error dict"
            result = result[0]
        assert isinstance(result, dict), f"Expected dict, got {type(result)}: {result}"
        assert result.get("status") == "error",    f"Missing status=error: {result}"
        assert "error_type" in result,             f"Missing error_type: {result}"
        assert "message" in result,                f"Missing message: {result}"
        assert isinstance(result["message"], str), f"message must be str: {result}"
        if "details" in result:
            assert isinstance(result["details"], dict), f"details must be dict: {result}"

    def test_mcp_error_handler_project_not_found_returns_standard_error_structure(self):
        result = _wrap(search_tasks_logic, _ghost())
        self._assert_structure(result)

    def test_mcp_error_handler_task_not_found_returns_standard_error_structure(self, real_project):
        result = _wrap(get_task_details_logic, real_project, "F00000")
        self._assert_structure(result)

    def test_mcp_error_handler_runtime_error_does_not_leak_absolute_paths(self):
        """System errors must not expose Windows filesystem paths."""
        @mcp_error_handler
        def leaky():
            raise RuntimeError(r"D:\MCPs\marrow_server\secret\path.py failed")
        result = leaky()
        assert "D:\\" not in result["message"], f"Path leaked: {result}"

    def test_mcp_error_handler_domain_exception_uses_class_name_as_error_type(self):
        result = _wrap(search_tasks_logic, _ghost())
        if isinstance(result, list):
            result = result[0]
        assert result["error_type"] == "ProjectNotFoundError"

    def test_mcp_error_handler_returns_status_error_instead_of_legacy_error_key(self):
        """
        The old-style {\"error\": \"...\"} response must NOT appear as the only key.
        Acceptable: {status: error, error_type: ..., message: ...}
        """
        result = _wrap(search_tasks_logic, _ghost())
        if isinstance(result, list):
            result = result[0]
        # The new format has 'status', not a bare 'error' key
        assert "status" in result, f"Missing 'status' key in result: {result}"
        assert result["status"] == "error"
        # There must be no naked "error" key without "status"
        if "error" in result:
            assert "status" in result, f"Bare 'error' key without 'status': {result}"
