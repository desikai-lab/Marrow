import os

import pytest

pytestmark = pytest.mark.integration
UNIFORM = {"type": "Unauthorized", "message": "Invalid or missing credentials."}


def _url(project, tail="session-context"):
    return f"/api/v1/projects/{project}/{tail}"


def _assert_uniform_401(r):
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
    assert r.json()["error"] == UNIFORM


def test_valid_key_returns_200(client, rest_project, keys, auth):
    assert client.get(_url(rest_project), headers=auth(keys["a"])).status_code == 200
    assert client.get(_url(rest_project), headers=auth(keys["b"])).status_code == 200


@pytest.mark.parametrize(
    "case",
    ["no_header", "wrong_key", "short_key", "other_project_key", "global_token", "basic_scheme"],
)
def test_bad_credentials_return_uniform_401(client, rest_project, keys, auth, case):
    headers = {
        "no_header": {},
        "wrong_key": auth("mk_" + "Z" * 43),
        "short_key": auth("mk_short"),
        "other_project_key": auth(keys["other"]),
        "global_token": auth(os.environ["SECRET_TOKEN"]),
        "basic_scheme": {"Authorization": "Basic " + keys["a"]},
    }[case]
    _assert_uniform_401(client.get(_url(rest_project), headers=headers))


def test_token_in_query_string_is_not_accepted(client, rest_project, keys):
    _assert_uniform_401(client.get(_url(rest_project) + "?token=" + keys["a"]))


@pytest.mark.parametrize("name", ["NoSuchProject", "%2e%2e", "a" * 100, "RestKeyless"])
def test_unknown_or_keyless_or_malicious_project_returns_uniform_401(client, keys, auth, name):
    _assert_uniform_401(client.get(_url(name), headers=auth(keys["a"])))


def test_rotation_revokes_old_key_on_next_request(client, rotating_project, keys, auth):
    from common.path_resolver import get_settings_path

    assert client.get(_url(rotating_project), headers=auth(keys["a"])).status_code == 200
    path = get_settings_path(rotating_project)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"API_KEYS=new:{keys['b']}\n")  # later line wins in the raw parser
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    _assert_uniform_401(client.get(_url(rotating_project), headers=auth(keys["a"])))
    assert client.get(_url(rotating_project), headers=auth(keys["b"])).status_code == 200


def test_docs_and_schema_routes_are_not_served(client):
    for path in ("/docs", "/redoc", "/openapi.json", "/api/v1/docs", "/api/v1/openapi.json"):
        assert client.get(path).status_code == 404


def test_unknown_route_with_valid_key_returns_404_envelope(client, rest_project, keys, auth):
    r = client.get(_url(rest_project, "nope"), headers=auth(keys["a"]))
    assert r.status_code == 404 and r.json()["error"]["type"] == "NotFound"
