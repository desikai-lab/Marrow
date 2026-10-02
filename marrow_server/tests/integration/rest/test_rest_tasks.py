import pytest

pytestmark = pytest.mark.integration
TASK = {
    "title": "REST-TEST: roundtrip",
    "type": "TD",
    "priority": "low",
    "problem": "p",
    "solution": "s",
}


def test_tasks_roundtrip_add_search_get_update_complete(client, rest_project, keys, auth):
    base, h = f"/api/v1/projects/{rest_project}", auth(keys["a"])
    added = client.post(f"{base}/tasks", json={"tasks": [TASK]}, headers=h)
    assert added.status_code == 200
    task_id = added.json()["result"]["created_task_ids"][0]
    found = client.get(f"{base}/tasks", params={"status": "open"}, headers=h).json()["result"]
    assert task_id in [t["id"] for t in found]
    detail = client.get(f"{base}/tasks/{task_id}", headers=h).json()["result"]
    assert detail["title"] == TASK["title"]
    upd = client.patch(f"{base}/tasks/{task_id}", json={"updates": {"priority": "high"}}, headers=h)
    # Real MCP shape: TaskUpdateResult(status, task={id, status, updated}).
    assert upd.status_code == 200 and upd.json()["result"]["status"] == "success"
    assert upd.json()["result"]["task"]["id"] == task_id
    detail = client.get(f"{base}/tasks/{task_id}", headers=h).json()["result"]
    assert detail["priority"] == "high"
    assert (
        client.post(f"{base}/tasks/complete", json={"task_ids": [task_id]}, headers=h).status_code
        == 200
    )
    every = client.get(f"{base}/tasks", params={"status": "all"}, headers=h).json()["result"]
    # Real MCP shape: complete_tasks closes with status "closed" (TaskStatus.closed).
    assert any(t["id"] == task_id and t["status"] == "closed" for t in every)


def test_add_tasks_duplicate_title_returns_422_validation_error(client, rest_project, keys, auth):
    url, h = f"/api/v1/projects/{rest_project}/tasks", auth(keys["a"])
    payload = {"tasks": [{**TASK, "title": "REST-TEST: duplicate"}]}
    client.post(url, json=payload, headers=h)
    r = client.post(url, json=payload, headers=h)
    assert r.status_code == 422 and r.json()["error"]["type"] == "ValidationError"


def test_get_task_details_unknown_id_returns_404(client, rest_project, keys, auth):
    r = client.get(f"/api/v1/projects/{rest_project}/tasks/TD999999", headers=auth(keys["a"]))
    assert r.status_code == 404 and r.json()["error"]["type"] == "TaskNotFoundError"


def test_add_tasks_invalid_body_without_key_returns_401_not_422(client, rest_project):
    r = client.post(f"/api/v1/projects/{rest_project}/tasks", json={"tasks": "nope"})
    assert r.status_code == 401


def test_add_tasks_invalid_body_with_key_returns_422(client, rest_project, keys, auth):
    r = client.post(
        f"/api/v1/projects/{rest_project}/tasks", json={"tasks": "nope"}, headers=auth(keys["a"])
    )
    assert r.status_code == 422
