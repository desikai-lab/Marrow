import os
import tempfile
import uuid

import pytest

os.environ.setdefault("TASKS_DIR", tempfile.mkdtemp(prefix="marrow_rest_integration_"))
os.environ.setdefault("SECRET_TOKEN", "test-token-integration")

KEY_A = "mk_" + "A" * 43
KEY_B = "mk_" + "B" * 43
KEY_OTHER = "mk_" + "C" * 43


def _scaffold(name: str, api_keys: str | None) -> str:
    from common.path_resolver import get_settings_path
    from config import PROJECTS_ROOT
    from storage.db import init_db
    from tools.projects import init_project_logic

    init_project_logic(name, "default")
    project_dir = os.path.join(PROJECTS_ROOT, name)
    init_db(project_dir)
    if api_keys is not None:
        with open(get_settings_path(name), "a", encoding="utf-8") as f:
            f.write(f"\nAPI_KEYS={api_keys}\n")
    return name


@pytest.fixture(scope="session")
def rest_project():
    return _scaffold("RestProject", f"zapier:{KEY_A},acme:{KEY_B}")


@pytest.fixture(scope="session")
def other_project():
    return _scaffold("RestOther", f"other:{KEY_OTHER}")


@pytest.fixture(scope="session")
def keyless_project():
    return _scaffold("RestKeyless", None)


@pytest.fixture()
def rotating_project():
    return _scaffold(f"RestRotate{uuid.uuid4().hex[:6]}", f"old:{KEY_A}")


@pytest.fixture(scope="session")
def keys():
    return {"a": KEY_A, "b": KEY_B, "other": KEY_OTHER}


@pytest.fixture(scope="session")
def auth():
    return lambda key: {"Authorization": f"Bearer {key}"}


@pytest.fixture(scope="session")
def client(rest_project, other_project, keyless_project):
    from fastapi.testclient import TestClient
    from transport.rest.app import rest_app

    return TestClient(rest_app, raise_server_exceptions=False)
