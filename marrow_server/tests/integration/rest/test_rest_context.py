import pytest

pytestmark = pytest.mark.integration


def _url(project, tail):
    return f"/api/v1/projects/{project}/{tail}"


def test_session_context_returns_enveloped_string(client, rest_project, keys, auth):
    r = client.get(_url(rest_project, "session-context"), headers=auth(keys["a"]))
    assert r.status_code == 200 and isinstance(r.json()["result"], str)
    assert r.json()["request_id"] == r.headers["x-request-id"]


def test_session_context_start_role_equals_operation_result(client, rest_project, keys, auth):
    from tools.session_context import get_session_context_logic

    r = client.get(
        _url(rest_project, "session-context"),
        params={"start_role": "planning"},
        headers=auth(keys["a"]),
    )
    assert r.json()["result"] == get_session_context_logic(rest_project, "planning")


def test_guideline_known_role_returns_bundle(client, rest_project, keys, auth):
    r = client.get(_url(rest_project, "guidelines/planning"), headers=auth(keys["a"]))
    assert r.status_code == 200 and "=== ROLE GUIDELINES ===" in r.json()["result"]


def test_guideline_unknown_role_returns_200_with_error_string(client, rest_project, keys, auth):
    r = client.get(_url(rest_project, "guidelines/no-such-role"), headers=auth(keys["a"]))
    assert r.status_code == 200 and isinstance(r.json()["result"], str)
