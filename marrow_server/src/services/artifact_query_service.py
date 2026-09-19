import logging
import os

from common.path_resolver import ResourceKind, get_dir_path
from common.project_file_error import ProjectFileError
from config import PROJECTS_ROOT
from domain.responses import ArtifactSectionResult, EmptyArtifactsResult, TaskSemanticResult
from tools.artifacts import read_project_artifact_logic_async
from tools.utils.filesystem_utils import resolve_artifact_project_path
from utils.exceptions import InvalidPathError, ProjectNotFoundError

MAX_SCOPES = 20
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


def _normalize_scopes(scopes: list[str]) -> list[str]:
    """Pure string cleanup for caller-supplied scopes: strips surrounding
    whitespace, converts '\\' to '/' (defends a Windows-style client input
    even though storage is POSIX per OQ6), and drops one trailing '/'. Does
    not check validity and never raises -- that is _validate_scopes's job,
    not this function's. Must run before _validate_scopes (see Task 4's note
    on call order in implementation_plan_part2.md).
    """
    return [scope.strip().replace("\\", "/").rstrip("/") for scope in scopes]


def _validate_scopes(project: str, scopes: list[str]) -> None:
    """Validates already-normalized scopes (REQ-04, REQ-05): rejects more than
    MAX_SCOPES, an empty scope, or a scope that escapes the project's artifacts
    root (traversal, absolute path). Pure validation only -- never mutates
    `scopes` and never returns a transformed value; call _normalize_scopes
    first and pass its output here. Raises InvalidPathError, never leaking a
    host path (REQ-05), on failure; returns None on success.

    No special handling for a scope that happens to be a file path (Open
    Question #9, resolved): it is validated like any other directory-shaped
    string, then matches zero chunks downstream and falls through to the
    REQ-07 EmptyArtifactsResult, which itself tells the caller scopes are
    directories.
    """
    if len(scopes) > MAX_SCOPES:
        raise InvalidPathError(f"Too many scopes: {len(scopes)} supplied, maximum is {MAX_SCOPES}.")

    for scope in scopes:
        if not scope:
            raise InvalidPathError("Scope must not be empty.")
        try:
            get_dir_path(project, scope, ResourceKind.ARTIFACTS)
        except ProjectFileError as e:
            raise InvalidPathError(
                f"Invalid scope: '{e.relative_path}'. Scopes must be directories "
                "inside the project's artifacts folder."
            ) from None


async def search_artifact_sections_logic(
    project: str,
    query: str,
    limit: int = 5,
    include_content: bool = True,
    scopes: list[str] | None = None,
) -> list[ArtifactSectionResult] | EmptyArtifactsResult:
    """Semantic search by artifact sections (chunks) (ASV-7), optionally restricted
    to one or more directory scopes (OR semantics; REQ-01). With include_content,
    each hit also carries the live file text at [start_line, end_line]; a hit whose
    file cannot be read gets content=None plus a warning (partial success). A scoped
    query matching zero chunks returns an EmptyArtifactsResult instead of an empty
    list (REQ-07); unscoped behavior is unchanged (REQ-02)."""
    from storage.uow import UnitOfWork

    if not await get_dir_path(project, "", ResourceKind.ROOT).exists_async():
        raise ProjectNotFoundError(f"Project '{project}' not found")

    normalized_scopes = _normalize_scopes(scopes) if scopes else None
    if normalized_scopes:
        _validate_scopes(project, normalized_scopes)

    uow = UnitOfWork.for_project(project)
    results = await uow.chunks.semantic_search(query, limit, normalized_scopes)

    if not results and normalized_scopes:
        return EmptyArtifactsResult(
            message=(
                f"No indexed chunks found under scope(s): {normalized_scopes}. "
                "Scopes must be directories -- to check a specific file, use "
                "read_project_artifacts instead."
            )
        )

    if include_content:
        for r in results:
            await _hydrate_hit_content(project, r)
    return [ArtifactSectionResult(**r) for r in results]
