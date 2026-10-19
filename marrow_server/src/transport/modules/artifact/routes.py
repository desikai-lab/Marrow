from fastapi import FastAPI

from transport.rest.paths import PROJECT_PREFIX
from transport.rest.routers.artifacts import router as artifacts_router
from transport.rest.routers.search import router as search_router


def use_artifact_routes(app: FastAPI) -> None:
    """Serve the artifact, history and search REST routes (core, always on)."""
    app.include_router(artifacts_router, prefix=PROJECT_PREFIX)
    app.include_router(search_router, prefix=PROJECT_PREFIX)
