import asyncio
from typing import Any

from services.skeleton_query_service import (
    get_file_skeleton_logic,
    get_project_map_logic,
    search_code_skeletons_logic,
)
from tools import view_file_source_logic


async def view_file_source(
    project: str, path: str, start_line: int, end_line: int
) -> str | dict[str, Any]:
    return await asyncio.to_thread(view_file_source_logic, project, path, start_line, end_line)


async def search_code_skeletons(
    project: str,
    query: str,
    chunk_type: str | None = None,
    limit: int = 10,
    include_tests: bool = False,
    root_path: str | None = None,
) -> list[dict[str, Any]]:
    results = await search_code_skeletons_logic(
        project,
        query,
        chunk_type=chunk_type,
        limit=limit,
        include_tests=include_tests,
        root_path=root_path,
    )
    return [r.model_dump() for r in results]


async def get_file_skeleton(
    project: str, path: str, depth: int = 2, summary_only: bool = False
) -> list[dict[str, Any]]:
    results = await get_file_skeleton_logic(project, path, depth=depth, summary_only=summary_only)
    return [r.model_dump() for r in results]


async def get_project_map(
    project: str, depth: int = 4, include_tests: bool = False
) -> dict[str, Any]:
    result = await get_project_map_logic(project, depth=depth, include_tests=include_tests)
    return result.model_dump()
