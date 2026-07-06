from unittest.mock import AsyncMock, patch

import httpx
import pytest
from src.transport.api_client import MCPClient
from src.transport.outbox import WorkerOutbox


@pytest.mark.asyncio
async def test_delete_durability_on_failure():
    # 1. Setup in-memory outbox
    outbox = WorkerOutbox(db_path=":memory:", flush_interval=60)
    await outbox.setup()

    # 2. Setup MCPClient with a mock httpx client
    mock_httpx = AsyncMock(spec=httpx.AsyncClient)

    # Simulate network failure for DELETE requests
    mock_httpx.request.side_effect = httpx.ConnectError("Network is down")

    client = MCPClient(
        target_url="http://mock-server",
        project_name="TestProject",
        secret_token="fake-token",
        root_dir="/mock/root",
        outbox=outbox,
    )
    # Inject the mock client
    client.client = mock_httpx

    # 3. Trigger a delete
    test_file = "/mock/root/src/deleted_file.py"
    # We need to ensure relpath works correctly with /mock/root
    # Since we are on Windows, we might need to adjust paths or mock os.path.relpath
    with patch("os.path.relpath", return_value="src/deleted_file.py"):
        await client.delete_chunks(test_file)

    # 4. Verify outbox state
    rows = outbox._conn.execute("SELECT id, operation, status FROM outbox").fetchall()
    assert len(rows) == 1
    assert rows[0][1] == "delete"
    assert rows[0][2] == "pending"

    # 5. Restore network (mock success)
    mock_httpx.request.side_effect = None
    mock_httpx.request.return_value = AsyncMock(status_code=200, json=lambda: {"status": "ok"})

    # 6. Flush outbox
    deliver_fn = client._make_deliver_fn()
    await outbox.flush_pending(deliver_fn)

    # 7. Verify outbox is now empty
    rows_after = outbox._conn.execute("SELECT id FROM outbox").fetchall()
    assert len(rows_after) == 0

    # Verify the mock was called with DELETE
    mock_httpx.request.assert_called_with(
        "DELETE",
        "/api/vectorize",
        json={"project_name": "TestProject", "path": "src/deleted_file.py"},
    )

    await outbox.close()
