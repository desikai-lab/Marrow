from fastapi import APIRouter

from transport.rest.routers import artifacts, context, search, tasks

ROUTERS: list[APIRouter] = [context.router, tasks.router, search.router, artifacts.router]
