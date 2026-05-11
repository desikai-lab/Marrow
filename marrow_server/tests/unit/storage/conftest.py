import pytest
import shutil
from pathlib import Path
from storage.entities import TaskRecord
from storage.db import init_db

@pytest.fixture
def tmp_project_root(tmp_path):
    """Creates a temporary project structure for testing."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    # Initialize DB and directories
    init_db(str(project_root))
    return str(project_root)

@pytest.fixture
def sample_task_record():
    """Returns a sample TaskRecord instance."""
    return TaskRecord(
        id=123,
        key="F123",
        title="Sample Task",
        type="F",
        status="active",
        priority="high",
        file_path="db/blobs/active/F123.md",
        updated="2026-03-27T12:00:00",
        project="test_project",
        problem="Problem description",
        solution="Solution description",
        where=["config.py", "app.py"]
    )
