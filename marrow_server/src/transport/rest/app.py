"""REST sub-application (ADR-0053). Sibling of the legacy MCP app; never wrapped by its middleware."""

import config
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from transport.rest.auth import authenticate_project_key
from transport.rest.errors import register_error_handlers
from transport.rest.middleware import (
    AccessLogMiddleware,
    BodyLimitMiddleware,
    ConcurrencyLimitMiddleware,
)
from transport.rest.routers import ROUTERS

API_PREFIX = "/api/v1"
PROJECT_PREFIX = f"{API_PREFIX}/projects/{{project}}"


def _operation_id(route: APIRoute) -> str:
    return route.name


def create_rest_app() -> FastAPI:
    app = FastAPI(
        title="Marrow REST API",
        version="1.0.0",
        dependencies=[Depends(authenticate_project_key)],
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        generate_unique_id_function=_operation_id,
    )
    register_error_handlers(app)
    for router in ROUTERS:
        app.include_router(router, prefix=PROJECT_PREFIX)
    app.add_middleware(BodyLimitMiddleware, max_bytes=config.REST_MAX_BODY_BYTES)
    app.add_middleware(ConcurrencyLimitMiddleware, limit=config.REST_MAX_CONCURRENCY)
    if config.REST_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.REST_CORS_ORIGINS,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )
    app.add_middleware(AccessLogMiddleware)
    return app


rest_app = create_rest_app()
