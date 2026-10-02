from fastapi import APIRouter

from transport.rest.routers import artifacts, code, context, meta, search, tasks

ROUTERS: list[APIRouter] = [
    context.router,
    tasks.router,
    search.router,
    artifacts.router,
    code.router,
    meta.router,
]
