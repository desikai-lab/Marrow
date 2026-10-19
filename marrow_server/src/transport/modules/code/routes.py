import config
from fastapi import FastAPI

from transport.rest.disabled import disabled_router_for
from transport.rest.paths import PROJECT_PREFIX
from transport.rest.routers.code import router


def use_code_routes(app: FastAPI) -> None:
    """Serve the code REST routes; HTTP 409 stubs when TOOL_GROUP_CODE_ENABLED=false."""
    if config.CODE_ENABLED:
        app.include_router(router, prefix=PROJECT_PREFIX)
    else:
        app.include_router(disabled_router_for(router, "code"), prefix=PROJECT_PREFIX)
