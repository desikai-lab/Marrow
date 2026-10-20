import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from flag_matrix import combinations_of, ids, set_flags
from transport.rest.route_registry import register_routes
from transport.rest.routers import code, tasks
from utils.exceptions import BaseBacklogError

GROUP_ROUTERS = {"task": tasks.router, "code": code.router}
REST_GROUPS = ("code", "task")
COMBINATIONS = combinations_of(REST_GROUPS)


def _app(monkeypatch, disabled) -> FastAPI:
    set_flags(monkeypatch, disabled, REST_GROUPS)
    app = FastAPI(generate_unique_id_function=lambda route: route.name)

    @app.exception_handler(BaseBacklogError)
    async def _domain(request, exc: BaseBacklogError):
        return JSONResponse({"error": {"type": type(exc).__name__}}, status_code=409)

    register_routes(app)
    return app


def _operations(app: FastAPI) -> set[str]:
    spec = app.openapi()
    return {op["operationId"] for methods in spec["paths"].values() for op in methods.values()}


def _group_operations(group: str) -> set[str]:
    return {route.name for route in GROUP_ROUTERS[group].routes}


def _group_routes(group: str) -> list[tuple[str, str]]:
    return sorted((m, r.path) for r in GROUP_ROUTERS[group].routes for m in r.methods)


def _concrete(path: str) -> str:
    return "/api/v1/projects/P" + path.replace("{task_id}", "T1")


def test_register_routes_all_groups_enabled_lists_every_group_operation_in_openapi(monkeypatch):
    operations = _operations(_app(monkeypatch, frozenset()))
    for group in REST_GROUPS:
        assert _group_operations(group) and _group_operations(group) <= operations


@pytest.mark.parametrize("disabled", COMBINATIONS, ids=ids)
def test_register_routes_group_off_removes_exactly_that_groups_operations(monkeypatch, disabled):
    expected = _operations(_app(monkeypatch, frozenset()))
    for group in disabled:
        expected -= _group_operations(group)
    assert _operations(_app(monkeypatch, disabled)) == expected


@pytest.mark.parametrize("disabled", COMBINATIONS, ids=ids)
def test_register_routes_group_off_answers_409_for_every_route_of_that_group(monkeypatch, disabled):
    client = TestClient(_app(monkeypatch, disabled), raise_server_exceptions=False)
    for group in disabled:
        routes = _group_routes(group)
        assert routes
        for method, path in routes:
            assert client.request(method, _concrete(path)).status_code == 409, (method, path)
