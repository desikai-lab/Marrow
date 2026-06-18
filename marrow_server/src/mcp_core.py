from mcp.server.fastmcp import FastMCP
from transport.tool_registry import register_all_tools

mcp = FastMCP("marrow")
register_all_tools(mcp)
