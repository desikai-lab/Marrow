import os
import sys
from pathlib import Path

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

pytestmark = pytest.mark.integration

SERVER_SCRIPT = Path(__file__).resolve().parents[3] / 'src' / 'mcp_local.py'
CODE_TOOLS = {'search_code_skeletons', 'get_file_skeleton', 'get_project_map', 'view_file_source'}
TASK_TOOLS = {'add_tasks', 'search_tasks', 'get_task_details', 'update_task', 'complete_tasks'}


def _env(**flags: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith('TOOL_GROUP_')}
    env.update(flags)
    return env


async def _tool_names(env: dict[str, str]) -> set[str]:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_SCRIPT)], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return {tool.name for tool in (await session.list_tools()).tools}


async def test_stdio_default_environment_lists_24_tools():
    assert len(await _tool_names(_env())) == 24


async def test_stdio_code_and_build_off_lists_19_tools_without_them():
    names = await _tool_names(
        _env(TOOL_GROUP_CODE_ENABLED='false', TOOL_GROUP_BUILD_ENABLED='false')
    )
    assert len(names) == 19
    assert not names & (CODE_TOOLS | {'run_project_build'})
    assert {'search_tasks', 'get_session_context'} <= names


async def test_stdio_task_off_lists_19_tools_without_task_tools():
    names = await _tool_names(_env(TOOL_GROUP_TASK_ENABLED='false'))
    assert len(names) == 19
    assert not names & TASK_TOOLS
    assert {'view_file_source', 'run_project_build'} <= names
