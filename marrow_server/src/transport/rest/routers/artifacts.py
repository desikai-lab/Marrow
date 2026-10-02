from fastapi import APIRouter, Request
from operations import artifacts as ops

from transport.rest.envelope import ok
from transport.rest.schemas import (
    MoveArtifactBody,
    ReadArtifactsBody,
    RestoreArtifactBody,
    WriteArtifactsBody,
)

router = APIRouter(tags=["artifacts"])


@router.get("/artifacts")
async def list_project_artifacts(
    request: Request, project: str, path: str = "", recursive: bool = False
):
    return ok(request, await ops.list_project_artifacts(project, path, recursive))


@router.post("/artifacts/read")
async def read_project_artifacts(request: Request, project: str, body: ReadArtifactsBody):
    return ok(request, await ops.read_project_artifacts(project, body.reads))


@router.post("/artifacts/write")
async def save_project_artifacts(request: Request, project: str, body: WriteArtifactsBody):
    return ok(request, await ops.save_project_artifacts(project, body.updates))


@router.get("/artifacts/outline")
async def get_project_artifact_outline(request: Request, project: str, path: str):
    return ok(request, await ops.get_project_artifact_outline(project, path))


@router.post("/artifacts/move")
async def move_project_artifact(request: Request, project: str, body: MoveArtifactBody):
    return ok(request, await ops.move_project_artifact(project, body.src_path, body.dest_path))


@router.delete("/artifacts")
async def delete_project_artifact(request: Request, project: str, path: str):
    return ok(request, await ops.delete_project_artifact(project, path))


@router.get("/artifacts/history")
async def list_artifact_history(request: Request, project: str, path: str):
    return ok(request, await ops.list_artifact_history(project, path))


@router.post("/artifacts/restore")
async def restore_project_artifact(request: Request, project: str, body: RestoreArtifactBody):
    return ok(request, await ops.restore_project_artifact(project, body.path, body.backup_name))
