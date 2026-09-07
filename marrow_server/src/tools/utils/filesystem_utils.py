import os
import shutil
import sys
import threading
from datetime import datetime
from typing import Any

from common import path_resolver
from common.path_resolver import ResourceKind
from common.project_file_error import ProjectFileError

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


def validate_artifact_path(project: str, rel_path: str) -> str:
    """Validates the artifact path and ensures it is inside the project's artifacts/ folder."""
    if rel_path.lower() == "readme.md":
        try:
            return path_resolver.get_raw_path(project, "README.md", ResourceKind.ROOT)
        except ProjectFileError:
            raise ValueError("Path traversal attempt") from None
    try:
        return path_resolver.get_raw_path(project, rel_path, ResourceKind.ARTIFACTS)
    except ProjectFileError:
        raise ValueError("Path traversal attempt") from None


def create_artifact_backup(project: str, rel_path: str):
    """Creates a timestamped snapshot in the item's own .history folder before modification."""
    try:
        full_src = validate_artifact_path(project, rel_path)
        if not os.path.exists(full_src):
            return

        history_dir = path_resolver.get_history_raw_dir(project, rel_path, "artifacts")
        os.makedirs(history_dir, exist_ok=True)

        _, ext = os.path.splitext(os.path.basename(rel_path))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = os.path.join(history_dir, f"{timestamp}{ext}")

        shutil.copy2(full_src, target_path)
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
    real_src = validate_artifact_path(project, rel_path)
    if not os.path.exists(real_src):
        return f"File {rel_path} not found."

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name, ext = os.path.splitext(os.path.basename(real_src))
    target_path = path_resolver.get_raw_path(
        project, f"{name}_{timestamp}{ext}", ResourceKind.RECYCLE_BIN
    )
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    shutil.move(real_src, target_path)
    return f"File {rel_path} moved to recycle bin."


def get_artifact_history(project: str, rel_path: str) -> list[dict[str, Any]]:
    """Returns a list of available backups for the artifact."""
    history_dir = path_resolver.get_history_raw_dir(project, rel_path, "artifacts")
    if not os.path.isdir(history_dir):
        return []

    return [
        {
            "backup_name": fname,
            "date": datetime.fromtimestamp(os.path.getmtime(os.path.join(history_dir, fname))).strftime("%Y-%m-%d %H:%M:%S"),
            "size": os.path.getsize(os.path.join(history_dir, fname)),
        }
        for fname in sorted(os.listdir(history_dir), reverse=True)
    ]


def restore_backup(project: str, rel_path: str, backup_name: str) -> str:
    """Restores an artifact from a backup."""
    try:
        src = path_resolver.get_raw_path(
            project, os.path.join("artifacts", rel_path, backup_name), ResourceKind.HISTORY
        )
    except ProjectFileError:
        raise ValueError("Invalid backup source") from None

    dest = validate_artifact_path(project, rel_path)

    if not os.path.exists(src):
        raise FileNotFoundError(f"Backup {backup_name} not found.")

    # Back up the CURRENT state before restoring (so the rollback itself can be undone)
    create_artifact_backup(project, rel_path)

    # Copy the backup file back to its original location
    shutil.copy2(src, dest)
    return f"Artifact {rel_path} successfully restored from {backup_name}."
