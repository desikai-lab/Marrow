import logging
import os

from common.path_resolver import ResourceKind, get_dir_path
from common.project_file_error import ProjectFileError
from config import PROJECTS_ROOT
from domain.responses import ArtifactSectionResult, TaskSemanticResult
from tools.artifacts import read_project_artifact_logic_async
from tools.utils.filesystem_utils import resolve_artifact_project_path
from utils.exceptions import ProjectNotFoundError

logger = logging.getLogger(__name__)


async def semantic_search_tasks_logic(
    project: str, query: str, limit: int = 5
) -> list[TaskSemanticResult]:
    """
    [EXPERIMENTAL] Semantic task search via vector embeddings.
    """

    project_root = os.path.join(PROJECTS_ROOT, project)
    if not os.path.exists(project_root):
        raise ProjectNotFoundError(f"Project '{project}' not found")

    try:
        # 1-2. Generate vector and search in LanceDB via repository
        from storage.uow import UnitOfWork

        uow = UnitOfWork(project_root)
        results = await uow.tasks.semantic_search(query, limit)

        # 3. Format result
        return [
            TaskSemanticResult(
                key=r["record"].key,
                title=r["record"].title,
                status=r["record"].status,
                score=r["distance"],
            )
            for r in results
        ]
    except Exception:
        raise


async def _hydrate_hit_content(project: str, r: dict) -> None:
    """Populate r['content'] (success) or r['warning'] (failure) in place for one
    search hit. Never echoes exception text into `warning` -- only the hit's own
    relative path, already public via r['path'] (why sanitize_error_message() is
    not used)."""
    try:
        project_path = resolve_artifact_project_path(project, r["path"])
    except ProjectFileError:
        r["warning"] = f"Source file no longer resolvable at path: {r['path']}."
        return

    if not await project_path.exists_async():
        r["warning"] = f"Source file no longer exists at path: {project_path.relative_path}."
        return

    try:
        r["content"] = await read_project_artifact_logic_async(
            project_path,
            mode="lines",
            start_line=r["start_line"],
            end_line=r["end_line"],
        )
    except Exception as e:
        r["warning"] = f"Could not read content: {project_path.relative_path}"
        logger.warning("content-hydration failed for %s: %s", project_path.relative_path, e)


async def search_artifact_sections_logic(
    project: str, query: str, limit: int = 5, include_content: bool = True
) -> list[ArtifactSectionResult]:
    """Semantic search by artifact sections (chunks) (ASV-7). With include_content,
    each hit also carries the live file text at [start_line, end_line]; a hit whose
    file cannot be read gets content=None plus a warning (partial success)."""
    from storage.uow import UnitOfWork

    if not await get_dir_path(project, "", ResourceKind.ROOT).exists_async():
        raise ProjectNotFoundError(f"Project '{project}' not found")

    uow = UnitOfWork.for_project(project)
    results = await uow.chunks.semantic_search(query, limit)
    if include_content:
        for r in results:
            await _hydrate_hit_content(project, r)
    return [ArtifactSectionResult(**r) for r in results]
