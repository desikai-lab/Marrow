import re

import config
import pytest
from fastapi.testclient import TestClient
from transport.rest.app import create_rest_app
from transport.rest.routers import code, tasks

pytestmark = pytest.mark.integration


def _routes(router):
    return sorted((method, route.path) for route in router.routes for method in route.methods)


TASK_ROUTES = _routes(tasks.router)
CODE_ROUTES = _routes(code.router)


@pytest.fixture()
def make_client(monkeypatch):
    def make(*disabled):
        monkeypatch.setattr(config, 'TASK_ENABLED', 'task' not in disabled)
        monkeypatch.setattr(config, 'CODE_ENABLED', 'code' not in disabled)
        return TestClient(create_rest_app(), raise_server_exceptions=False)

    return make


def _base(project):
    return f'/api/v1/projects/{project}'


def _concrete(path):
    return re.sub(r'\{[^}]+\}', 'X1', path)


def _operation_ids(spec):
    return {op['operationId'] for methods in spec['paths'].values() for op in methods.values()}


def _spec(client, project, keys, auth):
    response = client.get(f'{_base(project)}/openapi.json', headers=auth(keys['a']))
    assert response.status_code == 200
    return response.json()


def test_router_route_counts_match_the_tool_counts():
    assert len(TASK_ROUTES) == 5
    assert len(CODE_ROUTES) == 4


@pytest.mark.parametrize('method,path', TASK_ROUTES)
def test_task_group_off_every_task_route_returns_409(method, path, make_client, rest_project, keys, auth):
    url = f'{_base(rest_project)}{_concrete(path)}'
    response = make_client('task').request(method, url, headers=auth(keys['a']))
    assert response.status_code == 409
    assert response.json()['error']['type'] == 'ToolGroupDisabledError'


@pytest.mark.parametrize('method,path', CODE_ROUTES)
def test_code_group_off_every_code_route_returns_409(method, path, make_client, rest_project, keys, auth):
    url = f'{_base(rest_project)}{_concrete(path)}'
    response = make_client('code').request(method, url, headers=auth(keys['a']))
    assert response.status_code == 409
    assert response.json()['error']['type'] == 'ToolGroupDisabledError'


def test_disabled_response_names_the_group_and_no_environment_variable(make_client, rest_project, keys, auth):
    response = make_client('task').get(f'{_base(rest_project)}/tasks', headers=auth(keys['a']))
    body = response.json()
    assert body['error']['message'] == "The 'task' tool group is disabled on this server."
    assert body['error']['details'] == {'group': 'task'}
    assert body['request_id']
    assert 'TOOL_GROUP' not in response.text


def test_disabled_route_without_key_returns_uniform_401(make_client, rest_project):
    response = make_client('task').get(f'{_base(rest_project)}/tasks')
    assert response.status_code == 401
    assert response.json()['error']['type'] == 'Unauthorized'


def test_disabled_route_with_key_of_another_project_returns_401(make_client, rest_project, keys, auth):
    response = make_client('task').get(f'{_base(rest_project)}/tasks', headers=auth(keys['other']))
    assert response.status_code == 401


def test_malformed_body_on_disabled_route_returns_409_not_422(make_client, rest_project, keys, auth):
    headers = {**auth(keys['a']), 'content-type': 'application/json'}
    response = make_client('task').post(
        f'{_base(rest_project)}/tasks', content=b'{not json', headers=headers
    )
    assert response.status_code == 409


def test_enabled_group_stays_served_when_another_group_is_off(make_client, rest_project, keys, auth):
    client = make_client('code')
    assert client.get(f'{_base(rest_project)}/tasks', headers=auth(keys['a'])).status_code == 200
    assert client.get(f'{_base(rest_project)}/code/map', headers=auth(keys['a'])).status_code == 409


def test_openapi_task_group_off_omits_task_operations_and_schemas(make_client, rest_project, keys, auth):
    spec = _spec(make_client('task'), rest_project, keys, auth)
    ids = _operation_ids(spec)
    assert len(ids) == 16
    assert 'search_tasks' not in ids and 'search_code_skeletons' in ids
    assert 'AddTasksBody' not in spec['components']['schemas']


def test_openapi_code_group_off_omits_code_operations_and_schemas(make_client, rest_project, keys, auth):
    spec = _spec(make_client('code'), rest_project, keys, auth)
    ids = _operation_ids(spec)
    assert len(ids) == 17
    assert 'search_code_skeletons' not in ids and 'search_tasks' in ids
    assert 'CodeSearchBody' not in spec['components']['schemas']


def test_openapi_both_groups_off_keeps_the_12_core_operations(make_client, rest_project, keys, auth):
    spec = _spec(make_client('task', 'code'), rest_project, keys, auth)
    assert len(_operation_ids(spec)) == 12


def test_create_root_app_honours_the_flags(monkeypatch, rest_project, keys, auth):
    from transport.app_factory import create_root_app

    monkeypatch.setattr(config, 'CODE_ENABLED', False)
    client = TestClient(create_root_app(), raise_server_exceptions=False)
    response = client.get(f'{_base(rest_project)}/code/map', headers=auth(keys['a']))
    assert response.status_code == 409
