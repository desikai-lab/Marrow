import asyncio

from mcp_core import mcp
from transport.rest.app import rest_app
from transport.rest.exclusions import REST_EXCLUSIONS

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _mcp_params() -> dict[str, set[str]]:
    tools = asyncio.run(mcp.list_tools())
    return {t.name: set(t.inputSchema.get("properties", {})) for t in tools}


def _resolve(spec, schema):
    ref = schema.get("$ref")
    return spec["components"]["schemas"][ref.split("/")[-1]] if ref else schema


def _rest_operations() -> dict[str, set[str]]:
    spec = rest_app.openapi()
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
