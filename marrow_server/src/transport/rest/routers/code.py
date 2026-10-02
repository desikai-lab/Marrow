from fastapi import APIRouter, Request
from operations import code_intel as ops

from transport.rest.envelope import ok
from transport.rest.schemas import CodeSearchBody

router = APIRouter(tags=["code"])


@router.post("/code/search")
async def search_code_skeletons(request: Request, project: str, body: CodeSearchBody):
    results = await ops.search_code_skeletons(
        project, body.query, body.chunk_type, body.limit, body.include_tests, body.root_path
    )
    return ok(request, results)


@router.get("/code/skeleton")
async def get_file_skeleton(
    request: Request, project: str, path: str, depth: int = 2, summary_only: bool = False
):
    return ok(request, await ops.get_file_skeleton(project, path, depth, summary_only))


@router.get("/code/map")
async def get_project_map(
    request: Request, project: str, depth: int = 4, include_tests: bool = False
):
    return ok(request, await ops.get_project_map(project, depth, include_tests))


@router.get("/code/source")
async def view_file_source(
    request: Request, project: str, path: str, start_line: int, end_line: int
):
    return ok(request, await ops.view_file_source(project, path, start_line, end_line))
