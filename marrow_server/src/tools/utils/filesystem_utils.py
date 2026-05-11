import os
import shutil
import sys
import threading
from datetime import datetime
from typing import Any

from config import PROJECTS_ROOT

_file_lock = threading.Lock()

def get_now_iso() -> str:
    """Returns the current date and time formatted as YYYY-MM-DDTHH:MM."""
    return datetime.now().strftime("%Y-%m-%dT%H:%M")

def validate_project_path(project: str) -> str:
    """Validates the project path and returns the absolute path to the project folder."""
    safe_project = os.path.basename(project) 
    prj_path = os.path.normpath(os.path.join(PROJECTS_ROOT, safe_project))
    if not prj_path.startswith(os.path.normpath(PROJECTS_ROOT)):
        raise ValueError("Invalid project path")
    return prj_path

def validate_artifact_path(project: str, rel_path: str) -> str:
    """Validates the artifact path and ensures it is inside the project's artifacts/ folder."""
    prj_path = validate_project_path(project)
    art_root = os.path.normpath(os.path.join(prj_path, "artifacts"))
    
    # README.md is permitted at the project root
    if rel_path.lower() == "readme.md":
        target = os.path.normpath(os.path.join(prj_path, "README.md"))
        if not target.startswith(prj_path):
             raise ValueError("Path traversal attempt")
        return target

    full_path = os.path.normpath(os.path.join(art_root, rel_path))
    if not full_path.startswith(art_root):
        raise ValueError("Path traversal attempt")
    return full_path

def create_artifact_backup(project: str, rel_path: str):
    """Creates a copy of the artifact in the hidden .history folder before modification."""
    try:
        prj_path = validate_project_path(project)
        full_src = validate_artifact_path(project, rel_path)
        
        if not os.path.exists(full_src):
            return
            
        history_root = os.path.join(prj_path, ".history", "artifacts")
        rel_dir = os.path.dirname(rel_path)
        target_dir = os.path.join(history_root, rel_dir)
        os.makedirs(target_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(os.path.basename(rel_path))
        target_path = os.path.join(target_dir, f"{name}_{timestamp}{ext}")
        
        shutil.copy2(full_src, target_path)
    except Exception as e:
        print(f"Backup error for {rel_path}: {e}", file=sys.stderr)

def list_directory_contents(path: str, recursive: bool = False, base_path: str = None) -> list[dict[str, str]]:
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
                results.extend(list_directory_contents(full_path, recursive=True, base_path=base_path))
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

    prj_path = validate_project_path(project)
    recycle_root = os.path.join(prj_path, ".recycle_bin")
    os.makedirs(recycle_root, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name, ext = os.path.splitext(os.path.basename(real_src))
    target_path = os.path.join(recycle_root, f"{name}_{timestamp}{ext}")
    
    shutil.move(real_src, target_path)
    return f"File {rel_path} moved to recycle bin."

def get_artifact_history(project: str, rel_path: str) -> list[dict[str, Any]]:
    """Returns a list of available backups for the artifact."""
    prj_path = validate_project_path(project)
    name, ext = os.path.splitext(os.path.basename(rel_path))
    rel_dir = os.path.dirname(rel_path)
    
    history_dir = os.path.join(prj_path, ".history", "artifacts", rel_dir)
    if not os.path.exists(history_dir):
        return []
        
    backups = []
    # Pattern: name_YYYYMMDD_HHMMSS.ext
    for f in os.listdir(history_dir):
        if f.startswith(f"{name}_") and f.endswith(ext):
            full_path = os.path.join(history_dir, f)
            mtime = os.path.getmtime(full_path)
            dt = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            backups.append({
                "backup_name": f,
                "date": dt,
                "size": os.path.getsize(full_path)
            })
            
    # Sort: newest first
    return sorted(backups, key=lambda x: x["backup_name"], reverse=True)

def restore_backup(project: str, rel_path: str, backup_name: str) -> str:
    """Restores an artifact from a backup."""
    prj_path = validate_project_path(project)
    rel_dir = os.path.dirname(rel_path)
    
    src = os.path.normpath(os.path.join(prj_path, ".history", "artifacts", rel_dir, backup_name))
    dest = validate_artifact_path(project, rel_path)
    
    # Guard against path traversal outside the .history folder
    if not src.startswith(os.path.normpath(os.path.join(prj_path, ".history"))):
        raise ValueError("Invalid backup source")
        
    if not os.path.exists(src):
        raise FileNotFoundError(f"Backup {backup_name} not found.")
        
    # Back up the CURRENT state before restoring (so the rollback itself can be undone)
    create_artifact_backup(project, rel_path)
    
    # Copy the backup file back to its original location
    shutil.copy2(src, dest)
    return f"Artifact {rel_path} successfully restored from {backup_name}."
