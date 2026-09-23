"""Health-check edge cases, report metrics over finished work, and serving the built interface."""

import subprocess
from pathlib import Path

from alfred.domain.constants import RunStatus, TaskStatus
from alfred.domain.models import AgentRun, Task
from fastapi.testclient import TestClient

from alfred_ui.app import create_app
from alfred_ui.doctor import fix_tmux_path, run_checks
from alfred_ui.reporting import build_reports
from alfred_ui.security import TokenPolicy
from alfred_ui.tmux_inspector import TmuxInspector
from alfred_ui.workspace import WorkspaceContext


def checks_for(
    context: WorkspaceContext, inspector: TmuxInspector | None = None
) -> dict[str, dict[str, object]]:
    return {item["key"]: item for item in run_checks(context, inspector or TmuxInspector())}


def test_agent_command_warnings(workspace: Path) -> None:
    text = workspace.read_text()
    text += """
[agents.claude]
runtime_target = "claude-code"

[agents.claude.commands]
direct = ["claude"]
plan = ["claude"]
execution = ["claude"]

[agents.broken]
runtime_target = "x"

[agents.broken.commands]
direct = ["tail", "{task_number}", "{prompt}"]
plan = ["tail", "{nope}"]
execution = ["tail"]
"""
    workspace.write_text(text)
    checks = checks_for(WorkspaceContext(workspace))
    assert checks["agent:claude"]["status"] == "warn"
    assert "prompts are pasted into a new session" in str(checks["agent:claude"]["detail"])
    assert checks["agent:broken"]["status"] == "error"
    assert "plan: nope" in str(checks["agent:broken"]["detail"])
    assert checks["agent:fake"]["status"] == "ok"


def test_repository_without_remote_or_branch(workspace: Path) -> None:
    app = workspace.parent.parent / "app"
    subprocess.run(["git", "remote", "remove", "origin"], cwd=app, check=True)
    workspace.write_text(
        workspace.read_text().replace('default_branch = "main"', 'default_branch = "trunk"', 1)
    )
    detail = str(checks_for(WorkspaceContext(workspace))["repository:app"]["detail"])
    assert "default branch 'trunk' does not exist" in detail
    assert "remote 'origin' is not configured" in detail


def test_missing_tmux_and_missing_workspace(workspace: Path, tmp_path: Path) -> None:
    offline = TmuxInspector(executable_finder=lambda _: None)
    checks = checks_for(WorkspaceContext(workspace), offline)
    assert checks["tmux"]["status"] == "warn"
    assert "tmux_unavailable_policy" in str(checks["tmux"]["detail"])
    nothing = run_checks(WorkspaceContext(start=tmp_path), offline)
    assert nothing[0]["key"] == "workspace"
    assert nothing[0]["status"] == "error"
    workspace.write_text("version = 2\n")
    broken = checks_for(WorkspaceContext(workspace), offline)
    assert broken["config"]["status"] == "error"


def test_fix_tmux_path_adds_this_installation(prefix: str) -> None:
    inspector = TmuxInspector()
    subprocess.run(["tmux", "new-session", "-d", "-s", f"{prefix}-path", "sleep 20"], check=True)
    try:
        subprocess.run(["tmux", "set-environment", "-g", "PATH", "/usr/bin:/bin"], check=True)
        message = fix_tmux_path(inspector)
        assert message.startswith("Added ")
        assert fix_tmux_path(inspector).endswith("is already on the tmux PATH")
        path = inspector.global_environment("PATH") or ""
        assert path.startswith("/usr/bin:/bin:")
    finally:
        subprocess.run(["tmux", "kill-session", "-t", f"={prefix}-path"], check=False)


def test_reports_over_finished_work() -> None:
    tasks = (
        Task(
            1,
            "Done",
            "d",
            status=TaskStatus.COMPLETED,
            created_at="2026-01-01T00:00:00+00:00",
            branch_name="b",
        ),
        Task(
            2,
            "Open",
            "d",
            status=TaskStatus.BLOCKED,
            priority="P0",
            branch_name="b",
            dependencies=[1],
        ),
    )
    runs = (
        AgentRun(
            "r1",
            1,
            "fake",
            "local",
            RunStatus.COMPLETED,
            started_at="2026-01-01T00:00:00+00:00",
            ended_at="2026-01-01T01:30:00+00:00",
        ),
        AgentRun(
            "r2",
            2,
            "fake",
            "local",
            RunStatus.STOPPED,
            started_at="2026-01-01T00:00:00+00:00",
            ended_at="2026-01-01T00:10:00+00:00",
        ),
        AgentRun("r3", 2, "fake", "local", RunStatus.RUNNING, started_at="bad"),
    )
    events = [
        {
            "task_number": 1,
            "event_type": "STATUS_COMPLETED",
            "timestamp": "2026-01-01T03:00:00+00:00",
        },
        {
            "task_number": 1,
            "event_type": "PHASE_ARCHIVED",
            "timestamp": "2026-01-02T03:00:00+00:00",
        },
        {
            "task_number": 2,
            "event_type": "STATUS_BLOCKED",
            "timestamp": "2026-01-02T03:00:00+00:00",
        },
    ]
    reports = build_reports(tasks, runs, events)
    assert reports["velocity"] == {"completed": 1, "total": 2}
    assert reports["throughput"] == [
        {"day": "2026-01-01", "count": 1},
        {"day": "2026-01-02", "count": 1},
    ]
    assert reports["cycle_times"] == [{"task_number": 1, "title": "Done", "hours": 3.0}]
    assert reports["runs"]["average_hours_by_agent"] == {"fake": 1.5}
    assert reports["runs"]["by_status"] == {"completed": 1, "stopped": 1, "running": 1}
    assert [row["task_number"] for row in reports["risk"]] == [2]


def test_built_interface_is_served_with_history_fallback(workspace: Path, tmp_path: Path) -> None:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>Alfred</title>")
    (static / "assets" / "app.js").write_text("console.log(1)")
    (static / "favicon.svg").write_text("<svg/>")
    app = create_app(
        WorkspaceContext(workspace),
        policy=TokenPolicy(token=None),
        allowed_hosts=("testserver",),
        static_directory=static,
    )
    client = TestClient(app)
    assert client.get("/").text.startswith("<!doctype html>")
    assert client.get("/tasks/12").headers["cache-control"] == "no-cache"
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/favicon.svg").text == "<svg/>"
    assert client.get("/api/unknown").status_code == 404
    missing = create_app(
        WorkspaceContext(workspace),
        allowed_hosts=("testserver",),
        static_directory=tmp_path / "none",
    )
    page = TestClient(missing).get("/")
    assert page.status_code == 503
    assert "npm install" in page.text
