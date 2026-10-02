import os

import pytest

pytestmark = pytest.mark.integration


def _url(project):
    return f"/api/v1/projects/{project}/session-context"


def test_rest_is_reachable_through_the_root_app(root_client, rest_project, keys, auth):
    assert root_client.get(_url(rest_project), headers=auth(keys["a"])).status_code == 200


def test_global_token_is_rejected_on_rest_routes(root_client, rest_project, auth):
    assert (
        root_client.get(_url(rest_project), headers=auth(os.environ["SECRET_TOKEN"])).status_code
        == 401
    )


def test_project_key_is_rejected_on_mcp_endpoint(root_client, keys, auth):
    assert root_client.post("/mcp", headers=auth(keys["a"]), json={}).status_code == 401


def test_project_key_is_rejected_on_vectorize_endpoint(root_client, keys, auth):
    assert root_client.post("/api/vectorize", headers=auth(keys["a"]), json={}).status_code == 401


def test_legacy_docs_unchanged_and_rest_docs_absent(root_client):
    assert root_client.get("/docs").status_code == 200
    assert root_client.get("/api/v1/docs").status_code == 404


def test_rest_responses_do_not_inherit_wildcard_cors(root_client, rest_project, keys, auth):
    headers = {**auth(keys["a"]), "Origin": "https://evil.example"}
    assert (
        "access-control-allow-origin"
        not in root_client.get(_url(rest_project), headers=headers).headers
    )
