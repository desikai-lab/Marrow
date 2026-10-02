import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from transport.rest.errors import RestAuthError, register_error_handlers
from utils import exceptions as exc


class _Body(BaseModel):
    n: int


def _client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/domain/{name}")
    async def domain(name: str):
        raise getattr(exc, name)("boom", {"line": 3})

    @app.get("/auth")
    async def auth():
        raise RestAuthError()

    @app.post("/body")
    async def body(b: _Body):
        return {}

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    "name,status",
    [
        ("InvalidPathError", 400),
        ("ProjectNotFoundError", 404),
        ("TaskNotFoundError", 404),
        ("ArtifactNotFoundError", 404),
        ("DomainProtectionError", 409),
        ("SourceAccessDisabledError", 409),
        ("ValidationError", 422),
        ("SourceFileError", 422),
        ("StorageTimeoutError", 503),
    ],
)
def test_domain_error_maps_to_status_and_envelope(name, status):
    r = _client().get(f"/domain/{name}")
    assert r.status_code == status
    assert r.json()["error"] == {"type": name, "message": "boom", "details": {"line": 3}}
    assert r.json()["request_id"] == "-"
    assert (r.headers.get("retry-after") == "1") == (status == 503)


def test_auth_error_returns_uniform_401_with_bearer_challenge():
    r = _client().get("/auth")
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
    assert r.json()["error"] == {
        "type": "Unauthorized",
        "message": "Invalid or missing credentials.",
    }


def test_request_validation_error_returns_422_without_input_echo():
    r = _client().post("/body", json={"n": "secret-value"})
    assert r.status_code == 422 and "secret-value" not in r.text
    assert r.json()["error"]["type"] == "ValidationError"


def test_unknown_path_returns_404_envelope():
    r = _client().get("/nope")
    assert r.status_code == 404 and r.json()["error"]["type"] == "NotFound"


def test_wrong_method_returns_405_envelope():
    r = _client().delete("/auth")
    assert r.status_code == 405 and r.json()["error"]["type"] == "MethodNotAllowed"
