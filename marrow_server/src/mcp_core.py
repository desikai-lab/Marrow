from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from config import MCP_ALLOWED_HOSTS, MCP_DNS_REBINDING_PROTECTION
from transport.tool_registry import register_tools

transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=MCP_DNS_REBINDING_PROTECTION,
    allowed_hosts=MCP_ALLOWED_HOSTS,
)

mcp = FastMCP("marrow", transport_security=transport_security)
register_tools(mcp)
