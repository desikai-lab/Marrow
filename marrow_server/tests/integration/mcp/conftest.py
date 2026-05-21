import os
import tempfile

import pytest
import yaml

# Create a temporary directory at import time so it is set before any config imports
INTEGRATION_TASKS_DIR = tempfile.mkdtemp(prefix="marrow_integration_")
os.environ["TASKS_DIR"] = INTEGRATION_TASKS_DIR
os.environ["SECRET_TOKEN"] = "test-token-integration"


def pytest_configure(config):
    """Set integration env vars BEFORE any module (config.py) is imported."""
    os.environ["TASKS_DIR"] = INTEGRATION_TASKS_DIR
    os.environ["SECRET_TOKEN"] = "test-token-integration"


@pytest.fixture(scope="session")
def tmp_project():
    """
    Bootstrap a complete isolated project in the temp directory.
    Returns the project name string.
    """
    project_name = "IntegrationTestProject"

    # Import after env is set
    from config import PROJECTS_ROOT
    from storage.db import init_db

    project_dir = os.path.join(PROJECTS_ROOT, project_name)
    os.makedirs(project_dir, exist_ok=True)
    init_db(project_dir)

    return project_name


@pytest.fixture(scope="session")
def tmp_build_manifest(tmp_project):
    """
    Creates a minimal valid BuildManifest YAML file.
    Returns (project_name, build_name) tuple.
    """
    from config import PROJECTS_ROOT

    project_dir = os.path.join(PROJECTS_ROOT, tmp_project)
    builds_dir = os.path.join(project_dir, "builds")
    os.makedirs(builds_dir, exist_ok=True)

    build_name = "test-build"
    manifest = {
        "name": build_name,
        "version": "1.0.0",
        "schema_version": 1,
        "output": {"format": "single_file", "filename": "output.md"},
        "steps": [{"action": "append_text", "content": "# Integration Test Build"}],
    }
    manifest_path = os.path.join(builds_dir, f"{build_name}.yaml")
    with open(manifest_path, "w") as f:
        yaml.safe_dump(manifest, f)

    return tmp_project, build_name
