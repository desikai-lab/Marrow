from fastapi import FastAPI

from transport.rest.paths import PROJECT_PREFIX
from transport.rest.routers.tasks import router


def use_task_routes(app: FastAPI) -> None:
    """Serve the task REST routes."""
    app.include_router(router, prefix=PROJECT_PREFIX)
