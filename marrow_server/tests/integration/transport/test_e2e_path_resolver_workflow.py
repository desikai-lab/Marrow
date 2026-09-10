import os
import sys

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@pytest.mark.asyncio
async def test_e2e_path_resolver_workflow_via_stdio(tmp_path, monkeypatch):
    """
    End-to-End test that spawns mcp_local.py as a subprocess over stdio,
    and executes a full workflow involving project creation, nested artifact creation,
    reading, session context resolution, and traversal protection using PathResolver.
    """
    server_script = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "src", "mcp_local.py")
    )
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

    env = os.environ.copy()
    env["PROJECTS_ROOT"] = str(tmp_path)
    env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{root_dir}"

    server_params = StdioServerParameters(command=sys.executable, args=[server_script], env=env)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. Initialize project (triggers validate_project_path / PathResolver.get_raw_path)
            init_res = await session.call_tool(
                "init_project", {"project": "E2ETestProj", "template": "default"}
            )
            assert init_res is not None
            assert len(init_res.content) > 0

            # 2. Save nested artifact (triggers validate_artifact_path / PathResolver / FileAccessor)
            save_res = await session.call_tool(
                "save_project_artifacts",
                {
                    "project": "E2ETestProj",
                    "updates": [
                        {
                            "path": "docs/features/active/F100/spec.md",
                            "mode": "replace_file",
                            "content": "## Feature Spec\n\nContent for E2E test.",
                        }
                    ],
                },
            )
            assert save_res is not None
            assert (
                "File saved" in save_res.content[0].text
                or "success" in save_res.content[0].text.lower()
            )

            # 3. Read nested artifact back
            read_res = await session.call_tool(
                "read_project_artifacts",
                {
                    "project": "E2ETestProj",
                    "reads": [
                        {
                            "path": "docs/features/active/F100/spec.md",
                            "mode": "full",
                        }
                    ],
                },
            )
            assert read_res is not None
            assert "Feature Spec" in read_res.content[0].text

            # 4. Read session context (triggers PathResolver + session integrity)
            context_res = await session.call_tool("get_session_context", {"project": "E2ETestProj"})
            assert context_res is not None
            assert len(context_res.content) > 0

            # 5. Path traversal protection test (attempt to access outside project)
            traversal_res = await session.call_tool(
                "read_project_artifacts",
                {
                    "project": "E2ETestProj",
                    "reads": [
                        {
                            "path": "../../outside.txt",
                            "mode": "full",
                        }
                    ],
                },
            )
            assert traversal_res is not None
            res_text = traversal_res.content[0].text
            assert (
                "error" in res_text.lower()
                or "traversal" in res_text.lower()
                or "invalid" in res_text.lower()
            )
