from fastapi import FastAPI

from transport.rest.paths import PROJECT_PREFIX
from transport.rest.routers.context import router


def use_session_routes(app: FastAPI) -> None:
    """Serve the session-context REST routes (core, always on)."""
    app.include_router(router, prefix=PROJECT_PREFIX)
