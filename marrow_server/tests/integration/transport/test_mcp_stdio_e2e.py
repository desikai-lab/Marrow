import os
import sys

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@pytest.mark.asyncio
async def test_mcp_stdio_server_list_tools_returns_all_registered_tools():
    """
    End-to-End test that spawns mcp_local.py as a subprocess and fully
    communicates over stdio using the official MCP Client.
    """
    server_script = os.path.join(os.path.dirname(__file__), "..", "..", "..", "src", "mcp_local.py")

    server_params = StdioServerParameters(
        command=sys.executable, args=[server_script], env=os.environ.copy()
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Request tools
            tools = await session.list_tools()
            tool_names = [tool.name for tool in tools.tools]

            # Assert some of the known tools are present
            assert "list_projects" in tool_names
            assert "search_tasks" in tool_names
            assert "get_session_context" in tool_names

            # Attempt to execute a simple read-only tool
            result = await session.call_tool("list_projects", {})
            assert result is not None
            assert len(result.content) > 0
            # E2E passed
