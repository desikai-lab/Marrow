from fastapi import FastAPI
from fastapi.testclient import TestClient
from transport.rest.errors import register_error_handlers
from transport.rest.middleware import (
    AccessLogMiddleware,
    BodyLimitMiddleware,
    ConcurrencyLimitMiddleware,
)


def _client(max_bytes=10) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/ok")
    async def ok():
        return {"fine": True}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret-detail")

    @app.post("/echo")
    async def echo(payload: dict):
        return payload

    app.add_middleware(BodyLimitMiddleware, max_bytes=max_bytes)
    app.add_middleware(AccessLogMiddleware)
    return TestClient(app, raise_server_exceptions=False)


def test_access_log_adds_eight_char_request_id_header():
    assert len(_client().get("/ok").headers["x-request-id"]) == 8


def test_unhandled_exception_returns_500_envelope_without_traceback():
    r = _client().get("/boom")
    assert r.status_code == 500 and "Traceback" not in r.text
    assert r.json()["error"]["type"] == "SystemError"
    assert r.json()["request_id"] == r.headers["x-request-id"]


def test_body_limit_content_length_over_cap_returns_413():
    r = _client().post("/echo", content=b"x" * 50, headers={"content-type": "application/json"})
    assert r.status_code == 413 and r.json()["error"]["type"] == "PayloadTooLarge"
    assert r.json()["request_id"] == r.headers["x-request-id"]


def test_body_limit_small_body_passes():
    assert _client().post("/echo", json={"a": 1}).status_code == 200


async def test_concurrency_limit_saturated_returns_503_with_retry_after():
    sent = []

    async def downstream(scope, receive, send):
        raise AssertionError("must not run")

    async def send(message):
        sent.append(message)

    mw = ConcurrencyLimitMiddleware(downstream, limit=1)
    await mw._sem.acquire()
    await mw({"type": "http", "state": {"request_id": "abcd1234"}}, None, send)
    assert sent[0]["status"] == 503 and (b"retry-after", b"1") in sent[0]["headers"]
