from fastapi import APIRouter

from transport.rest.routers import context

ROUTERS: list[APIRouter] = [context.router]
