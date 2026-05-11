"""
tests/test_vectorize_endpoint.py
Tests for SKEL-7: POST /api/vectorize endpoint.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from config import EMBEDDING_DIMENSIONS, SECRET_TOKEN
from transport.app_factory import app

client = TestClient(app, raise_server_exceptions=False)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_CHUNK = {
    "type": "method",
    "name": "ProcessOrder",
    "skeleton_text": "public async Task<Result> ProcessOrder(OrderDto dto) { ... }",
    "vector": [0.1] * EMBEDDING_DIMENSIONS,
    "line_start": 45,
    "line_end": 90,
}

VALID_PAYLOAD = {
    "schema_version": "1.0",
    "project_name": "YourProject",
    "path": "src/Services/BigService.cs",
    "file_summary": "Namespace: YourProject.Services | Class: BigService",
    "chunks": [
        {
            "type": "namespace",
            "name": "YourProject.Services",
            "skeleton_text": "namespace YourProject.Services { ... }",
            "vector": [0.1] * EMBEDDING_DIMENSIONS,
            "line_start": 1,
            "line_end": 150,
        },
        {
            "type": "constructor",
            "name": "BigService",
            "skeleton_text": "public BigService(IDbContext db, ILogger log) { ... }",
            "vector": [0.2] * EMBEDDING_DIMENSIONS,
            "line_start": 25,
            "line_end": 32,
        },
        VALID_CHUNK,
    ],
}

AUTH_HEADERS = {"Authorization": f"Bearer {SECRET_TOKEN}"}


# ---------------------------------------------------------------------------
# Test 1 — Valid payload with correct token returns 200 and correct count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vectorize_logic_valid_payload_returns_stored_chunks_count():
    with patch(
        "services.skeleton_command_service.skeleton_command_service.ingest",
        new_callable=MagicMock,  # We'll return a coroutine manually or use AsyncMock
    ) as mock_ingest:
        # Mock as async
        mock_ingest.return_value = asyncio.Future()
        mock_ingest.return_value.set_result(3)

        response = client.post(
            "/api/vectorize",
            json=VALID_PAYLOAD,
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["chunks_stored"] == 3
    mock_ingest.assert_called_once()


# ---------------------------------------------------------------------------
# Test 2 — Missing Authorization header → 401
# ---------------------------------------------------------------------------


def test_vectorize_logic_missing_auth_header_returns_401():
    response = client.post("/api/vectorize", json=VALID_PAYLOAD)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Test 3 — Wrong token value → 401
# ---------------------------------------------------------------------------


def test_vectorize_logic_invalid_token_returns_401():
    response = client.post(
        "/api/vectorize",
        json=VALID_PAYLOAD,
        headers={"Authorization": "Bearer wrong-token-xyz"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Test 4 — Empty chunks list → 422 (Pydantic validation)
# ---------------------------------------------------------------------------


def test_vectorize_empty_chunks():
    payload = {**VALID_PAYLOAD, "chunks": []}
    response = client.post("/api/vectorize", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Test 5 — Wrong vector dimension → 422 (Pydantic validation)
# ---------------------------------------------------------------------------


def test_vectorize_wrong_vector_dimension():
    bad_chunk = {**VALID_CHUNK, "vector": [0.1, 0.2, 0.3]}  # only 3 floats, not 384
    payload = {**VALID_PAYLOAD, "chunks": [bad_chunk]}
    response = client.post("/api/vectorize", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422
    detail = response.json()
    assert "vector" in str(detail).lower() or "dimension" in str(detail).lower()


# ---------------------------------------------------------------------------
# Test 6 — Idempotency: posting the same path twice stores clean count
# ---------------------------------------------------------------------------


def test_vectorize_idempotency():
    call_counts = []

    async def fake_ingest(payload, **kwargs):
        call_counts.append(len(payload.chunks))
        return len(payload.chunks)

    with patch(
        "services.skeleton_command_service.skeleton_command_service.ingest",
        side_effect=fake_ingest,
    ):
        r1 = client.post("/api/vectorize", json=VALID_PAYLOAD, headers=AUTH_HEADERS)
        r2 = client.post("/api/vectorize", json=VALID_PAYLOAD, headers=AUTH_HEADERS)

    assert r1.status_code == 200
    assert r2.status_code == 200
    # Both calls should independently report the chunk count (upsert semantics)
    assert r1.json()["chunks_stored"] == 3
    assert r2.json()["chunks_stored"] == 3
    assert len(call_counts) == 2


# ---------------------------------------------------------------------------
# Test 7 — Service exception bubbles up as 500
# ---------------------------------------------------------------------------


def test_vectorize_service_error_returns_500():
    with patch(
        "services.skeleton_command_service.skeleton_command_service.ingest",
        side_effect=RuntimeError("DB connection failed"),
    ):
        response = client.post(
            "/api/vectorize",
            json=VALID_PAYLOAD,
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 500
    assert "error" in response.json()
