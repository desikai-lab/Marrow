import logging
import os
from typing import Any, Literal

import tools.utils.session_integrity  # noqa: F401 -- import for registration side-effect
from storage.uow import UnitOfWork
from tools.utils.artifact_integrity_hooks import ArtifactIntegrityRegistry
from tools.utils.artifact_strategies import ArtifactStrategyFactory
from tools.utils.filesystem_utils import (
    create_artifact_backup,
    get_artifact_history,
    recycle_file,
    restore_backup,
    validate_artifact_path,
    validate_project_path,
)
from utils.exceptions import ArtifactNotFoundError

logger = logging.getLogger(__name__)


def save_artifact_logic(
    project: str,
    rel_path: str,
    content: str,
    mode: Literal[
        "replace_file",
        "replace_section",
        "append_section",
        "replace_chunk",
        "patch",
        "delete_section",
    ] = "replace_file",
    **kwargs,
) -> str:
    """Universal artifact save via the Strategy pattern."""
    if "\0" in content:
        raise ValueError("Binary data is not allowed.")

    target_path = validate_artifact_path(project, rel_path)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    hook = ArtifactIntegrityRegistry.get_hook(rel_path)
    if hook:
        content = hook.validate_and_repair(project, rel_path, content, mode)

    # Automatic backup before modification (ADR-05)
    create_artifact_backup(project, rel_path)

    strategy = ArtifactStrategyFactory.get_save_strategy(mode)
    return strategy.save(target_path, content, **kwargs)


def read_artifact_logic(
    project: str,
    rel_path: str,
    mode: Literal["full", "section", "lines"] = "full",
    direction: Literal["begin", "end"] = "begin",
    **kwargs,
) -> str:
    """Universal artifact read via the Strategy pattern."""
    target_path = validate_artifact_path(project, rel_path)

    if not os.path.exists(target_path) or not os.path.isfile(target_path):
        raise ArtifactNotFoundError(f"Artifact {rel_path} not found.")

    strategy = ArtifactStrategyFactory.get_read_strategy(mode)
    return strategy.read(target_path, direction=direction, **kwargs)


def list_artifacts_logic(
    project: str, rel_dir: str = "", recursive: bool = False
) -> list[dict[str, str]]:
    """Lists artifacts in a folder. Returns objects with {'name', 'type'}.
    Uses the shared directory listing utility."""
    from tools.utils.filesystem_utils import list_directory_contents

    target_dir = validate_artifact_path(project, rel_dir)
    return list_directory_contents(target_dir, recursive=recursive)


async def move_project_artifact_logic(project: str, src_path: str, dest_path: str) -> str:
    """Moves or renames an artifact."""
    from tools.utils.filesystem_utils import safe_move_file

    real_src = validate_artifact_path(project, src_path)
    real_dest = validate_artifact_path(project, dest_path)

    if not os.path.exists(real_src):
        return f"Source file {src_path} not found."

    safe_move_file(real_src, real_dest)

    # Phase 3: Sync index
    try:
        project_root = validate_project_path(project)
        uow = UnitOfWork(project_root)
        await uow.artifacts.rename(src_path, dest_path)
    except (ImportError, Exception):
        pass  # Indexing might not be fully implemented yet (Task 4)

    return f"Artifact moved: {src_path} -> {dest_path}"


async def delete_project_artifact_logic(project: str, rel_path: str) -> str:
    """Safe delete: moves the file to the .recycle_bin."""
    msg = recycle_file(project, rel_path)

    # Phase 3: Sync index
    try:
        project_root = validate_project_path(project)
        uow = UnitOfWork(project_root)
        await uow.artifacts.delete(rel_path)
    except (ImportError, Exception):
        pass

    return msg


async def search_project_artifacts_logic(project: str, query: str) -> list[dict[str, Any]]:
    """Global search across all text artifacts in the project."""
    # Phase 3: Cascade Search (Semantic + Grep)
    results = []

    try:
        project_root = validate_project_path(project)
        uow = UnitOfWork(project_root)
        semantic_results = await uow.artifacts.semantic_search(query, limit=10)
        for res in semantic_results:
            # Extract the file beginning (snippet), as vectorization indexes the file start
            snippet = "[Semantic vector match in file] (Read file for details)"
            file_path_abs = os.path.join(project_root, res["record"].path)
            if os.path.exists(file_path_abs):
                try:
                    with open(file_path_abs, encoding="utf-8", errors="replace") as _f:
                        snippet_text = _f.read(300).strip()
                        if snippet_text:
                            # Collapse newlines for compact JSON output
                            snippet_text = " ".join(snippet_text.split())
                            snippet = f"[Semantic Match] {snippet_text}..."
                except Exception:
                    pass

            results.append(
                {
                    "path": res["record"].path,
                    "line": 1,  # Vectorization indexes the header/start, so line 1 is returned
                    "content": snippet,
                    "distance": res.get("distance", 0),
                }
            )
    except (ImportError, Exception):
        logger.error("Semantic search failed", exc_info=True)

    # Classic grep-style search (fallback / supplement)
    prj_path = validate_project_path(project)
    art_root = os.path.join(prj_path, "artifacts")
    # Also search project root (README, etc.)
    search_dirs = [art_root, prj_path]

    query_lower = query.lower()

    for base_dir in search_dirs:
        if not os.path.exists(base_dir):
            continue

        for root, dirs, files in os.walk(base_dir):
            if ".db" in root or ".history" in root:
                continue
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for file in files:
                if file.startswith("."):
                    continue
                full_path = os.path.join(root, file)
                if os.path.getsize(full_path) > 1024 * 1024:
                    continue

                try:
                    rel_to_prj = os.path.relpath(full_path, prj_path).replace("\\", "/")
                    with open(full_path, encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            if query_lower in line.lower():
                                results.append(
                                    {"path": rel_to_prj, "line": i, "content": line.strip()}
                                )
                            if len(results) >= 100:
                                return results
                except Exception:
                    continue
    return results


def patch_project_artifact_logic(project: str, rel_path: str, old_str: str, new_str: str) -> str:
    """Replaces a unique substring (via the shared strategy logic)."""
    return save_artifact_logic(project, rel_path, new_str, mode="patch", old_str=old_str)


def get_project_artifact_outline_logic(project: str, rel_path: str) -> str:
    """Extracts the table of contents (headings) from a Markdown file."""
    if not rel_path.lower().endswith(".md") and rel_path.lower() != "readme.md":
        raise ValueError("This tool only supports .md files.")

    target_path = validate_artifact_path(project, rel_path)

    if not os.path.exists(target_path):
        raise FileNotFoundError(f"File {rel_path} not found.")

    outline = []
    with open(target_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.strip().startswith("#"):
                outline.append(line.strip())

    if not outline:
        return "No Markdown headings found in the file."
    return "\n".join(outline)


def list_artifact_history_logic(project: str, rel_path: str) -> list[dict[str, Any]]:
    """Returns a list of available artifact versions."""
    return get_artifact_history(project, rel_path)


def restore_project_artifact_logic(project: str, rel_path: str, backup_name: str) -> str:
    """Restores an artifact from a backup (copies from .history to the artifact root)."""
    return restore_backup(project, rel_path, backup_name)


def read_project_artifacts_logic(project: str, reads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for req in reads:
        path = req.get("path")
        if not path:
            results.append({"error": "Request is missing 'path'"})
            continue

        try:
            content = read_artifact_logic(
                project=project,
                rel_path=path,
                mode=req.get("mode", "full"),
                direction=req.get("direction", "begin"),
                section_name=req.get("section_name"),
                start_line=req.get("start_line", 1),
                end_line=req.get("end_line"),
                max_chars=req.get("max_chars", 10000),
                skip_chars=req.get("skip_chars", 0),
                line_numbers=req.get("line_numbers", False),
            )
            results.append({"path": path, "content": content})
        except Exception as e:
            results.append({"path": path, "error": str(e)})

    return results
