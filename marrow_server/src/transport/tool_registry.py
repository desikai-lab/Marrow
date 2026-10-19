"""MCP tool registration: composes the tool modules under transport/modules/.

Each module owns the MCP stubs of one tool group and exposes one use_<group>_tools(mcp)
function. The optional groups (code, task, build) switch themselves off inside that
function (TOOL_GROUP_<GROUP>_ENABLED, see config.py). Add a new tool to its module's
tools.py; add a new module here.
"""

from mcp.server.fastmcp import FastMCP

from transport.modules.artifact.tools import use_artifact_tools
from transport.modules.build.tools import use_build_tools
from transport.modules.code.tools import use_code_tools
from transport.modules.history.tools import use_history_tools
from transport.modules.project.tools import use_project_tools
from transport.modules.session.tools import use_session_tools
from transport.modules.task.tools import use_task_tools


def register_tools(mcp: FastMCP) -> None:
    """Mount all MCP tools onto the provided FastMCP instance."""
    use_artifact_tools(mcp)
    use_history_tools(mcp)
    use_session_tools(mcp)
    use_project_tools(mcp)
    use_code_tools(mcp)
    use_task_tools(mcp)
    use_build_tools(mcp)
