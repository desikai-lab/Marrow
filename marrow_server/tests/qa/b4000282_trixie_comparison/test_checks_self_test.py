# tests/qa/b4000282_trixie_comparison/test_checks_self_test.py
"""In-process self-test for B4000282 check functions.

Transport: stdio (spawns src/mcp_local.py as a subprocess), same pattern as
marrow_server/tests/integration/transport/test_e2e_artifacts_tool.py. Fully
local -- needs no deployed container.

Why stdio and not in-process HTTP (the plan's original draft):
- httpx.ASGITransport never fires lifespan events, and /mcp requires the
  lifespan-entered StreamableHTTPSessionManager ("Task group is not
  initialized" otherwise). The manager's run() is single-entry per process,
  so a function-scoped lifespan fixture cannot re-enter it per test.
- The MCP SDK's DNS-rebinding protection rejects Host: testserver (421).

Session handling: an @asynccontextmanager entered *inside* each test body,
not a yield-fixture -- pytest-asyncio tears fixtures down in a different
task, and anyio cancel scopes (ClientSession/stdio_client) must exit in the
same task that entered them ("Attempted to exit cancel scope in a different
task" otherwise). This matches test_mcp_stdio_e2e.py, which also keeps the
session inside the test function.

Workspace: a fresh tmp TASKS_DIR per test, TEST_PROJECT="MarrowTest3"
(human-ordered 2026-09-26). This exercises the ensure_project create-path
for real with zero pollution of any real workspace.
"""

import os
import sys
from contextlib import asynccontextmanager

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from tests.qa.b4000282_trixie_comparison.checks import ensure_project, run_req05, run_rt04, run_rt16

TEST_PROJECT = "MarrowTest3"


def _server_params(tmp_path) -> StdioServerParameters:
    server_script = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "src", "mcp_local.py")
    )
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    env = os.environ.copy()
    env["TASKS_DIR"] = str(tmp_path)
    env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{root_dir}"
    return StdioServerParameters(command=sys.executable, args=[server_script], env=env)


@asynccontextmanager
async def open_session(tmp_path):
    """Stdio MCP session against a scratch TASKS_DIR -- checks.py runs exactly
    as it will against a real deployed container (it only needs an
    already-connected ClientSession)."""
    async with stdio_client(_server_params(tmp_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


@pytest.mark.asyncio
async def test_ensure_project_creates_then_noops(tmp_path):
    async with open_session(tmp_path) as session:
        first = await ensure_project(session, TEST_PROJECT)
        assert first == {"created": True}
        second = await ensure_project(session, TEST_PROJECT)
        assert second == {"created": False}


@pytest.mark.asyncio
async def test_run_rt04_returns_one_result_per_variant(tmp_path):
    async with open_session(tmp_path) as session:
        await ensure_project(session, TEST_PROJECT)
        result = await run_rt04(session, TEST_PROJECT)
        assert set(result.keys()) == {
            "v1_recursive_false",
            "v2_recursive_true",
            "v3_path_docs_recursive_true",
        }
        for variant in result.values():
            assert variant["shape"] in ("list", "dict")
            assert "error_type" in variant


@pytest.mark.asyncio
async def test_run_rt16_reports_write_and_readback(tmp_path):
    async with open_session(tmp_path) as session:
        await ensure_project(session, TEST_PROJECT)
        result = await run_rt16(session, TEST_PROJECT)
        assert result["write_timed_out"] in (True, False)
        assert result["readback_confirmed"] in (True, False)
        assert "elapsed_seconds" in result


@pytest.mark.asyncio
async def test_run_req05_forces_the_dict_list_mismatch(tmp_path):
    async with open_session(tmp_path) as session:
        await ensure_project(session, TEST_PROJECT)
        result = await run_req05(session, TEST_PROJECT)
        # Either the error dict arrives (widened contract) or schema
        # validation rejects it (current behavior) -- both prove REQ-03.
        # Note: pydantic truncates the rejected dict's repr, so the exception
        # name is unrecoverable client-side in the rejection shape; the
        # list_type signature itself is the mismatch fingerprint (its name is
        # established by code reading: path_resolver raises ProjectFileError).
        if result["shape"] == "dict":
            assert result["error_type"] == "ProjectFileError"
        else:
            assert result["shape"] == "schema_rejection"
            assert result["signature"] == "list_type"
