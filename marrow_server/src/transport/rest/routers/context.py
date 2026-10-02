from fastapi import APIRouter, Request
from operations import context as ops

from transport.rest.envelope import ok

router = APIRouter(tags=["context"])


@router.get("/session-context")
async def get_session_context(request: Request, project: str, start_role: str | None = None):
    return ok(request, await ops.get_session_context(project, start_role))


@router.get("/guidelines/{role}")
async def get_guideline(request: Request, project: str, role: str):
    return ok(request, await ops.get_guideline(project, role))
