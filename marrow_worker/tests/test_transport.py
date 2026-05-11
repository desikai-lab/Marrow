import json
import os

import pytest
from pytest_httpx import HTTPXMock

from src.transport import MCPClient

FAKE_TOKEN = "test-secret-token"
FAKE_CHUNKS = [
    {
        "type": "method",
        "name": "ProcessOrder",
        "skeleton_text": "public async Task<Result> ProcessOrder(OrderDto dto) { ... }",
        "vector": [0.1, 0.2],
        "line_start": 45,
        "line_end": 90,
    }
]


@pytest.mark.asyncio
async def test_mcp_client_success(httpx_mock: HTTPXMock):
    """Valid payload → 200, correct relative path and fields in body."""
    httpx_mock.add_response(
        method="POST",
        url="http://test_server/api/vectorize",
        status_code=200,
        json={"status": "ok", "chunks_stored": 1},
    )

    client = MCPClient(
        target_url="http://test_server",
        project_name="TestProject",
        secret_token=FAKE_TOKEN,
        root_dir=os.getcwd(),
    )

    cwd = os.getcwd()
    fake_abs_path = os.path.join(cwd, "src", "dummy.cs")

    await client.send_chunks(
        absolute_filepath=fake_abs_path,
        file_summary="CS file: dummy.cs",
        chunks=FAKE_CHUNKS,
    )

    requests = httpx_mock.get_requests()
    assert len(requests) == 1

    # Verify Authorization header is sent
    assert requests[0].headers["authorization"] == f"Bearer {FAKE_TOKEN}"

    # Verify payload shape
    payload = json.loads(requests[0].read().decode("utf-8"))
    assert payload["project_name"] == "TestProject"
    assert payload["path"] == "src/dummy.cs"
    assert payload["file_summary"] == "CS file: dummy.cs"
    assert len(payload["chunks"]) == 1
    assert payload["chunks"][0]["type"] == "method"
    assert payload["chunks"][0]["name"] == "ProcessOrder"

    await client.close()


@pytest.mark.asyncio
async def test_mcp_client_resilience(httpx_mock: HTTPXMock, caplog):
    """Server 500 → exception swallowed, error message logged (no crash)."""
    httpx_mock.add_response(
        method="POST",
        url="http://test_server/api/vectorize",
        status_code=500,
    )

    client = MCPClient(
        target_url="http://test_server",
        project_name="TestProject",
        secret_token=FAKE_TOKEN,
        root_dir=os.getcwd(),
    )
    cwd = os.getcwd()
    fake_abs_path = os.path.join(cwd, "src", "dummy.cs")

    # Must NOT raise — failure is logged and swallowed
    with caplog.at_level("ERROR"):
        await client.send_chunks(
            absolute_filepath=fake_abs_path,
            file_summary="CS file: dummy.cs",
            chunks=FAKE_CHUNKS,
        )

    assert "Failed to deliver skeleton" in caplog.text

    await client.close()
