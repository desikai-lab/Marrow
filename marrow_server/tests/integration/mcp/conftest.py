import os

import pytest
import yaml


def pytest_configure(config):
    """Set integration env vars BEFORE any module (config.py) is imported."""
    os.environ.setdefault("SECRET_TOKEN", "test-token-integration")
    # TASKS_DIR set later per-session via tmp_path_factory; setdefault avoids
    # overriding if already set by the user's env for the unit test run.


@pytest.fixture(scope="session")
def tmp_project(tmp_path_factory):
    """
    Bootstrap a complete isolated project in a temp directory.
    Returns the project name string.
    """
    base = tmp_path_factory.mktemp("marrow_integration")
    # Must set BEFORE importing config (config reads os.environ at import time)
    os.environ["TASKS_DIR"] = str(base)
    os.environ["SECRET_TOKEN"] = "test-token-integration"

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
