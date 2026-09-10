import os
import shutil
import sys
import threading
from datetime import datetime
from typing import Any

from common import path_resolver
from common.file_accessor import FileAccessor
from common.path_resolver import (
    HISTORY_TIMESTAMP_FORMAT,
    NAMESPACE_ARTIFACTS,
    ResourceKind,
    get_history,
)
from common.project_file_error import ProjectFileError
from common.project_path import ProjectPath

_file_lock = threading.Lock()


def get_now_iso() -> str:
    """Returns the current date and time formatted as YYYY-MM-DDTHH:MM."""
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


def validate_project_path(project: str) -> str:
    """Validates the project path and returns the absolute path to the project folder."""
    try:
        return path_resolver.get_raw_path(project, "", ResourceKind.ROOT)
    except ProjectFileError:
        raise ValueError("Invalid project path") from None


def validate_artifact_path(project: str, rel_path: str) -> bool:
    """Validates the artifact path and ensures it is inside the project's artifacts/ folder (or root README.md).
    Returns True if valid, False if traversal or invalid."""
    kind = ResourceKind.ROOT if rel_path.lower() == "readme.md" else ResourceKind.ARTIFACTS
    target_rel = "README.md" if rel_path.lower() == "readme.md" else rel_path
    try:
        path_resolver.get_path(project, target_rel, kind)
        return True
    except ProjectFileError:
        return False


def resolve_artifact_project_path(project: str, rel_path: str) -> ProjectPath:
    """Resolves an artifact path to a ProjectPath primitive. Raises ProjectFileError if invalid."""
    kind = ResourceKind.ROOT if rel_path.lower() == "readme.md" else ResourceKind.ARTIFACTS
    target_rel = "README.md" if rel_path.lower() == "readme.md" else rel_path
    return path_resolver.get_path(project, target_rel, kind)


def create_artifact_backup(project: str, rel_path: str):
    """Creates a timestamped snapshot in the item's own .history folder before modification."""
    try:
        if not validate_artifact_path(project, rel_path):
            return
        src_pp = resolve_artifact_project_path(project, rel_path)
        if not src_pp.exists():
            return

        _, ext = os.path.splitext(os.path.basename(rel_path))
        timestamp = datetime.now().strftime(HISTORY_TIMESTAMP_FORMAT)
        backup_rel = os.path.join(NAMESPACE_ARTIFACTS, rel_path, f"{timestamp}{ext}")
        backup_pp = path_resolver.get_path(project, backup_rel, ResourceKind.HISTORY)

        src_pp.copy(backup_pp)
    except Exception as e:
        print(f"Backup error for {rel_path}: {e}", file=sys.stderr)


def list_directory_contents(
    path: str, recursive: bool = False, base_path: str = None
) -> list[dict[str, str]]:
    """Lists files and folders in a directory. Returns [{'name', 'type'}]."""
    if not os.path.exists(path) or not os.path.isdir(path):
        return []

    results = []
    if base_path is None:
        base_path = path

    for item in os.listdir(path):
        if item.startswith("."):
            continue

        full_path = os.path.join(path, item)
        rel_to_base = os.path.relpath(full_path, base_path).replace("\\", "/")

        if os.path.isdir(full_path):
            results.append({"name": f"{rel_to_base}/", "type": "dir"})
            if recursive:
                results.extend(
                    list_directory_contents(full_path, recursive=True, base_path=base_path)
                )
        else:
            results.append({"name": rel_to_base, "type": "file"})

    if base_path == path:
        return sorted(results, key=lambda x: (x["type"] != "dir", x["name"]))
    return results


def safe_move_file(src: str, dest: str):
    """Safely moves a file, creating parent directories as needed."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.move(src, dest)


def recycle_file(project: str, rel_path: str) -> str:
    """Moves a file to the project recycle bin with a timestamp."""
    if not validate_artifact_path(project, rel_path):
        return f"File {rel_path} not found."
    src_pp = resolve_artifact_project_path(project, rel_path)
    if not src_pp.exists():
        return f"File {rel_path} not found."

    timestamp = datetime.now().strftime(HISTORY_TIMESTAMP_FORMAT)
    name, ext = os.path.splitext(os.path.basename(rel_path))
    dest_pp = path_resolver.get_path(project, f"{name}_{timestamp}{ext}", ResourceKind.RECYCLE_BIN)

    src_pp.move(dest_pp)
    return f"File {rel_path} moved to recycle bin."


def get_artifact_history(project: str, rel_path: str) -> list[dict[str, Any]]:
    """Returns a list of available backups for the artifact."""
    history_dir = path_resolver.get_history_raw_dir(
        project, rel_path, NAMESPACE_ARTIFACTS
    )
    if not os.path.isdir(history_dir):
        return []

    accessor = FileAccessor()
    return [
        {
            "backup_name": fname,
            "date": datetime.fromtimestamp(
                os.path.getmtime(os.path.join(history_dir, fname))
            ).strftime("%Y-%m-%d %H:%M:%S"),
            "size": os.path.getsize(os.path.join(history_dir, fname)),
        }
        for fname in sorted(accessor.listdir(history_dir), reverse=True)
    ]


def restore_backup(project: str, rel_path: str, backup_name: str) -> str:
    """Restores an artifact from a backup."""
    history = get_history(project, rel_path, NAMESPACE_ARTIFACTS)
    item = history.find(backup_name)
    if item is None:
        raise FileNotFoundError(f"Backup {backup_name} not found.")

    try:
        backup_pp = history.backup_path(item)
    except ProjectFileError:
        raise ValueError("Invalid backup source") from None

    if not backup_pp.exists():
        raise FileNotFoundError(f"Backup {backup_name} not found.")

    dest_pp = resolve_artifact_project_path(project, rel_path)

    create_artifact_backup(project, rel_path)

    backup_pp.copy(dest_pp)

    return f"Artifact {rel_path} successfully restored from {backup_name}."
