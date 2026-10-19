from mcp.server.fastmcp import FastMCP
from transport.tool_registry import register_tools

mcp = FastMCP("marrow")
register_tools(mcp)
