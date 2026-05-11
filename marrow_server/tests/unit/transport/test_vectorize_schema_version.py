"""
tests/unit/transport/test_vectorize_schema_version.py
Tests for ADR-23 schema version enforcement.
"""
import pytest
from fastapi.testclient import TestClient

from transport.app_factory import app
from config import SECRET_TOKEN, EMBEDDING_DIMENSIONS
from marrow_common.skeleton_schema import SCHEMA_VERSION

client = TestClient(app, raise_server_exceptions=False)

AUTH_HEADERS = {"Authorization": f"Bearer {SECRET_TOKEN}"}

def valid_vectorize_payload(schema_version: str = SCHEMA_VERSION):
    payload = {
        "project_name": "TestProject",
        "path": "src/App.cs",
        "file_summary": "Test Summary",
        "chunks": [
            {
                "type": "class",
                "name": "App",
                "skeleton_text": "class App {}",
                "vector": [0.1] * EMBEDDING_DIMENSIONS,
                "line_start": 1,
                "line_end": 10,
            }
        ],
    }
    if schema_version is not None:
        payload["schema_version"] = schema_version
    return payload

def test_schema_version_mismatch_returns_422():
    payload = valid_vectorize_payload(schema_version="0.9")
    response = client.post("/api/vectorize", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "schema_version_mismatch"
    assert body["expected"] == SCHEMA_VERSION
    assert body["received"] == "0.9"

@pytest.mark.asyncio
async def test_schema_version_match_succeeds():
    payload = valid_vectorize_payload(schema_version=SCHEMA_VERSION)
    from unittest.mock import patch, MagicMock
    import asyncio
    with patch(
        "services.skeleton_command_service.skeleton_command_service.ingest",
        new_callable=MagicMock,
    ) as mock_ingest:
        mock_ingest.return_value = asyncio.Future()
        mock_ingest.return_value.set_result(1)
        
        response = client.post("/api/vectorize", json=payload, headers=AUTH_HEADERS)
    
    assert response.status_code == 200

def test_missing_schema_version_returns_422():
    payload = valid_vectorize_payload(schema_version=None)
    response = client.post("/api/vectorize", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422
    # Standard Pydantic error
    body = response.json()
    assert "detail" in body
    assert any(err["loc"] == ["body", "schema_version"] for err in body["detail"])
