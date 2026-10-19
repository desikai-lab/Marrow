import config
from fastapi import FastAPI

from transport.rest.disabled import disabled_router_for
from transport.rest.paths import PROJECT_PREFIX
from transport.rest.routers.tasks import router


def use_task_routes(app: FastAPI) -> None:
    """Serve the task REST routes; HTTP 409 stubs when TOOL_GROUP_TASK_ENABLED=false."""
    if config.TASK_ENABLED:
        app.include_router(router, prefix=PROJECT_PREFIX)
    else:
        app.include_router(disabled_router_for(router, "task"), prefix=PROJECT_PREFIX)
