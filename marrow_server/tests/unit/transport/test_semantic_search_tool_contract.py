import pytest
from mcp.server.fastmcp import FastMCP

from transport.tool_registry import register_all_tools


async def _semantic_search_tool():
    mcp = FastMCP("semantic-search-contract")
    register_all_tools(mcp)
    return next(t for t in await mcp.list_tools() if t.name == "semantic_search")


@pytest.mark.asyncio
async def test_semantic_search_tool_schema_exposes_only_project_query_limit():
    tool = await _semantic_search_tool()

    assert set(tool.inputSchema["properties"]) == {"project", "query", "limit"}


@pytest.mark.asyncio
async def test_semantic_search_tool_description_documents_content_warning_and_negative_guidance():
    description = (await _semantic_search_tool()).description

    for required in (
        "[ARTIFACT TOOLS]",
        "Read-only",
        "content",
        "warning",
        "partial success",
        "Do NOT use",
        "read_project_artifacts",
    ):
        assert required in description, required
    assert "include_content" not in description
