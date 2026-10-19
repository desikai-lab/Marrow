'''Default-surface golden snapshots.

The JSON files under tests/fixtures/tool_groups/ were captured from unmodified main
before any tool-group source change. They pin the MCP tool list (name, description,
inputSchema) and the REST OpenAPI document of a default server.

Regenerate only when the served default surface is meant to change:
    cd marrow_server
    SECRET_TOKEN=x PYTHONPATH=src:.. python tests/unit/transport/test_tool_groups_golden.py --regenerate
'''

import asyncio
import json
import os
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / 'fixtures' / 'tool_groups'
MCP_GOLDEN = FIXTURES / 'default_mcp_tools.json'
REST_GOLDEN = FIXTURES / 'default_rest_openapi.json'


def capture_mcp_tools() -> list[dict]:
    from mcp_core import mcp

    tools = asyncio.run(mcp.list_tools())
    return sorted(
        (
            {'name': t.name, 'description': t.description, 'inputSchema': t.inputSchema}
            for t in tools
        ),
        key=lambda tool: tool['name'],
    )


def capture_rest_openapi() -> dict:
    from transport.rest.app import rest_app

    return json.loads(json.dumps(rest_app.openapi()))


def _dump(data) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + '\n'


def test_default_mcp_golden_pins_24_tools():
    assert len(json.loads(MCP_GOLDEN.read_text(encoding='utf-8'))) == 24


def test_default_mcp_tool_list_matches_golden():
    assert capture_mcp_tools() == json.loads(MCP_GOLDEN.read_text(encoding='utf-8'))


def test_default_rest_openapi_matches_golden():
    assert capture_rest_openapi() == json.loads(REST_GOLDEN.read_text(encoding='utf-8'))


if __name__ == '__main__':
    if '--regenerate' not in sys.argv:
        raise SystemExit('pass --regenerate to overwrite the golden snapshots')
    leaked = [k for k in os.environ if k.upper().startswith('TOOL_GROUP_')]
    if leaked:
        raise SystemExit(f'Unset {leaked} first: the golden must be the default surface.')
    FIXTURES.mkdir(parents=True, exist_ok=True)
    MCP_GOLDEN.write_text(_dump(capture_mcp_tools()), encoding='utf-8')
    REST_GOLDEN.write_text(_dump(capture_rest_openapi()), encoding='utf-8')
    print(f'wrote {MCP_GOLDEN} and {REST_GOLDEN}')