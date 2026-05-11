"""
Regression test for B4000124:
  update_task_atomically must NOT raise AttributeError when closing a task with a resolution field.

Root cause: os.relpath(new_blob_path, project_root) — os has no attribute 'relpath'.
Fix: str(Path(new_blob_path).relative_to(project_root)).replace("\\", "/")

This test reproduces the exact call path that triggered the crash:
  update_task(status='closed', resolution='...')
"""

import asyncio
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_project(tmp_path):
    """Creates a minimal project root with a pre-seeded blob for task TEST-001."""
    project_root = tmp_path / "project"
    blob_dir = project_root / ".db" / "blobs" / "active"
    blob_dir.mkdir(parents=True)

    # Minimal frontmatter blob
    blob_content = """---
id: 1
key: TEST-001
title: Test task for B4000124
type: B
status: open
priority: high
project: TestProject
updated: '2026-04-23T00:00:00'
---

## Problem
Test problem.

## Solution
Test solution.
"""
    (blob_dir / "TEST-001.md").write_text(blob_content, encoding="utf-8")
    return str(project_root)


@pytest.fixture
def mock_task_record():
    """Returns a minimal TaskRecord-like object for patching the repository."""

    class FakeRecord:
        id = 1
        key = "TEST-001"
        title = "Test task for B4000124"
        type = "B"
        status = "open"
        priority = "high"
        project = "TestProject"
        file_path = ".db/blobs/active/TEST-001.md"
        updated = "2026-04-23T00:00:00"
        problem = "Test problem."
        solution = "Test solution."
        blocked_by = []
        where = []
        comments = None
        resolution = None

    return FakeRecord()


# ---------------------------------------------------------------------------
# Core regression test
# ---------------------------------------------------------------------------


def test_update_task_atomically_close_with_resolution_no_attribute_error_regression_b4000124(
    tmp_project, mock_task_record, monkeypatch
):
    """
    GIVEN a task in 'open' status
    WHEN update_task_atomically is called with status='closed' and a resolution string
    THEN no AttributeError should be raised (regression for os.relpath bug)
    AND the returned TaskRecord.file_path must be a valid relative path (not absolute)
    AND the path must point under the 'done' subdirectory
    """
    import os
    import sys

    # Add src to sys.path
    src_path = os.path.abspath("src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from storage.entities import TaskRecord
    from storage.uow import UnitOfWork

    uow = UnitOfWork(project_root=tmp_project)

    # Patch repository so we don't need a real LanceDB instance
    async def fake_get_by_key(key):
        return mock_task_record

    async def fake_upsert(record):
        pass  # no-op — we only care that os.relpath doesn't blow up before this

    monkeypatch.setattr(uow.tasks, "get_by_key", fake_get_by_key)
    monkeypatch.setattr(uow.tasks, "upsert", fake_upsert)

    # Also patch table.name to avoid DB connection requirements in get_table_lock
    uow.tasks.table = type("FakeTable", (), {"name": "tasks"})()  # minimal stub

    # Patch get_table_lock to a no-op async context manager
    from contextlib import asynccontextmanager

    import storage.db as db_module

    @asynccontextmanager
    async def fake_lock(name):
        yield

    monkeypatch.setattr(db_module, "get_table_lock", fake_lock)

    # Run the update
    result = asyncio.run(
        uow.update_task_atomically(
            "TEST-001",
            {
                "status": "closed",
                "resolution": "Fixed by correcting os.relpath to Path.relative_to.",
            },
        )
    )

    # Assertions
    assert isinstance(result, TaskRecord), "Should return a TaskRecord"
    assert not Path(result.file_path).is_absolute(), (
        f"file_path must be relative, got: {result.file_path}"
    )
    assert "done" in result.file_path, (
        f"Closed task blob must be under 'done/', got: {result.file_path}"
    )
    assert result.status == "closed"
    assert result.resolution == "Fixed by correcting os.relpath to Path.relative_to."


# ---------------------------------------------------------------------------
# Guard: ensure the broken call would fail on unpatched os
# ---------------------------------------------------------------------------


def test_os_relpath_does_not_exist():
    """
    Documents that os.relpath does not exist and confirms the fix is necessary.
    """
    import os

    assert not hasattr(os, "relpath"), (
        "os.relpath unexpectedly exists — stdlib may have changed; review the fix."
    )
    assert hasattr(os.path, "relpath"), "os.path.relpath must exist for the fallback fix to work."
