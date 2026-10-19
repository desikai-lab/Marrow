import asyncio
from itertools import combinations

import config
import pytest
from mcp.server.fastmcp import FastMCP
from mcp_core import mcp
from transport.rest.app import create_rest_app, rest_app
from transport.rest.exclusions import REST_EXCLUSIONS
from transport.tool_registry import register_tools

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _mcp_params(server=mcp) -> dict[str, set[str]]:
    tools = asyncio.run(server.list_tools())
    return {t.name: set(t.inputSchema.get("properties", {})) for t in tools}


def _resolve(spec, schema):
    ref = schema.get("$ref")
    return spec["components"]["schemas"][ref.split("/")[-1]] if ref else schema


def _rest_operations(app=rest_app) -> dict[str, set[str]]:
    spec = app.openapi()
    found = {}
    for methods in spec["paths"].values():
        for method, op in methods.items():
            if method not in HTTP_METHODS:
                continue
            names = {p["name"] for p in op.get("parameters", [])}
            body = (
                op.get("requestBody", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema")
            )
            if body:
                names |= set(_resolve(spec, body).get("properties", {}))
            found[op["operationId"]] = names
    return found


def test_every_mcp_tool_is_bound_to_rest_or_explicitly_excluded():
    assert set(_mcp_params()) - set(_rest_operations()) - set(REST_EXCLUSIONS) == set()


def test_rest_has_no_operation_without_an_mcp_tool():
    assert set(_rest_operations()) - set(_mcp_params()) == set()


def test_exclusions_name_registered_tools_and_are_not_bound():
    assert set(REST_EXCLUSIONS) <= set(_mcp_params())
    assert not set(REST_EXCLUSIONS) & set(_rest_operations())


def test_rest_parameter_names_equal_mcp_parameter_names_per_operation():
    rest, tools = _rest_operations(), _mcp_params()
    assert {n: (sorted(rest[n]), sorted(tools[n])) for n in rest if rest[n] != tools[n]} == {}


def test_rest_exposes_exactly_21_operations():
    assert len(_rest_operations()) == 21


FLAG_OF = {'code': 'CODE_ENABLED', 'task': 'TASK_ENABLED', 'build': 'BUILD_ENABLED'}
COMBINATIONS = [
    frozenset(combo) for size in range(4) for combo in combinations(sorted(FLAG_OF), size)
]
GROUP_OF_EXCLUSION = {
    'list_projects': 'project',
    'init_project': 'project',
    'run_project_build': 'build',
}


def _ids(disabled):
    return '+'.join(sorted(disabled)) or 'none'


def _surfaces(monkeypatch, disabled):
    for group, flag in FLAG_OF.items():
        monkeypatch.setattr(config, flag, group not in disabled)
    server = FastMCP('parity-flags-test')
    register_tools(server)
    return _mcp_params(server), _rest_operations(create_rest_app())


@pytest.mark.parametrize('disabled', COMBINATIONS, ids=_ids)
def test_rest_operations_group_off_equal_mcp_minus_configured_exclusions(monkeypatch, disabled):
    tools, rest = _surfaces(monkeypatch, disabled)
    assert set(tools) - set(rest) - set(REST_EXCLUSIONS) == set()
    assert set(rest) - set(tools) == set()


@pytest.mark.parametrize('disabled', COMBINATIONS, ids=_ids)
def test_rest_operation_count_group_off_equals_21_minus_disabled_rest_ops(monkeypatch, disabled):
    _, rest = _surfaces(monkeypatch, disabled)
    expected = 21
    expected -= 5 if 'task' in disabled else 0
    expected -= 4 if 'code' in disabled else 0
    assert len(rest) == expected


@pytest.mark.parametrize('disabled', COMBINATIONS, ids=_ids)
def test_exclusions_naming_unregistered_tool_require_disabled_group(monkeypatch, disabled):
    tools, _ = _surfaces(monkeypatch, disabled)
    unregistered = set(REST_EXCLUSIONS) - set(tools)
    assert unregistered == {n for n, g in GROUP_OF_EXCLUSION.items() if g in disabled}


@pytest.mark.parametrize('disabled', COMBINATIONS, ids=_ids)
def test_rest_parameter_names_equal_mcp_parameter_names_group_off(monkeypatch, disabled):
    tools, rest = _surfaces(monkeypatch, disabled)
    assert {n: (sorted(rest[n]), sorted(tools[n])) for n in rest if rest[n] != tools[n]} == {}
