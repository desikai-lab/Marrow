# marrow_server/tests/integration/transport/test_external_debug_log.py
import importlib
import os
import shutil

import pytest

import config
from config import PROJECTS_ROOT

pytestmark = pytest.mark.integration

TEST_PROJECT = "TestExternalDebugLog"


@pytest.fixture
def real_project():
    root = os.path.join(PROJECTS_ROOT, TEST_PROJECT)
    os.makedirs(os.path.join(root, "artifacts"), exist_ok=True)
    yield TEST_PROJECT
    shutil.rmtree(root, ignore_errors=True)


def _reload_error_middleware_with_flag(flag_value: str | None):
    if flag_value is None:
        os.environ.pop("EXTERNAL_DEBUG", None)
    else:
        os.environ["EXTERNAL_DEBUG"] = flag_value
    importlib.reload(config)
    import utils.error_middleware as em

    importlib.reload(em)
    return em


def test_external_debug_true_writes_traceback_to_debug_log(real_project):
    """EXTERNAL_DEBUG=true (bool): full traceback is raised as McpError (dicts
    can't survive output-schema validation for list-declared tools) AND the
    traceback is appended to <project>/artifacts/Debug.log via the log handler."""
    from mcp.shared.exceptions import McpError

    em = _reload_error_middleware_with_flag("true")
    assert em.EXTERNAL_DEBUG is True
    try:

        @em.mcp_error_handler
        def failing_tool(project: str):
            raise RuntimeError("synthetic failure for F4000283")

        with pytest.raises(McpError) as exc_info:
            failing_tool(project=real_project)
        assert "RuntimeError: synthetic failure for F4000283" in exc_info.value.error.message
        assert "Traceback" in exc_info.value.error.message

        debug_log_path = os.path.join(PROJECTS_ROOT, real_project, "artifacts", "Debug.log")
        assert os.path.exists(debug_log_path)
        content = open(debug_log_path, encoding="utf-8").read()
        assert "RuntimeError: synthetic failure for F4000283" in content
        assert "failing_tool" in content
    finally:
        _reload_error_middleware_with_flag(None)


def test_external_debug_false_returns_dict_and_writes_nothing(real_project):
    """EXTERNAL_DEBUG unset (bool False): dict contract, no Debug.log."""
    em_off = _reload_error_middleware_with_flag(None)
    assert em_off.EXTERNAL_DEBUG is False

    @em_off.mcp_error_handler
    def failing_tool(project: str):
        raise RuntimeError("synthetic failure for F4000283")

    result_off = failing_tool(project=real_project)
    assert result_off["status"] == "error"
    assert result_off["error_type"] == "SystemError"

    debug_log_path = os.path.join(PROJECTS_ROOT, real_project, "artifacts", "Debug.log")
    assert not os.path.exists(debug_log_path)


def test_external_debug_true_domain_error_also_writes_debug_log(real_project):
    from mcp.shared.exceptions import McpError

    em = _reload_error_middleware_with_flag("true")
    assert em.EXTERNAL_DEBUG is True
    try:
        from utils.exceptions import ArtifactNotFoundError

        @em.mcp_error_handler
        def failing_tool(project: str):
            raise ArtifactNotFoundError("spec.md not found")

        with pytest.raises(McpError) as exc_info:
            failing_tool(project=real_project)
        assert "ArtifactNotFoundError" in exc_info.value.error.message

        debug_log_path = os.path.join(PROJECTS_ROOT, real_project, "artifacts", "Debug.log")
        assert os.path.exists(debug_log_path)
        content = open(debug_log_path, encoding="utf-8").read()
        assert "ArtifactNotFoundError" in content
    finally:
        _reload_error_middleware_with_flag(None)
