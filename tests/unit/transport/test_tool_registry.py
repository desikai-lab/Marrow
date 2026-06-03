import inspect
from unittest.mock import MagicMock

from mcp.server.fastmcp import FastMCP

import mcp_core
from transport.tool_registry import register_all_tools


def test_register_all_tools_called_with_mcp_instance_mounts_23_tools():
    mock_mcp = MagicMock()
    register_all_tools(mock_mcp)
    assert mock_mcp.tool.call_count == 23


def test_register_all_tools_mcp_core_import_resolves_mcp_symbol():
    from mcp_core import mcp

    assert isinstance(mcp, FastMCP)


def test_register_all_tools_no_tool_stubs_remain_in_mcp_core():
    functions = [name for name, obj in inspect.getmembers(mcp_core, inspect.isfunction)]
    assert "add_tasks" not in functions
    assert "search_tasks" not in functions
    assert "get_task_details" not in functions
