"""Workspace switching, initialization, configuration editing, health checks, and migration."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from alfred_ui.workspace import NoWorkspaceError, WorkspaceContext


def test_config_read_validate_save_and_snippets(client: TestClient, workspace: Path) -> None:
    payload = client.get("/api/config").json()
    assert payload["validation"]["valid"] is True
    assert {"claude", "codex", "agy", "recorder"} <= set(payload["presets"])
    summary = payload["validation"]["summary"]
    assert [agent["alias"] for agent in summary["agents"]] == ["fake", "recorder"]
    assert summary["repositories"][0]["is_git"] is True

    broken = client.post(
        "/api/config/validate", json={"text": payload["text"] + "\n[extra]\n"}
    ).json()
    assert broken == {"valid": False, "error": "Unknown keys in configuration: extra"}
    bad_zone = payload["text"].replace('timezone = "UTC"', 'timezone = "Mars/Olympus"')
    assert (
        "No time zone found"
        in client.post("/api/config/validate", json={"text": bad_zone}).json()["error"]
    )
    refused = client.put("/api/config", json={"text": "not toml ["})
    assert refused.status_code == 400
    assert "Configuration was not saved" in refused.json()["error"]

    repository = client.post(
        "/api/config/snippets/repository", json={"name": "docs", "path": "docs"}
    ).json()["text"]
    assert repository.startswith('[[repositories]]\nname = "docs"')
    agent = client.post(
        "/api/config/snippets/agent",
        json={
            "alias": "claude-opus",
            "direct": ["claude"],
            "plan": ["claude", "{prompt}"],
            "execution": ["claude", "--model", "opus", "{prompt}"],
        },
    ).json()["text"]
    saved = client.put("/api/config", json={"text": payload["text"] + "\n" + agent}).json()
    assert saved["backup"].endswith("config.toml.bak")
    agents = client.get("/api/snapshot").json()["config"]["agents"]
    opus = next(item for item in agents if item["alias"] == "claude-opus")
    assert opus["model"] == "opus"
    assert opus["cli"] == "Claude Code"
    assert opus["prompt_delivery"] == {
        "direct": "paste",
        "plan": "argument",
        "execution": "argument",
    }


def test_doctor_reports_real_conditions(client: TestClient, workspace: Path) -> None:
    fresh = {item["key"]: item for item in client.get("/api/doctor").json()["checks"]}
    assert fresh["state"]["status"] in {"info", "ok"}
    # Tracker files appear with the first task; until then the check says what is missing.
    assert fresh["tracker"]["status"] == "warn"
    assert "Markdown tracker file is missing" in fresh["tracker"]["detail"]
    client.post(
        "/api/tasks",
        json={"task": 1, "title": "First", "description": "d", "branch": "feature/first-1"},
    )
    checks = {item["key"]: item for item in client.get("/api/doctor").json()["checks"]}
    for key in (
        "config",
        "state",
        "git",
        "tmux",
        "alfred-path",
        "discovery",
        "agent-executables",
        "tracker",
    ):
        assert checks[key]["status"] == "ok", checks[key]
    assert checks["repository:app"]["status"] == "ok"
    assert checks["knowledge"]["status"] == "info"

    text = workspace.read_text().replace('path = "library"', 'path = "missing-library"')
    text = text.replace(
        'execution = ["tail", "-f", "/dev/null"]', 'execution = ["no-such-agent-cli"]'
    )
    workspace.write_text(text)
    checks = {item["key"]: item for item in client.get("/api/doctor").json()["checks"]}
    assert checks["repository:library"]["status"] == "error"
    assert "no-such-agent-cli" in checks["agent-executables"]["detail"]


def test_open_initialize_and_migrate(client: TestClient, workspace: Path, tmp_path: Path) -> None:
    second = tmp_path / "second"
    initialized = client.post("/api/workspace/init", json={"root": str(second)}).json()
    assert initialized["config_path"] == str(second.resolve() / ".alfred" / "config.toml")
    snapshot = client.get("/api/snapshot").json()
    assert snapshot["workspace"]["config_path"] == initialized["config_path"]
    assert snapshot["tasks"] == []
    exists = client.post("/api/workspace/init", json={"root": str(second)})
    assert exists.status_code == 409

    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "tasks.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "task_number": 7,
                        "title": "Legacy",
                        "description": "Old",
                        "branch_name": "legacy/7",
                    }
                ]
            }
        )
    )
    (legacy / "queue.json").write_text(json.dumps({"queued_tasks": [7]}))
    migrated = client.post("/api/migrate", json={"source": str(legacy)}).json()
    assert migrated["message"] == "Legacy runtime migrated: tasks=1 runs=0 queued=1"
    assert migrated["already_migrated"] is False
    again = client.post("/api/migrate", json={"source": str(legacy)}).json()
    assert again["already_migrated"] is True
    assert client.get("/api/snapshot").json()["tasks"][0]["title"] == "Legacy"

    reopened = client.post(
        "/api/workspace/open", json={"path": str(workspace.parent.parent)}
    ).json()
    assert reopened["config_path"] == str(workspace)
    missing = client.post("/api/workspace/open", json={"path": str(tmp_path / "nowhere.toml")})
    assert missing.status_code == 400


def test_invalid_configuration_is_reported_not_fatal(client: TestClient, workspace: Path) -> None:
    workspace.write_text("unknown_top = true\n" + workspace.read_text())
    snapshot = client.get("/api/snapshot").json()
    assert snapshot["error"] == {
        "kind": "config",
        "message": "Unknown keys in configuration: unknown_top",
    }
    assert client.get("/api/config").json()["validation"]["valid"] is False
    assert client.post("/api/tasks/1/start", json={}).status_code == 400


def test_corrupt_state_is_reported(client: TestClient, workspace: Path) -> None:
    (workspace.parent / "state" / "runs.json").write_text('{"schema_version": 99, "runs": []}')
    snapshot = client.get("/api/snapshot").json()
    assert snapshot["error"]["kind"] == "state"
    assert "Unsupported state version 99" in snapshot["error"]["message"]


def test_no_workspace_context(tmp_path: Path) -> None:
    context = WorkspaceContext(start=tmp_path)
    assert context.config_path is None
    assert "No Alfred configuration found" in context.discovery_error
    try:
        context.require_path()
    except NoWorkspaceError as error:
        assert "No Alfred workspace is open" in str(error)
    else:  # pragma: no cover - the call above must raise
        raise AssertionError("expected NoWorkspaceError")
