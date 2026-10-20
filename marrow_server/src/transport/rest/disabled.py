"""Stub routers answering HTTP 409 for a disabled tool group (F4000302, ADR-0055)."""

from fastapi import APIRouter, Request
from fastapi.routing import APIRoute
from utils.exceptions import ToolGroupDisabledError


def group_disabled_message(group: str) -> str:
    return f"The '{group}' tool group is disabled on this server."


def disabled_router_for(router: APIRouter, group: str) -> APIRouter:
    """Clone path, methods and name of every route onto a handler that raises.

    The stub declares no body or query parameters, so no 422 can leak the real schema,
    and it is excluded from OpenAPI. App-level authentication still runs first.
    """

    async def _disabled(request: Request) -> None:
        raise ToolGroupDisabledError(group_disabled_message(group), {"group": group})

    stub = APIRouter(tags=list(router.tags))
    for route in router.routes:
        if isinstance(route, APIRoute):
            stub.add_api_route(
                route.path,
                _disabled,
                methods=sorted(route.methods),
                name=route.name,
                include_in_schema=False,
            )
    return stub
