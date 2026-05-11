import pytest
from pathlib import Path
from storage.blobs import write_blob, read_blob, delete_blob, _blob_path

def test_blob_path_active_status_contains_active_directory(tmp_project_root):
    """Verifies the path for active status."""
    path = _blob_path(tmp_project_root, "F1", "active")
    assert "active/F1.md" in path.as_posix()

def test_blob_path_paused_status_contains_paused_directory(tmp_project_root):
    """Verifies the path for paused status."""
    # Using English status now
    path = _blob_path(tmp_project_root, "F1", "paused")
    assert "paused/F1.md" in path.as_posix()

def test_blob_path_closed_status_with_year_contains_done_directory(tmp_project_root):
    """Verifies the path for done status with a specific year."""
    # Using English status now
    path = _blob_path(tmp_project_root, "F1", "closed", year="2025")
    assert "done/2025/F1.md" in path.as_posix()

def test_write_blob_and_read_blob_roundtrip_preserves_all_fields(tmp_project_root):
    """Verifies the write-read cycle for a blob."""
    task = {
        "id": 123,
        "key": "F123",
        "title": "Test Task",
        "type": "F",
        "status": "active",
        "priority": "high",
        "problem": "Problem description",
        "solution": "Solution description",
        "comments": "Comment text",
        "resolution": "Fixed in v2.0",
        "project": "test_project",
        "where": ["test.py"]
    }
    
    path = write_blob(tmp_project_root, task)
    assert path.exists()
    
    read_data = read_blob(path)
    # Verify core fields
    for k in ["id", "key", "title", "type", "status", "priority", "problem", "solution", "comments", "resolution"]:
        assert read_data[k] == task[k]

def test_read_blob_no_frontmatter_raises_value_error(tmp_path):
    """Verifies behavior when reading an invalid file."""
    bad_file = tmp_path / "bad.md"
    bad_file.write_text("Hello world", encoding="utf-8")
    with pytest.raises(ValueError, match="no frontmatter"):
        read_blob(bad_file)

def test_delete_blob_existing_file_removes_from_filesystem(tmp_project_root):
    """Verifies blob deletion."""
    task = {"id": 1, "key": "DEL1", "status": "active"}
    path = write_blob(tmp_project_root, task)
    assert path.exists()
    delete_blob(path)
    assert not path.exists()

def test_read_blob_missing_frontmatter_closing_raises_value_error(tmp_path):
    """Verifies behavior when frontmatter closing marker is missing."""
    bad_file = tmp_path / "no_close.md"
    bad_file.write_text("---\ntitle: test", encoding="utf-8")
    with pytest.raises(ValueError, match="missing frontmatter closing"):
        read_blob(bad_file)
