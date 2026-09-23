"""Coordinator, learner, notifications, knowledge, tracker, and file endpoints."""

import json
from pathlib import Path

from conftest import wait_for
from fastapi.testclient import TestClient


def create(client: TestClient, number: int, **fields: object) -> None:
    body = {
        "task": number,
        "title": f"Task {number}",
        "description": "Completes at once",
        "branch": f"feature/task-{number}",
        "repos": ["app"],
        "assign": "fake",
        **fields,
    }
    assert client.post("/api/tasks", json=body).status_code == 200


def completed(workspace: Path, number: int) -> bool:
    runs = json.loads((workspace.parent / "state" / "runs.json").read_text())["runs"]
    return any(item["task_number"] == number and item["run_status"] == "completed" for item in runs)


def test_coordinator_once_start_and_stop(client: TestClient, workspace: Path, prefix: str) -> None:
    create(client, 1)
    client.post("/api/runs/trigger", json={"tasks": [1]})
    wait_for(lambda: completed(workspace, 1))
    once = client.post("/api/coordinator/once").json()
    assert once["processed"] == 1
    assert once["message"] == "Processed=1 invalid=0 dead_sessions=0"
    notes = client.get("/api/snapshot").json()["notifications"]
    assert notes[0]["notification_type"] == "task_completed"
    assert notes[0]["details"]["validation_issues"] == []

    started = client.post("/api/coordinator/start").json()
    assert started["message"] == f"Coordinator started: {prefix}-coordinator"
    again = client.post("/api/coordinator/start").json()
    assert again["message"] == f"Coordinator already running: {prefix}-coordinator"
    wait_for(lambda: client.get("/api/snapshot").json()["coordinator"]["running"])
    stopped = client.post("/api/coordinator/stop").json()
    assert stopped["message"] == f"Coordinator stopped: {prefix}-coordinator"
    assert client.post("/api/coordinator/stop").json()["message"] == "Coordinator is not running"


def test_learner_start_status_stop(client: TestClient, prefix: str) -> None:
    started = client.post("/api/learner/start", json={"agent": "fake"}).json()
    assert started["message"] == "Learner started"
    assert client.post("/api/learner/start", json={}).json()["message"] == "Learner already running"
    learner = wait_for(
        lambda: (value := client.get("/api/snapshot").json()["learner"])["running"] and value
    )
    assert learner == {"session_name": f"{prefix}-learner", "running": True, "agent": "fake"}
    prompt = client.get("/api/prompts/learner.md").json()
    assert prompt["exists"] is True
    assert "Alfred Knowledge Learner" in prompt["content"]
    killed = client.post(f"/api/sessions/{prefix}-learner/kill", json={}).json()
    assert killed["message"] == "Learner stopped"
    assert client.post("/api/learner/stop").json()["message"] == "Learner is not running"
    missing = client.post("/api/learner/start", json={"agent": "ghost"})
    assert "Unknown agent 'ghost'" in missing.json()["error"]


def test_notifications_ack_and_clear(client: TestClient, workspace: Path) -> None:
    create(client, 2)
    client.post("/api/runs/trigger", json={"tasks": [2]})
    wait_for(lambda: completed(workspace, 2))
    client.post("/api/coordinator/once")
    acknowledged = client.post("/api/notifications/ack", json={"task": 2}).json()
    assert acknowledged["count"] == 1
    assert client.post("/api/notifications/clear").json()["count"] == 1
    assert client.get("/api/snapshot").json()["notifications"] == []


def test_knowledge_add_list_and_read(client: TestClient) -> None:
    create(client, 3)
    added = client.post(
        "/api/knowledge",
        json={
            "task": 3,
            "category": "patterns",
            "title": "Health checks stay private",
            "content": "Return no customer data.",
            "agent": "fake",
            "files": ["src/health.py", " "],
            "modules": ["app"],
        },
    ).json()
    assert added["path"].endswith("-task-3-health-checks-stay-private.md")
    listing = client.get("/api/knowledge", params={"category": "patterns", "task": 3}).json()
    entry = listing["entries"][0]
    assert entry["title"] == "Health checks stay private"
    assert entry["files"] == ["src/health.py"]
    assert entry["repositories"] == ["app"]
    assert entry["summary"] == "Return no customer data."
    read = client.get("/api/knowledge/entry", params={"path": entry["relative"]}).json()
    assert read["task_number"] == 3
    escape = client.get("/api/knowledge/entry", params={"path": "../../config.toml"})
    assert escape.status_code == 400
    empty = client.post(
        "/api/knowledge", json={"task": 3, "category": "issues", "title": " ", "content": "x"}
    )
    assert empty.json()["error"] == "Knowledge title is required"
    assert client.get("/api/snapshot").json()["knowledge"]["by_task"] == {"3": 1}


def test_tracker_validate_apply_and_daily_notes(client: TestClient, workspace: Path) -> None:
    create(client, 4)
    tracker = client.get("/api/tracker").json()
    assert tracker["enabled"] is True
    assert tracker["issues"] == []
    assert "| 4 |" in tracker["canonical"]["content"]
    note = tracker["daily_notes"]["files"][0]["name"]
    daily = client.get(f"/api/tracker/daily/{note}").json()
    assert "Task 4" in daily["content"]
    assert client.get("/api/tracker/daily/..%2Fsecret.md").status_code in {400, 404}
    canonical = Path(tracker["canonical"]["path"])
    canonical.write_text(
        "\n".join(line for line in canonical.read_text().splitlines() if "| 4 |" not in line)
    )
    drift = client.get("/api/tracker", params={"task": 4}).json()["issues"]
    assert drift == ["Task 4 is missing from the canonical tracker"]
    applied = client.post("/api/sync/apply", json={"task": 4}).json()
    assert applied["message"] == "Synchronized 1 task(s)"
    assert client.get("/api/tracker").json()["issues"] == []


def test_completion_files_and_state_documents(client: TestClient, workspace: Path) -> None:
    pending = workspace.parent / "tmp" / "completions" / "pending"
    pending.mkdir(parents=True)
    (pending / "task-9.json").write_text("{not json")
    listing = client.get("/api/completions").json()
    assert listing["pending"][0]["task_number"] == 9
    assert listing["pending"][0]["error"]
    cycle = client.post("/api/coordinator/once").json()
    assert cycle["invalid"] == 1
    assert client.get("/api/completions").json()["invalid"][0]["name"] == "task-9.json"
    document = client.get("/api/state/tasks").json()
    assert json.loads(document["content"])["schema_version"] == 1
    assert client.get("/api/state/secrets").status_code == 400
    assert client.get("/api/prompts/..%2F..%2Fconfig.toml").status_code in {400, 404}
