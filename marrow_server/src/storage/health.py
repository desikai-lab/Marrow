import os
from pathlib import Path
from typing import Any

from storage.blobs import read_blob
from storage.db import get_table


def check_integrity(project_root: str) -> dict[str, Any]:
    """
    Comprehensive database integrity scanner (Integrity Scanner).
    Implements BS-2.3 and BS-2.4 (Phase 2).
    
    Tasks:
    - Orphans: DB records whose files have been deleted.
    - Dangling: Blob files without corresponding entries in the DB.
    - Inconsistencies: Metadata desync (status/title) between DB and file.
    """
    project_root = str(Path(project_root).absolute())
    
    try:
        table = get_table(project_root)
        # 1. Read all records from LanceDB
        # Advanced agent: Use .to_list() instead of .to_pandas()
        # to avoid dependency on pandas
        index_entries = table.search().to_list()
    except Exception as e:
        return {"status": "error", "message": f"Could not read LanceDB: {str(e)}"}

    index_keys = {str(r["key"]): r for r in index_entries}
    index_paths = {str(r["file_path"]): r for r in index_entries}
    
    orphans = []
    inconsistencies = []
    
    # 2. Search for orphans and verify sync
    for key, record in index_keys.items():
        rel_path = str(record["file_path"])
        abs_path = os.path.join(project_root, rel_path)
        
        if not os.path.exists(abs_path):
            orphans.append({
                "key": key, 
                "expected_path": rel_path, 
                "id": record["id"]
            })
            continue

        # 3. Verify metadata (DB status == file status)
        # B53: Status is critical for routing
        try:
             blob_data = read_blob(abs_path)
             if str(blob_data.get("status")) != str(record["status"]):
                 inconsistencies.append({
                     "key": key,
                     "field": "status",
                     "index_val": record["status"],
                     "blob_val": blob_data.get("status")
                 })
             if str(blob_data.get("title")) != str(record["title"]):
                 inconsistencies.append({
                     "key": key,
                     "field": "title",
                     "index_val": record["title"],
                     "blob_val": blob_data.get("title")
                 })
        except Exception as e:
             inconsistencies.append({"key": key, "error": f"Blob read/parse error: {str(e)}"})

    # 4. Search for dangling blobs (files in blobs/ missing from the index)
    dangling_blobs = []
    blobs_root = os.path.join(project_root, "db", "blobs")
    if os.path.exists(blobs_root):
        for root, dirs, files in os.walk(blobs_root):
            for file in files:
                if not file.endswith(".md"):
                    continue
                abs_file_path = os.path.join(root, file)
                rel_file_path = os.path.relpath(abs_file_path, project_root).replace("\\", "/")
                
                # Normalize to Unix-standard paths for DB comparison
                norm_rel_path = rel_file_path.replace("\\", "/")
                
                if norm_rel_path not in index_paths:
                    dangling_blobs.append(norm_rel_path)

    return {
        "status": "healthy" if not (orphans or dangling_blobs or inconsistencies) else "unhealthy",
        "orphans_count": len(orphans),
        "orphans": orphans,
        "dangling_blobs_count": len(dangling_blobs),
        "dangling_blobs": dangling_blobs,
        "inconsistencies_count": len(inconsistencies),
        "inconsistencies": inconsistencies,
        "total_index_records": len(index_entries)
    }
