"""TOOL_GROUP_CODE_ENABLED also gates the marrow_worker ingestion endpoint (F4000302)."""

import config
from fastapi import FastAPI
from fastapi.testclient import TestClient

from transport.vectorize_router import build_vectorize_router


def _client(monkeypatch, enabled: bool) -> TestClient:
    monkeypatch.setattr(config, "CODE_ENABLED", enabled)
    app = FastAPI()
    app.include_router(build_vectorize_router())
    return TestClient(app, raise_server_exceptions=False)


def test_vectorize_routes_served_when_code_group_enabled(monkeypatch):
    client = _client(monkeypatch, True)
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths["/api/vectorize"]) == {"post", "delete"}


def test_vectorize_post_answers_409_when_code_group_disabled(monkeypatch):
    client = _client(monkeypatch, False)
    response = client.post("/api/vectorize", json={})
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["type"] == "ToolGroupDisabledError"
    assert error["message"] == "The 'code' tool group is disabled on this server."
    assert error["details"] == {"group": "code"}
    assert "TOOL_GROUP" not in error["message"]
    assert "request_id" in response.json()


def test_vectorize_delete_answers_409_when_code_group_disabled(monkeypatch):
    client = _client(monkeypatch, False)
    response = client.delete("/api/vectorize")
    assert response.status_code == 409
    assert response.json()["error"]["type"] == "ToolGroupDisabledError"


def test_vectorize_disabled_hidden_from_openapi(monkeypatch):
    client = _client(monkeypatch, False)
    assert "/api/vectorize" not in client.get("/openapi.json").json()["paths"]
