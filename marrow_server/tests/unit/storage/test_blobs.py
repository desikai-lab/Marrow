from enum import StrEnum

import pytest
import yaml
from storage.blobs import _blob_path, _sanitize_for_yaml, delete_blob, read_blob, write_blob

# ---------------------------------------------------------------------------
# Local stub enums (mirror domain enums without importing domain layer)
# ---------------------------------------------------------------------------


class _Priority(StrEnum):
    medium = "medium"
    high = "high"


class _Status(StrEnum):
    open = "open"


class _Type(StrEnum):
    TD = "TD"


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
        "where": ["test.py"],
    }

    path = write_blob(tmp_project_root, task)
    assert path.exists()

    read_data = read_blob(path)
    # Verify core fields
    for k in [
        "id",
        "key",
        "title",
        "type",
        "status",
        "priority",
        "problem",
        "solution",
        "comments",
        "resolution",
    ]:
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


# ---------------------------------------------------------------------------
# B4000170 — Enum serialization fix
# ---------------------------------------------------------------------------


def test_sanitize_for_yaml_converts_enum_to_plain_value():
    """_sanitize_for_yaml must convert every Enum to its .value."""
    data = {"priority": _Priority.medium, "status": _Status.open, "type": _Type.TD}
    result = _sanitize_for_yaml(data)
    assert result == {"priority": "medium", "status": "open", "type": "TD"}


def test_writeBlob_enumFields_serializedAsPlainScalars(tmp_path):
    """Written blob must contain no !!python/object/apply tags."""
    task = {
        "key": "TD4000170",
        "id": "TD4000170",
        "title": "YAML Enum fix",
        "type": _Type.TD,
        "status": _Status.open,
        "priority": _Priority.medium,
        "project": "BacklogMCP",
    }
    write_blob(str(tmp_path), task)
    blob_file = tmp_path / ".db" / "blobs" / "active" / "TD4000170.md"
    raw = blob_file.read_text(encoding="utf-8")
    assert "!!python/object/apply" not in raw


def test_writeBlob_thenReadBlob_roundTripPreservesAllFields(tmp_path):
    """write_blob then read_blob must round-trip all fields without error."""
    task = {
        "key": "TD4000170",
        "id": "TD4000170",
        "title": "YAML Enum fix",
        "type": _Type.TD,
        "status": _Status.open,
        "priority": _Priority.medium,
        "project": "BacklogMCP",
        "problem": "Enum serialization bug",
        "solution": "Use safe_dump + sanitizer",
    }
    blob_path = write_blob(str(tmp_path), task)
    result = read_blob(blob_path)
    assert result["key"] == "TD4000170"
    assert result["priority"] == "medium"
    assert result["status"] == "open"
    assert result["type"] == "TD"
    assert result["problem"] == "Enum serialization bug"
    assert result["solution"] == "Use safe_dump + sanitizer"


def test_readBlob_corruptedPythonTaggedYaml_raisesConstructorError(tmp_path):
    """A blob with Python tags must raise yaml.constructor.ConstructorError."""
    corrupted = (
        "---\n"
        "key: TD4000170\n"
        "priority: !!python/object/apply:domain.enums.TaskPriority\n"
        "- medium\n"
        "---\n\n"
    )
    blob_path = tmp_path / "TD4000170.md"
    blob_path.write_text(corrupted, encoding="utf-8")
    with pytest.raises(yaml.constructor.ConstructorError):
        read_blob(blob_path)


def test_blobPath_unclosedStatus_routesToActiveDirectory(tmp_project_root):
    """'unclosed' contains 'closed' as a substring — must NOT route to done/."""
    path = _blob_path(tmp_project_root, "F1", "unclosed")
    assert "done" not in path.as_posix()
    assert "active/F1.md" in path.as_posix()
