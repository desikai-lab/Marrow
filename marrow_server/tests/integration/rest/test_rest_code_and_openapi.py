import pytest

pytestmark = pytest.mark.integration


def _base(project):
    return f"/api/v1/projects/{project}"


def test_openapi_requires_a_valid_key(client, rest_project, keys, auth):
    assert client.get(f"{_base(rest_project)}/openapi.json").status_code == 401
    r = client.get(f"{_base(rest_project)}/openapi.json", headers=auth(keys["a"]))
    spec = r.json()
    assert r.status_code == 200 and spec["openapi"].startswith("3")
    assert "HTTPBearer" in spec["components"]["securitySchemes"]
    ids = {op["operationId"] for m in spec["paths"].values() for op in m.values()}
    assert (
        "get_session_context" in ids
        and "list_projects" not in ids
        and "run_project_build" not in ids
    )


def test_view_file_source_without_source_root_returns_200_string(client, rest_project, keys, auth):
    r = client.get(
        f"{_base(rest_project)}/code/source",
        params={"path": "a.py", "start_line": 1, "end_line": 2},
        headers=auth(keys["a"]),
    )
    assert r.status_code == 200
    assert r.json()["result"] == "Project does not provide access to code files."


def test_view_file_source_invalid_range_still_requires_key(client, rest_project):
    r = client.get(
        f"{_base(rest_project)}/code/source",
        params={"path": "a.py", "start_line": 1, "end_line": 2},
    )
    assert r.status_code == 401


def test_get_project_map_returns_enveloped_result(client, rest_project, keys, auth):
    r = client.get(f"{_base(rest_project)}/code/map", headers=auth(keys["a"]))
    assert r.status_code == 200 and "result" in r.json()
