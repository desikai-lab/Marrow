import os
from enum import Enum

from config import PROJECTS_ROOT
from tools.utils import project_settings

from .project_file_error import ProjectFileError
from .project_path import ProjectPath


class ResourceKind(Enum):
    ARTIFACTS = "artifacts"
    SOURCE = "source"
    TASKS_BLOB = "tasks_blob"
    TEMPLATE = "template"
    ROOT = "root"


_READ_ONLY_KINDS = frozenset({ResourceKind.SOURCE})

_FIXED_SUBPATH: dict[ResourceKind, str] = {
    ResourceKind.ARTIFACTS: "artifacts",
    ResourceKind.TASKS_BLOB: os.path.join(".db", "blobs"),
}

_IO_OPTIONS: dict[ResourceKind, dict] = {
    ResourceKind.ARTIFACTS: dict(encoding="utf-8-sig", errors="replace", write_newline=""),
}


def get_path(
    project: str, relative_path: str = "", kind: ResourceKind = ResourceKind.ARTIFACTS
) -> ProjectPath:
    absolute = _resolve(project, relative_path, kind)
    if absolute is None:
        raise ProjectFileError(relative_path)
    return ProjectPath(
        relative_path,
        absolute,
        writable=kind not in _READ_ONLY_KINDS,
        **_IO_OPTIONS.get(kind, {}),
    )


def get_artifacts_path(project: str, relative_path: str = "") -> ProjectPath:
    return get_path(project, relative_path, ResourceKind.ARTIFACTS)


def get_source_path(project: str, relative_path: str = "") -> ProjectPath:
    return get_path(project, relative_path, ResourceKind.SOURCE)


def get_blob_path(project: str, task_key: str, status: str, year: str | None = None) -> ProjectPath:
    from datetime import datetime

    status_lower = status.lower()
    if status_lower in ("closed", "done"):
        y = year or str(datetime.now().year)
        rel = os.path.join("done", y, f"{task_key}.md")
    elif "paused" in status_lower:
        rel = os.path.join("paused", f"{task_key}.md")
    else:
        rel = os.path.join("active", f"{task_key}.md")
    return get_path(project, rel, ResourceKind.TASKS_BLOB)


def get_raw_path(
    project: str, relative_path: str = "", kind: ResourceKind = ResourceKind.ROOT
) -> str:
    """⚠️ Narrow escape hatch — see architecture.md §2.2 for full docstring/allowlist rationale.
    ALLOWLISTED CALLERS ONLY (enforced by implementation_plan_migrations.md Step 15's lint rule):
      services/skeleton_query_service.py, storage/migrate.py, cli/commands/diag_index.py,
      cli/commands/reindex.py, cli/commands/reindex_chunks.py, tools/projects.py,
      cli/commands/repair_blobs.py, tools/utils/filesystem_utils.py
      (full 8-file allowlist — see implementation_plan_migrations.md Steps 6, 12, and 15)."""
    absolute = _resolve(project, relative_path, kind)
    if absolute is None:
        raise ProjectFileError(relative_path)
    return absolute


def _project_root(project: str) -> str | None:
    safe_project = os.path.basename(project)
    root = os.path.normpath(os.path.join(PROJECTS_ROOT, safe_project))
    if not root.startswith(os.path.normpath(PROJECTS_ROOT)):
        return None
    return root


def _resolve(project: str, relative_path: str, kind: ResourceKind) -> str | None:
    if kind is ResourceKind.SOURCE:
        return _resolve_source(project, relative_path)

    project_root = _project_root(project)
    if project_root is None:
        return None

    if kind is ResourceKind.ROOT:
        candidate = (
            os.path.normpath(os.path.join(project_root, relative_path))
            if relative_path
            else project_root
        )
        return candidate if candidate.startswith(project_root) else None

    subpath = _FIXED_SUBPATH.get(kind, "")
    kind_root = os.path.normpath(os.path.join(project_root, subpath))
    candidate = (
        os.path.normpath(os.path.join(kind_root, relative_path)) if relative_path else kind_root
    )
    return candidate if candidate.startswith(kind_root) else None


def _resolve_source(project: str, relative_path: str) -> str | None:
    settings = project_settings.load_project_settings(project)
    if not settings.source_tools_available or settings.source_root is None:
        return None
    root = str(settings.source_root)
    candidate = os.path.normpath(os.path.join(root, relative_path)) if relative_path else root
    return candidate if candidate.startswith(root) else None
