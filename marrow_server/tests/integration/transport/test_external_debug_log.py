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
    em = _reload_error_middleware_with_flag("true")
    try:

        @em.mcp_error_handler
        def failing_tool(project: str):
            raise RuntimeError("synthetic failure for F4000283")

        result = failing_tool(project=real_project)

        assert result["status"] == "error"
        assert result["error_type"] == "SystemError"
        assert "debug_traceback" not in result  # REQ-05: never on the wire

        debug_log_path = os.path.join(PROJECTS_ROOT, real_project, "artifacts", "Debug.log")
        assert os.path.exists(debug_log_path)
        content = open(debug_log_path, encoding="utf-8").read()
        assert "RuntimeError: synthetic failure for F4000283" in content
        assert "failing_tool" in content
    finally:
        _reload_error_middleware_with_flag(None)


def test_external_debug_false_writes_nothing_and_response_matches_flag_on_shape(real_project):
    em_off = _reload_error_middleware_with_flag(None)

    @em_off.mcp_error_handler
    def failing_tool(project: str):
        raise RuntimeError("synthetic failure for F4000283")

    result_off = failing_tool(project=real_project)

    debug_log_path = os.path.join(PROJECTS_ROOT, real_project, "artifacts", "Debug.log")
    assert not os.path.exists(debug_log_path)

    em_on = _reload_error_middleware_with_flag("true")
    try:

        @em_on.mcp_error_handler
        def failing_tool_on(project: str):
            raise RuntimeError("synthetic failure for F4000283")

        result_on = failing_tool_on(project=real_project)
        # REQ-04: client-facing dict is identical regardless of the flag.
        assert result_off == result_on
    finally:
        _reload_error_middleware_with_flag(None)


def test_external_debug_true_domain_error_also_writes_debug_log(real_project):
    em = _reload_error_middleware_with_flag("true")
    try:
        from utils.exceptions import ArtifactNotFoundError

        @em.mcp_error_handler
        def failing_tool(project: str):
            raise ArtifactNotFoundError("spec.md not found")

        result = failing_tool(project=real_project)
        assert result["status"] == "error"
        assert result["error_type"] == "ArtifactNotFoundError"

        debug_log_path = os.path.join(PROJECTS_ROOT, real_project, "artifacts", "Debug.log")
        assert os.path.exists(debug_log_path)
        content = open(debug_log_path, encoding="utf-8").read()
        assert "ArtifactNotFoundError" in content
    finally:
        _reload_error_middleware_with_flag(None)
