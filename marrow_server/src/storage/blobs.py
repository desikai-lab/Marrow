from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from utils.metrics import track_time

FRONTMATTER_META_KEYS = {"id", "key", "title", "type", "status", "priority",
                         "blocked_by", "where", "updated", "project"}

def _blob_path(project_root: str, task_key: str, status: str, year: str | None = None) -> Path:
    """Builds the blob file path. Appends a year subdirectory for done/ blobs."""
    base = Path(project_root) / ".db" / "blobs"
    status_lower = status.lower()
    if "closed" in status_lower or status_lower == "done":
        y = year or str(datetime.now().year)
        return base / "done" / y / f"{task_key}.md"
    elif "paused" in status_lower:
        return base / "paused" / f"{task_key}.md"
    else:
        return base / "active" / f"{task_key}.md"

@track_time(layer="blob")
def write_blob(project_root: str, task: dict[str, Any]) -> Path:
    """Writes a task to a .md file with Frontmatter. Returns the file path."""
    # Use the key for the path (e.g. F1.md)
    path = _blob_path(project_root, task["key"], task.get("status", ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    
    meta = {k: task[k] for k in FRONTMATTER_META_KEYS if k in task}
    body_lines = []
    if task.get("problem"):
        body_lines += ["## Problem", task["problem"], ""]
    if task.get("solution"):
        body_lines += ["## Solution", task["solution"], ""]
    if task.get("comments"):
        body_lines += ["## Comments", task["comments"], ""]
    if task.get("resolution"):
        body_lines += ["## Resolution", task["resolution"], ""]
    
    content = "---\n" + yaml.dump(meta, allow_unicode=True, sort_keys=False) + "---\n\n"
    content += "\n".join(body_lines)
    
    path.write_text(content, encoding="utf-8")
    return path

@track_time(layer="blob")
def read_blob(blob_path: str | Path) -> dict[str, Any]:
    """Parses a .md file with Frontmatter. Returns a dict of all task fields."""
    path = Path(blob_path)
    if not path.exists():
        raise FileNotFoundError(f"Blob not found: {blob_path}")
    
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise ValueError(f"Invalid blob format (no frontmatter): {blob_path}")
    
    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Invalid blob format (missing frontmatter closing): {blob_path}")
        
    meta = yaml.safe_load(parts[1])
    body = parts[2].strip() if len(parts) > 2 else ""
    
    # Parse body sections
    result = dict(meta) if meta else {}
    # Support both English and legacy Russian headers
    sections = [
        ("Problem", "problem"),
        ("Solution", "solution"),
        ("Comments", "comments"),
        ("Resolution", "resolution")
    ]
    for header, field_name in sections:
        marker = f"## {header}"
        if marker in body:
            idx = body.find(marker) + len(marker)
            next_h2 = body.find("## ", idx)
            text = body[idx: next_h2 if next_h2 != -1 else None].strip()
            # Don't overwrite if already set by English header
            if field_name not in result:
                result[field_name] = text
    
    return result

@track_time(layer="blob")
def delete_blob(blob_path: str | Path) -> None:
    """Deletes the physical blob file."""
    Path(blob_path).unlink(missing_ok=True)
