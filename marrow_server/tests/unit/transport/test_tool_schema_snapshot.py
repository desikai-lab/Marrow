import asyncio
import json
import os
from pathlib import Path

from mcp_core import mcp

SNAPSHOT = Path(__file__).with_name("mcp_tool_schemas.snapshot.json")


def _current() -> dict:
    tools = asyncio.run(mcp.list_tools())
    data = {
        t.name: {
            "description": t.description,
            "inputSchema": t.inputSchema,
            "outputSchema": getattr(t, "outputSchema", None),
        }
        for t in tools
    }
    return json.loads(json.dumps(data, sort_keys=True))


def test_tool_schemas_registry_matches_golden_snapshot():
    current = _current()
    if os.getenv("MARROW_UPDATE_SNAPSHOT") == "1":
        SNAPSHOT.write_text(
            json.dumps(current, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
        )
    assert current == json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_tool_schemas_registry_exposes_24_tools():
    assert len(_current()) == 24
