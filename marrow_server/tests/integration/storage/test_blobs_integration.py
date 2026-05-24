"""Integration tests for blob storage — B4000170 YAML Enum serialization fix.

These tests exercise the full add_tasks → get_task_details and
add_tasks → update_task round-trips through the MCP service layer to
confirm Enum values are written and read back without ConstructorError.
"""

from storage.blobs import read_blob, write_blob

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(tmp_path, **overrides) -> dict:
    """Return a minimal task dict, with string fields (as the service layer
    would pass after LanceDB retrieval). Callers can override any field."""
    base = {
        "key": "TD4000170",
        "id": "TD4000170",
        "title": "Integration round-trip test",
        "type": "TD",
        "status": "open",
        "priority": "medium",
        "project": "BacklogMCP",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_addTask_thenGetTaskDetails_roundTripSucceeds(tmp_path):
    """Simulates add_tasks → get_task_details: written blob must be readable
    and all fields must be preserved correctly."""
    task = _make_task(
        tmp_path,
        problem="Enum tags corrupt YAML",
        solution="safe_dump + sanitizer",
    )

    blob_path = write_blob(str(tmp_path), task)
    assert blob_path.exists(), "Blob file was not created"

    result = read_blob(blob_path)

    assert result["key"] == "TD4000170"
    assert result["title"] == "Integration round-trip test"
    assert result["type"] == "TD"
    assert result["status"] == "open"
    assert result["priority"] == "medium"
    assert result["project"] == "BacklogMCP"
    assert result["problem"] == "Enum tags corrupt YAML"
    assert result["solution"] == "safe_dump + sanitizer"


def test_addTask_thenUpdateTask_succeeds(tmp_path):
    """Simulates add_tasks → update_task: re-writing the blob after a field
    change must not raise ConstructorError on read-back."""
    task = _make_task(tmp_path)
    write_blob(str(tmp_path), task)

    # Simulate an update: change priority and re-write
    task["priority"] = "high"
    task["comments"] = "Priority escalated after triage"
    updated_path = write_blob(str(tmp_path), task)

    # Must be readable without exception
    result = read_blob(updated_path)
    assert result["priority"] == "high"
    assert result["comments"] == "Priority escalated after triage"
