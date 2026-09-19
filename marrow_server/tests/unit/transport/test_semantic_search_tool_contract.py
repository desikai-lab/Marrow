import pytest
from mcp.server.fastmcp import FastMCP

from transport.tool_registry import register_all_tools


async def _semantic_search_tool():
    mcp = FastMCP("semantic-search-contract")
    register_all_tools(mcp)
    return next(t for t in await mcp.list_tools() if t.name == "semantic_search")


@pytest.mark.asyncio
async def test_semantic_search_tool_schema_exposes_project_query_limit_scopes():
    tool = await _semantic_search_tool()

    assert set(tool.inputSchema["properties"]) == {"project", "query", "limit", "scopes"}


@pytest.mark.asyncio
async def test_semantic_search_tool_scopes_param_is_optional_and_defaults_to_none():
    tool = await _semantic_search_tool()

    scopes_schema = tool.inputSchema["properties"]["scopes"]
    assert "scopes" not in tool.inputSchema.get("required", [])
    assert scopes_schema.get("default") is None


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


@pytest.mark.asyncio
async def test_semantic_search_tool_description_documents_scopes_and_no_longer_claims_no_other_params():
    description = (await _semantic_search_tool()).description

    for required in (
        "scopes",
        "directories",
        "20",
        "message",
    ):
        assert required in description, required
    # REQ-08: this sentence was true before scopes existed and must not survive.
    assert "there are no other tunable parameters" not in description


@pytest.mark.asyncio
async def test_semantic_search_tool_description_documents_the_two_return_shapes():
    description = (await _semantic_search_tool()).description

    # REQ-07: the empty-result shape is a single object with a "message" key,
    # not a list -- the docstring must say so explicitly, not just mention
    # "message" in passing.
    assert "list" in description
    assert '"message"' in description or "'message'" in description


@pytest.mark.asyncio
async def test_semantic_search_tool_description_warns_against_file_path_as_scope():
    description = (await _semantic_search_tool()).description

    assert "Do NOT pass a file path as a scope" in description
