import logging
import os
from typing import Any

from config import PROJECTS_ROOT
from storage.embeddings import embeddings_manager
from storage.repositories.skeleton_repository import SkeletonRepository

logger = logging.getLogger("marrow.skeleton_query_service")


async def search_code_skeletons_logic(
    project: str,
    query: str,
    chunk_type: str | None = None,
    limit: int = 10,
    include_tests: bool = False,
    root_path: str | None = None,
) -> list[dict[str, Any]]:
    """
    Performs a semantic similarity search over the code_skeleton_index for the
    given project.

    Generates a query embedding from `query`, then delegates to
    SkeletonRepository.semantic_search() with optional chunk_type prefilter.

    Returns a list of matching chunks sorted by vector distance (closest first).
    Each result includes: path, project, chunk_type, chunk_name, skeleton_text,
    start_line, end_line, distance.
    """
    project_root = os.path.join(PROJECTS_ROOT, project)
    if not os.path.exists(project_root):
        logger.warning("Project not found: %s", project)
        return []

    import asyncio

    from config import EMBEDDING_MODEL_CODE
    query_vector = await asyncio.to_thread(
        embeddings_manager.generate_vector, query, model_name=EMBEDDING_MODEL_CODE
    )
    if query_vector is None:
        logger.error("Failed to generate embedding for query: %s", query)
        return []

    repo = SkeletonRepository(project_root)
    return await repo.semantic_search(
        query_vector=query_vector,
        project=project,
        chunk_type=chunk_type,
        limit=limit,
        include_tests=include_tests,
        root_path=root_path,
    )


async def get_exact_code_units_logic(
    project: str,
    exact_name: str,
    chunk_type: str | None = None,
    include_tests: bool = False,
) -> list[dict[str, Any]]:
    """
    Retrieves code units matching an exact name (e.g. a specific class or method).
    """
    project_root = os.path.join(PROJECTS_ROOT, project)
    if not os.path.exists(project_root):
        logger.warning("Project not found: %s", project)
        return []

    repo = SkeletonRepository(project_root)
    return await repo.get_exact_code_units(project, exact_name, chunk_type, include_tests=include_tests)


async def get_file_skeleton_logic(
    project: str,
    path: str,
    depth: int = 0,
    summary_only: bool = False,
) -> list[dict[str, Any]]:
    """
    Retrieves the chronological structural outline of a file.
    """
    project_root = os.path.join(PROJECTS_ROOT, project)
    if not os.path.exists(project_root):
        logger.warning("Project not found: %s", project)
        return []

    repo = SkeletonRepository(project_root)
    return await repo.get_file_skeleton_chunks(path, project, depth=depth, summary_only=summary_only)


def _build_tree(paths: list[str], max_depth: int) -> dict[str, Any]:
    """Collapses flat file paths into a nested dict tree truncated at max_depth."""
    tree: dict[str, Any] = {}
    for path in paths:
        parts = path.replace('\\', '/').split('/')
        parts = parts[:max_depth]          # truncate at depth
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part + "/", {})
        node.setdefault(parts[-1], None)   # leaf
    return {"root": ".", "structure": tree}


async def get_project_map_logic(project: str, depth: int = 2, include_tests: bool = False) -> dict[str, Any]:
    """Returns a live directory tree of indexed files for agent orientation."""
    project_root = os.path.join(PROJECTS_ROOT, project)
    if not os.path.exists(project_root):
        logger.warning("Project not found: %s", project)
        return {}
    repo = SkeletonRepository(project_root)
    paths = await repo.get_all_indexed_paths(project, include_tests=include_tests)
    return _build_tree(paths, max_depth=depth)
