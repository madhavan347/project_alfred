"""Task, review, and delivery endpoints behave exactly like the Alfred CLI."""

import json
from pathlib import Path

from fastapi.testclient import TestClient


def state(workspace: Path, name: str) -> list[dict[str, object]]:
    document = json.loads((workspace.parent / "state" / f"{name}.json").read_text())
    return document[name if name != "queue" else "queued_tasks"]


def task(workspace: Path, number: int) -> dict[str, object]:
    return next(item for item in state(workspace, "tasks") if item["task_number"] == number)


def create(client: TestClient, number: int, **fields: object) -> None:
    body = {
        "task": number,
        "title": f"Task {number}",
        "description": "Described",
        "branch": f"feature/task-{number}",
        "repos": ["app"],
        "assign": "fake",
        **fields,
    }
    response = client.post("/api/tasks", json=body)
    assert response.status_code == 200, response.text


def test_create_update_and_refuse_duplicates(client: TestClient, workspace: Path) -> None:
    create(client, 1, priority="P1", dependencies=[], dispatch="queued", mode="plan-execution")
    record = task(workspace, 1)
    assert record["status"] == "Queued"
    assert record["planning_state"] == "pending"
    assert record["priority"] == "P1"

    duplicate = client.post("/api/tasks", json={"task": 1, "title": "Again", "description": "x"})
    assert duplicate.status_code == 400
    assert "already exists" in duplicate.json()["error"]

    updated = client.patch(
        "/api/tasks/1", json={"title": "Renamed", "mode": "direct", "repos": ["library"]}
    )
    assert updated.json()["message"] == "Updated task 1"
    record = task(workspace, 1)
    assert record["title"] == "Renamed"
    assert record["planning_state"] == "not_required"
    assert record["target_repositories"] == ["library"]


def test_validation_errors_are_readable(client: TestClient) -> None:
    response = client.post(
        "/api/tasks",
        json={"task": 0, "title": " ", "description": "", "priority": "P9", "branch": ""},
    )
    assert response.status_code == 400
    message = response.json()["error"]
    for expected in (
        "task_number must be positive",
        "title is required",
        "priority must be one of",
    ):
        assert expected in message
    unknown = client.post(
        "/api/tasks",
        json={"task": 5, "title": "t", "description": "d", "branch": "b", "assign": "ghost"},
    )
    assert "Unknown agent 'ghost'" in unknown.json()["error"]
    missing = client.post("/api/tasks", json={"title": "t"})
    assert missing.status_code == 400
    assert missing.json()["kind"] == "validation"


def test_status_actions_follow_the_state_machine(client: TestClient, workspace: Path) -> None:
    create(client, 2)
    assert client.post("/api/tasks/2/start", json={}).json()["message"] == "Task 2: In Progress"
    assert client.post("/api/tasks/2/progress", json={"note": "Halfway"}).status_code == 200
    blank = client.post("/api/tasks/2/progress", json={"note": "  "})
    assert blank.status_code == 400
    assert (
        client.post("/api/tasks/2/block", json={"reason": "Waiting"}).json()["message"]
        == "Task 2: Blocked"
    )
    assert client.post("/api/tasks/2/unblock", json={}).json()["message"] == "Task 2: Pending"
    assert (
        client.post("/api/tasks/2/hold", json={"note": "Later"}).json()["message"]
        == "Task 2: On Hold"
    )
    events = [item for item in state(workspace, "events") if item["task_number"] == 2]
    assert events[-1]["event_type"] == "STATUS_ON_HOLD"
    assert events[-1]["details"] == "Later"
    assert client.post("/api/tasks/2/unblock", json={"note": "Resumed"}).status_code == 200


def test_review_merge_deploy_archive(client: TestClient, workspace: Path) -> None:
    create(client, 3)
    client.post("/api/tasks/3/start", json={})
    refused = client.post("/api/tasks/3/merge", json={"mr": "1"})
    assert refused.status_code == 400
    assert "must be approved" in refused.json()["error"]
    approved = client.post("/api/tasks/3/review", json={"decision": "approved", "note": "Good"})
    assert approved.json()["message"] == "Task 3: MR in Review"
    merged = client.post("/api/tasks/3/merge", json={"mr": "!7", "actor": "reviewer"})
    assert merged.status_code == 200
    assert task(workspace, 3)["lifecycle_phase"] == "testing_deployment"
    deployed = client.post("/api/tasks/3/deploy", json={"env": "sandbox", "result": "passed"})
    assert deployed.json()["message"] == "Task 3: Completed"
    archived = client.post("/api/tasks/3/archive", json={})
    assert archived.status_code == 200
    assert task(workspace, 3)["lifecycle_phase"] == "archived"
    kinds = [item["event_type"] for item in state(workspace, "events") if item["task_number"] == 3]
    assert kinds[-4:] == [
        "MERGED",
        "PHASE_TESTING_DEPLOYMENT",
        "STATUS_COMPLETED",
        "PHASE_ARCHIVED",
    ]
    assert "REVIEW_APPROVED" in kinds


def test_changes_requested_and_consolidate(client: TestClient, workspace: Path) -> None:
    create(client, 4)
    client.post("/api/tasks/4/start", json={})
    client.post("/api/tasks/4/review", json={"decision": "approved", "note": "ok"})
    back = client.post(
        "/api/tasks/4/review", json={"decision": "changes_requested", "note": "Fix it"}
    )
    assert back.json()["message"] == "Task 4: In Progress"
    consolidated = client.post("/api/tasks/4/consolidate", json={"note": "Covered by 5"})
    assert consolidated.json()["message"] == "Task 4: Consolidated"
    assert task(workspace, 4)["lifecycle_phase"] == "consolidated"


def test_assign_and_reassign(client: TestClient, workspace: Path) -> None:
    create(client, 6, assign="")
    assigned = client.post("/api/tasks/6/assign", json={"agent": "recorder", "dispatch": "queued"})
    assert assigned.json()["message"] == "Task 6 assigned to recorder"
    assert task(workspace, 6)["status"] == "Queued"
    unknown = client.post("/api/tasks/6/assign", json={"agent": "ghost"})
    assert unknown.status_code == 400
    switched = client.post("/api/tasks/6/reassign", json={"agent": "fake", "mode": "soft-switch"})
    assert switched.json()["stopped"] is False
    assert task(workspace, 6)["assigned_agent_alias"] == "fake"


def test_missing_task_and_unknown_routes(client: TestClient) -> None:
    missing = client.post("/api/tasks/404/start", json={})
    assert missing.status_code == 400
    assert missing.json()["error"] == "Task 404 not found"
    assert client.get("/api/tasks/404").status_code == 400
    assert client.get("/api/nothing-here").status_code == 404


def test_reports_and_events(client: TestClient) -> None:
    create(client, 7, priority="P0")
    create(client, 8, dependencies=[7])
    client.post("/api/tasks/7/block", json={"reason": "stuck"})
    reports = client.get("/api/reports").json()
    assert reports["velocity"] == {"completed": 0, "total": 2}
    assert [row["task_number"] for row in reports["risk"]] == [7]
    assert reports["dependency"][0]["dependencies"] == [7]
    assert reports["by_status"] == {"Blocked": 1, "Pending": 1}
    listing = client.get("/api/events", params={"task": 7}).json()
    assert [item["event_type"] for item in listing["events"]] == ["TASK_UPSERTED", "STATUS_BLOCKED"]
    older = client.get("/api/events", params={"before": 1, "limit": 5}).json()
    assert [item["index"] for item in older["events"]] == [0]
