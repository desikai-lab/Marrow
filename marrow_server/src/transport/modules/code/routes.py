from fastapi import FastAPI

from transport.rest.paths import PROJECT_PREFIX
from transport.rest.routers.code import router


def use_code_routes(app: FastAPI) -> None:
    """Serve the code REST routes."""
    app.include_router(router, prefix=PROJECT_PREFIX)
