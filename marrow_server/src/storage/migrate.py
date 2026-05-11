import os
import yaml
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

from storage import TaskRecord, write_blob, upsert_task, init_db
from config import PROJECTS_ROOT, get_project_files

@dataclass
class MigrationReport:
    project: str
    created: int = 0
    skipped: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)

def extract_int_id(key: str) -> int:
    """Extracts a number from a key like 'F123' -> 123.
    Returns 0 if the key contains no digits.
    """
    match = re.search(r'\d+', key)
    return int(match.group()) if match else 0

def sync_initial(project: str, dry_run: bool = False, force: bool = False) -> MigrationReport:
    """Migrates YAML tasks of a project into Decoupled Storage.
    
    Pattern: ETL (Extract, Transform, Load)
    """
    report = MigrationReport(project=project)
    
    project_root = os.path.join(PROJECTS_ROOT, project)
    if not os.path.exists(project_root):
        report.errors.append({"error": f"Project root not found: {project_root}"})
        return report

    # 1. Initialize DB (create folders and table)
    # Advanced agent: ensure db/ structure exists
    if not dry_run:
        init_db(project_root)

    files = get_project_files(project)
    
    # Map file keys to default statuses
    file_map = {
        "active": "open",
        "paused": "paused",
        "done": "closed"
    }

    # ID offsets to avoid collisions between types F, B, TD
    type_offsets = {"F": 1000000, "B": 2000000, "TD": 3000000}
    # Backward compatibility for Russian types during migration
    legacy_type_map = {"Ф": "F", "Б": "B", "ТД": "TD"}

    for file_key, default_status in file_map.items():
        yaml_path = files.get(file_key)
        if not yaml_path or not os.path.exists(yaml_path):
            continue
            
        with open(yaml_path, "r", encoding="utf-8") as f:
            try:
                tasks = yaml.safe_load(f)
                if not isinstance(tasks, list):
                    # B53: Handle case where YAML is empty or not a list
                    continue
            except yaml.YAMLError as e:
                report.errors.append({"file": file_key, "error": f"YAML Parse Error: {str(e)}"})
                continue

        for task_data in tasks:
            try:
                # In the old system, ID was a string (F1). In the new system, it's 'key'.
                task_key = str(task_data.get("id", ""))
                if not task_key:
                    report.errors.append({"task_title": task_data.get("title"), "error": "Missing task ID"})
                    continue

                # Generate numeric ID from key
                task_type = task_data.get("type", "F")
                if task_type in legacy_type_map:
                    task_type = legacy_type_map[task_type]
                    
                base_id = extract_int_id(task_key)
                int_id = type_offsets.get(task_type, 4000000) + base_id

                status = task_data.get("status", default_status)
                
                # Create DTO
                record = TaskRecord(
                    id=int_id,
                    key=task_key,
                    title=task_data.get("title", "No Title"),
                    type=task_type,
                    status=status,
                    priority=task_data.get("priority", "medium"),
                    file_path="",  # Filled after write_blob
                    updated=task_data.get("updated", datetime.now().isoformat()),
                    project=project,
                    problem=task_data.get("problem"),
                    solution=task_data.get("solution"),
                    blocked_by=task_data.get("blocked_by", []) if isinstance(task_data.get("blocked_by"), list) else [],
                    where=task_data.get("where", []) if isinstance(task_data.get("where"), list) else [],
                    comments=task_data.get("comments")
                )

                if dry_run:
                    report.created += 1
                    continue

                # Load: Save blob (FS)
                # vars(record) contains all necessary fields for blobs.write_blob
                blob_path = write_blob(project_root, vars(record))
                
                # Update path in the index (relative to project root)
                rel_path = os.path.relpath(blob_path, project_root).replace("\\", "/")
                record.file_path = rel_path
                
                # Load: Save to index (LanceDB)
                upsert_task(project_root, record)
                
                report.created += 1
                
            except Exception as e:
                report.errors.append({"task_id": task_data.get("id", "unknown"), "error": f"Transform/Load error: {str(e)}"})

    return report

def load_task_from_blob(abs_path: str, project_name: str) -> Optional[TaskRecord]:
    """
    Loads a task from a Markdown file (.md).
    Extracts the YAML metadata block.
    """
    if not os.path.exists(abs_path):
        return None
        
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Search for Frontmatter block: --- \n YAML \n ---
        match = re.search(r'^---\n(.*?)\n---\n', content, re.DOTALL | re.MULTILINE)
        if not match:
            # Try variant without leading newline
            match = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
            if not match:
                return None
            
        meta = yaml.safe_load(match.group(1))
        
        # Search for ## Problem and ## Solution sections in Markdown body
        problem_chunk = ""
        solution_chunk = ""
        
        # Parse Problem
        prob_match = re.search(r'## Problem\n(.*?)(?:\n##|$)', content, re.DOTALL | re.IGNORECASE)
        if prob_match:
            problem_chunk = prob_match.group(1).strip()
            
        # Parse Solution
        sol_match = re.search(r'## Solution\n(.*?)(?:\n##|$)', content, re.DOTALL | re.IGNORECASE)
        if sol_match:
            solution_chunk = sol_match.group(1).strip()

        record = TaskRecord(
            id=meta.get("id"),
            key=meta.get("key", meta.get("id_str")),
            title=meta.get("title", f"Task {meta.get('key')}"),
            type=meta.get("type", "F"),
            status=meta.get("status", "open"),
            priority=meta.get("priority", "medium"),
            file_path="", 
            updated=meta.get("updated", datetime.now().isoformat()),
            project=project_name,
            problem=problem_chunk or meta.get("problem"),
            solution=solution_chunk or meta.get("solution"),
            blocked_by=meta.get("blocked_by", []),
            where=meta.get("where", []),
            comments=meta.get("comments"),
            resolution=meta.get("resolution")
        )
        
        # Recalculate relative file path for index
        # root/PROJECTS/ProjectName/.db/blobs/status/key.md
        # record.file_path should be .db/blobs/...
        project_root = os.path.join(PROJECTS_ROOT, project_name)
        rel_path = os.path.relpath(abs_path, project_root).replace("\\", "/")
        record.file_path = rel_path
        
        return record
        
    except Exception as e:
        print(f"Error loading blob {abs_path}: {str(e)}")
        return None
