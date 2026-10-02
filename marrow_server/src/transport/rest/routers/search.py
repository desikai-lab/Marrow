from fastapi import APIRouter, Request
from operations import artifacts as ops

from transport.rest.envelope import ok
from transport.rest.schemas import SemanticSearchBody, TextSearchBody

router = APIRouter(tags=["search"])


@router.post("/search/semantic")
async def semantic_search(request: Request, project: str, body: SemanticSearchBody):
    return ok(request, await ops.semantic_search(project, body.query, body.limit, body.scopes))


@router.post("/search/text")
async def search_project_artifacts(request: Request, project: str, body: TextSearchBody):
    return ok(request, await ops.search_project_artifacts(project, body.query))
