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


def test_task_type_and_model_round_trip(client: TestClient, workspace: Path) -> None:
    create(client, 9, type="research", model="any-model", branch="")
    record = task(workspace, 9)
    assert record["task_type"] == "research"
    assert record["model"] == "any-model"
    # Research and analysis never need a branch, so Alfred turns worktrees off.
    assert record["worktree_mode"] == "disabled"
    derived = client.get("/api/tasks/9").json()["task"]["derived"]
    assert derived["actions"]["worktree_create"]["reason"] == "Worktrees are disabled for this task"

    updated = client.patch("/api/tasks/9", json={"type": "analysis", "model": " other "})
    assert updated.status_code == 200
    record = task(workspace, 9)
    assert (record["task_type"], record["model"]) == ("analysis", "other")
    bad_type = client.patch("/api/tasks/9", json={"type": "chore"})
    assert bad_type.status_code == 400


def test_models_follow_the_agent_configuration(client: TestClient, workspace: Path) -> None:
    text = workspace.read_text(encoding="utf-8").replace(
        '[agents.recorder]\nruntime_target = "local-test"\n',
        '[agents.recorder]\nruntime_target = "local-test"\n'
        'models = ["small", "large"]\ndefault_model = "small"\n',
    )
    workspace.write_text(text, encoding="utf-8")
    agents = {
        item["alias"]: item for item in client.get("/api/snapshot").json()["config"]["agents"]
    }
    assert agents["recorder"]["models"] == ["small", "large"]
    assert agents["recorder"]["default_model"] == "small"
    assert agents["recorder"]["model"] == "small"

    create(client, 10, assign="")
    assigned = client.post("/api/tasks/10/assign", json={"agent": "recorder", "model": "large"})
    assert assigned.status_code == 200
    assert task(workspace, 10)["model"] == "large"
    refused = client.post("/api/tasks/10/reassign", json={"agent": "recorder", "model": "huge"})
    assert "configured models: small, large" in refused.json()["error"]
    kept = client.post("/api/tasks/10/reassign", json={"agent": "recorder"})
    assert kept.status_code == 200
    assert task(workspace, 10)["model"] == "large"


def test_cancel_from_any_stage(client: TestClient, workspace: Path) -> None:
    create(client, 11)
    client.post("/api/tasks/11/block", json={"reason": "Stuck"})
    assert client.get("/api/tasks/11").json()["task"]["derived"]["actions"]["cancel"]["enabled"]
    blank = client.post("/api/tasks/11/cancel", json={"reason": "  "})
    assert blank.json()["error"] == "A cancel reason is required"
    cancelled = client.post("/api/tasks/11/cancel", json={"reason": "No longer needed"})
    assert cancelled.json()["message"] == "Task 11: Cancelled"
    record = task(workspace, 11)
    assert (record["status"], record["lifecycle_phase"]) == ("Cancelled", "archived")
    derived = client.get("/api/tasks/11").json()["task"]["derived"]
    assert derived["actions"]["cancel"]["reason"] == "The task is finished"
    assert derived["actions"]["trigger"]["enabled"] is False
    again = client.post("/api/tasks/11/cancel", json={"reason": "Twice"})
    assert again.status_code == 400


def test_skills_can_be_listed_saved_and_removed(client: TestClient) -> None:
    listing = client.get("/api/skills").json()
    assert [item["phase"] for item in listing["skills"]] == ["plan", "execution"]
    assert not any(item["exists"] for item in listing["skills"])
    saved = client.put("/api/skills/plan", json={"content": "  Always list risks.  "})
    assert saved.json()["message"].startswith("Skill saved: ")
    plan = client.get("/api/skills").json()["skills"][0]
    assert (plan["exists"], plan["content"]) == (True, "Always list risks.")
    empty = client.put("/api/skills/execution", json={"content": " "})
    assert empty.json()["error"] == "Skill content must not be empty"
    unknown = client.put("/api/skills/review", json={"content": "x"})
    assert unknown.status_code == 400
    assert client.post("/api/skills/plan/remove").json()["removed"] is True
    assert client.post("/api/skills/plan/remove").json()["message"] == "No skill to remove"
