import asyncio
from typing import Any

from domain.responses import EmptyArtifactsResult
from models import ReadRequest, WriteRequest
from services.artifact_command_service import save_project_artifacts_logic
from services.artifact_query_service import search_artifact_sections_logic
from tools import (
    delete_project_artifact_logic,
    get_project_artifact_outline_logic,
    list_artifact_history_logic,
    list_artifacts_logic,
    move_project_artifact_logic,
    read_project_artifacts_logic,
    restore_project_artifact_logic,
    search_project_artifacts_logic,
)


def _to_request_dict(item: ReadRequest | WriteRequest) -> dict[str, Any]:
    data = item.model_dump()
    extra = data.pop("extra_fields", {})
    if extra:
        data.update(extra)
    return data


async def semantic_search(
    project: str, query: str, limit: int = 5, scopes: list[str] | None = None
) -> Any:
    results = await search_artifact_sections_logic(project, query, limit, scopes=scopes)
    if isinstance(results, EmptyArtifactsResult):
        return results.model_dump()
    return [r.model_dump() for r in results]


async def read_project_artifacts(project: str, reads: list[ReadRequest]) -> list[dict[str, Any]]:
    payload = [_to_request_dict(r) for r in reads]
    return await asyncio.to_thread(read_project_artifacts_logic, project, payload)


async def save_project_artifacts(project: str, updates: list[WriteRequest]) -> list[dict[str, Any]]:
    payload = []
    for u in updates:
        d = _to_request_dict(u)
        d["_explicit_fields"] = set(u.model_fields_set)
        payload.append(d)
    results = await save_project_artifacts_logic(project, payload)
    return [r.model_dump() for r in results]


async def list_project_artifacts(
    project: str, path: str = "", recursive: bool = False
) -> list[dict[str, str]]:
    return await asyncio.to_thread(list_artifacts_logic, project, path, recursive=recursive)


async def move_project_artifact(
    project: str, src_path: str, dest_path: str
) -> str | dict[str, Any]:
    return await move_project_artifact_logic(project, src_path, dest_path)


async def delete_project_artifact(project: str, path: str) -> str | dict[str, Any]:
    return await delete_project_artifact_logic(project, path)


async def search_project_artifacts(project: str, query: str) -> list[dict[str, Any]]:
    return await search_project_artifacts_logic(project, query)


async def get_project_artifact_outline(project: str, path: str) -> str | dict[str, Any]:
    return await asyncio.to_thread(get_project_artifact_outline_logic, project, path)


async def list_artifact_history(project: str, path: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(list_artifact_history_logic, project, path)


async def restore_project_artifact(
    project: str, path: str, backup_name: str
) -> str | dict[str, Any]:
    return await asyncio.to_thread(restore_project_artifact_logic, project, path, backup_name)
