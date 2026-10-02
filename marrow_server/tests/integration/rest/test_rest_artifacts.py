import pytest

pytestmark = pytest.mark.integration


def test_artifacts_write_read_list_delete_roundtrip(client, rest_project, keys, auth):
    base, h = f"/api/v1/projects/{rest_project}", auth(keys["a"])
    item = {"path": "docs/rest_probe.md", "content": "# Probe\n\nhello\n", "mode": "replace_file"}
    w = client.post(f"{base}/artifacts/write", json={"updates": [item]}, headers=h)
    assert w.status_code == 200 and w.json()["result"][0]["path"] == "docs/rest_probe.md"
    r = client.post(
        f"{base}/artifacts/read",
        json={"reads": [{"path": item["path"], "mode": "full"}]},
        headers=h,
    )
    assert "hello" in r.json()["result"][0]["content"]
    listed = client.get(
        f"{base}/artifacts", params={"path": "docs", "recursive": "true"}, headers=h
    )
    assert any(i["name"].endswith("rest_probe.md") for i in listed.json()["result"])
    assert (
        client.get(
            f"{base}/artifacts/history", params={"path": item["path"]}, headers=h
        ).status_code
        == 200
    )
    assert (
        client.delete(f"{base}/artifacts", params={"path": item["path"]}, headers=h).status_code
        == 200
    )


def test_artifact_outline_missing_file_returns_system_error_envelope(
    client, rest_project, keys, auth
):
    # Real MCP shape: outline raises builtin FileNotFoundError, which
    # mcp_error_handler surfaces as a SystemError dict (HTTP 200). REST maps
    # unhandled exceptions to a 500 SystemError envelope (T3b) — no traceback.
    r = client.get(
        f"/api/v1/projects/{rest_project}/artifacts/outline",
        params={"path": "nope.md"},
        headers=auth(keys["a"]),
    )
    assert r.status_code == 500 and r.json()["error"]["type"] == "SystemError"
    assert "Traceback" not in r.text and r.json()["request_id"] == r.headers["x-request-id"]


def test_artifact_outline_traversal_path_is_rejected(client, rest_project, keys, auth):
    # Traversal fails validate_artifact_path -> same FileNotFoundError path as above.
    r = client.get(
        f"/api/v1/projects/{rest_project}/artifacts/outline",
        params={"path": "../../x.md"},
        headers=auth(keys["a"]),
    )
    assert r.status_code == 500 and r.json()["error"]["type"] == "SystemError"


def test_semantic_search_returns_enveloped_result(client, rest_project, keys, auth):
    r = client.post(
        f"/api/v1/projects/{rest_project}/search/semantic",
        json={"query": "planning", "limit": 3},
        headers=auth(keys["a"]),
    )
    assert r.status_code == 200 and "result" in r.json()


def test_text_search_returns_enveloped_list(client, rest_project, keys, auth):
    r = client.post(
        f"/api/v1/projects/{rest_project}/search/text",
        json={"query": "session"},
        headers=auth(keys["a"]),
    )
    assert r.status_code == 200 and isinstance(r.json()["result"], list)
