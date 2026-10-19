import pytest
from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel
from transport.rest.disabled import disabled_router_for
from utils.exceptions import BaseBacklogError


class _Body(BaseModel):
    n: int


def _real_router() -> APIRouter:
    router = APIRouter(tags=['tasks'])

    @router.get('/tasks')
    async def search_tasks(project: str, status: str = 'open'):
        return {}

    @router.post('/tasks')
    async def add_tasks(project: str, body: _Body):
        return {}

    @router.get('/tasks/{task_id}')
    async def get_task_details(project: str, task_id: str):
        return {}

    @router.patch('/tasks/{task_id}')
    async def update_task(project: str, task_id: str, body: _Body):
        return {}

    return router


def _app(router: APIRouter) -> FastAPI:
    app = FastAPI(openapi_url=None, generate_unique_id_function=lambda route: route.name)

    @app.exception_handler(BaseBacklogError)
    async def _domain(request, exc: BaseBacklogError):
        body = {'error': {'type': type(exc).__name__, 'message': exc.message}}
        if exc.details:
            body['error']['details'] = exc.details
        return JSONResponse(body, status_code=409)

    app.include_router(disabled_router_for(router, 'task'), prefix='/p/{project}')
    return app


@pytest.mark.parametrize(
    'method,path',
    [('get', '/tasks'), ('post', '/tasks'), ('get', '/tasks/T1'), ('patch', '/tasks/T1')],
)
def test_disabled_router_every_route_raises_disabled_error(method, path):
    response = getattr(TestClient(_app(_real_router())), method)(f'/p/Proj{path}')
    assert response.status_code == 409
    assert response.json()['error'] == {
        'type': 'ToolGroupDisabledError',
        'message': "The 'task' tool group is disabled on this server.",
        'details': {'group': 'task'},
    }
    assert 'TOOL_GROUP' not in response.text


def test_disabled_router_malformed_body_returns_disabled_error_not_validation_error():
    client = TestClient(_app(_real_router()))
    response = client.post(
        '/p/Proj/tasks', content=b'{not json', headers={'content-type': 'application/json'}
    )
    assert response.status_code == 409


def test_disabled_router_keeps_paths_methods_and_names_of_the_real_router():
    real = _real_router()
    stub = disabled_router_for(real, 'task')
    shape = lambda router: [(r.path, sorted(r.methods), r.name) for r in router.routes]  # noqa: E731
    assert shape(stub) == shape(real)
    assert list(stub.tags) == ['tasks']


def test_disabled_router_is_excluded_from_openapi():
    assert _app(_real_router()).openapi()['paths'] == {}


def test_disabled_router_unrelated_method_still_returns_405():
    response = TestClient(_app(_real_router())).delete('/p/Proj/tasks')
    assert response.status_code == 405
