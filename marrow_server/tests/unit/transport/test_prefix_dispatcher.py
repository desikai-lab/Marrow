import config
import pytest
from fastapi import FastAPI
from transport import app_factory
from transport.app_factory import PrefixDispatcher


def _recorder(name, calls):
    async def app(scope, receive, send):
        calls.append(name)

    return app


@pytest.mark.parametrize(
    "path,expected",
    [
        ("/api/v1", "rest"),
        ("/api/v1/projects/P/tasks", "rest"),
        ("/api/v10/x", "legacy"),
        ("/api/vectorize", "legacy"),
        ("/mcp", "legacy"),
        ("/", "legacy"),
    ],
)
async def test_dispatcher_http_path_routes_to_expected_app(path, expected):
    calls = []
    d = PrefixDispatcher(_recorder("rest", calls), _recorder("legacy", calls))
    await d({"type": "http", "path": path}, None, None)
    assert calls == [expected]


async def test_dispatcher_lifespan_scope_goes_to_legacy_app():
    calls = []
    d = PrefixDispatcher(_recorder("rest", calls), _recorder("legacy", calls))
    await d({"type": "lifespan"}, None, None)
    assert calls == ["legacy"]


def test_create_root_app_rest_enabled_returns_dispatcher(monkeypatch):
    monkeypatch.setattr(config, "REST_API_ENABLED", True)
    assert isinstance(app_factory.create_root_app(), PrefixDispatcher)


def test_create_root_app_rest_disabled_returns_legacy_fastapi_app(monkeypatch):
    monkeypatch.setattr(config, "REST_API_ENABLED", False)
    assert isinstance(app_factory.create_root_app(), FastAPI)
