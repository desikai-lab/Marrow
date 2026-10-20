"""The vectorize stub and the REST group stub must answer the same 409 envelope (F4000302 T8).

Both stubs are exercised behind an app-level authentication dependency that is overridden
to a no-op, so the comparison needs no project, key store or filesystem state. `request_id`
is deliberately not compared: the two stubs sit behind different middleware stacks.
"""

import config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from transport.rest.app import create_rest_app
from transport.rest.auth import authenticate_project_key
from transport.vectorize_router import build_vectorize_router


async def _no_auth() -> None:
    return None


def _vectorize_response(monkeypatch):
    monkeypatch.setattr(config, "CODE_ENABLED", False)
    app = FastAPI()
    app.include_router(build_vectorize_router())
    return TestClient(app, raise_server_exceptions=False).post("/api/vectorize", json={})


def test_vectorize_stub_envelope_equals_rest_stub_envelope_for_code_group(monkeypatch):
    vectorize = _vectorize_response(monkeypatch)

    monkeypatch.setattr(config, "CODE_ENABLED", False)
    app = create_rest_app()
    app.dependency_overrides[authenticate_project_key] = _no_auth
    rest = TestClient(app, raise_server_exceptions=False).get(
        "/api/v1/projects/AnyProject/code/map"
    )

    assert vectorize.status_code == rest.status_code == 409
    assert vectorize.json()["error"] == rest.json()["error"]
