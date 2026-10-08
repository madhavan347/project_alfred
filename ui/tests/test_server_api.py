"""The server panel: offline frontend rebuild, staleness, and self-restart."""

import os
import sys
import threading
import time
from pathlib import Path

import pytest
from conftest import TOKEN, wait_for
from fastapi.testclient import TestClient

from alfred_ui import cli
from alfred_ui.app import create_app
from alfred_ui.security import TokenPolicy
from alfred_ui.updater import Updater, newest_mtime
from alfred_ui.workspace import WorkspaceContext


def checkout(root: Path) -> Path:
    """Lay out a minimal ui/ checkout with frontend sources, node_modules, and a build."""
    web = root / "web"
    (web / "src").mkdir(parents=True)
    (web / "node_modules").mkdir()
    (web / "package.json").write_text("{}", encoding="utf-8")
    (web / "src" / "main.ts").write_text("export {}", encoding="utf-8")
    static = root / "src" / "alfred_ui" / "static"
    static.mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html>", encoding="utf-8")
    return static


def client_for(context: WorkspaceContext, updater: Updater) -> TestClient:
    app = create_app(
        context,
        policy=TokenPolicy(token=TOKEN),
        allowed_hosts=("testserver",),
        static_directory=None,
        updater=updater,
    )
    return TestClient(app, headers={"X-Alfred-Token": TOKEN})


def test_status_reports_versions_checkout_and_why_restart_is_unavailable(
    client: TestClient,
) -> None:
    status = client.get("/api/server").json()
    assert set(status["versions"]) == {"alfred", "ui"}
    assert status["git"]["available"] is True
    assert status["packages"]["alfred_ui"].endswith("alfred_ui")
    assert status["restart"] == {
        "available": False,
        "reason": "Only a server started with the alfred-ui command can restart itself",
    }
    refused = client.post("/api/server/restart")
    assert refused.status_code == 400
    assert "started with the alfred-ui command" in refused.json()["error"]


def test_rebuild_runs_the_build_and_reports_staleness(
    context: WorkspaceContext, tmp_path: Path
) -> None:
    static = checkout(tmp_path)
    source = tmp_path / "web" / "src" / "main.ts"
    later = time.time() + 60
    os.utime(source, (later, later))
    script = (
        "import pathlib; pathlib.Path('../src/alfred_ui/static/index.html').touch(); print('ok')"
    )
    updater = Updater(ui_root=tmp_path, command=(sys.executable, "-c", script))
    with client_for(context, updater) as client:
        before = client.get("/api/server").json()
        assert before["frontend"]["stale"] is True
        assert before["rebuild"] == {"available": True, "reason": ""}
        os.utime(static / "index.html", (later - 120, later - 120))
        built = client.post("/api/server/rebuild").json()
        assert built["ok"] is True
        assert built["output"].strip() == "ok"
        os.utime(source, (time.time() - 60, time.time() - 60))
        assert client.get("/api/server").json()["frontend"]["stale"] is False

        failing = Updater(ui_root=tmp_path, command=(sys.executable, "-c", "raise SystemExit(3)"))
    with client_for(context, failing) as client:
        result = client.post("/api/server/rebuild").json()
        assert result["ok"] is False
        assert "exit 3" in result["message"]


def test_rebuild_is_refused_outside_a_ready_checkout(
    context: WorkspaceContext, tmp_path: Path
) -> None:
    missing = Updater(ui_root=tmp_path / "installed")
    assert "not a checkout" in missing.rebuild_problem()
    checkout(tmp_path)
    (tmp_path / "web" / "node_modules").rmdir()
    assert "Run npm ci" in Updater(ui_root=tmp_path).rebuild_problem()
    (tmp_path / "web" / "node_modules").mkdir()
    other = Updater(ui_root=tmp_path, static_directory=tmp_path / "elsewhere")
    assert "--static-dir" in other.rebuild_problem()
    absent = Updater(ui_root=tmp_path, command=("no-such-builder-xyz",))
    assert "not on this server's PATH" in absent.rebuild_problem()
    with client_for(context, absent) as client:
        refused = client.post("/api/server/rebuild")
        assert refused.status_code == 400


def test_restart_is_requested_after_the_response(context: WorkspaceContext, tmp_path: Path) -> None:
    fired = threading.Event()
    updater = Updater(ui_root=tmp_path, restart=fired.set)
    with client_for(context, updater) as client:
        assert client.get("/api/server").json()["restart"]["available"] is True
        response = client.post("/api/server/restart").json()
        assert response["message"] == "Restarting the server"
        assert wait_for(fired.is_set, timeout=5)


def test_restart_arguments_keep_the_port_and_workspace(tmp_path: Path) -> None:
    config = tmp_path / ".alfred" / "config.toml"
    arguments = cli.restart_arguments(
        ["--open", "--log-level", "info", "--port", "0"], port=8123, config=config
    )
    assert arguments == [
        "--log-level",
        "info",
        "--port",
        "0",
        "--port",
        "8123",
        "--config",
        str(config),
    ]
    parsed = cli.build_parser().parse_args(arguments)
    assert (parsed.port, parsed.config, parsed.open) == (8123, config, False)
    assert cli.restart_arguments([], port=9000, config=None) == ["--port", "9000"]


def test_restart_request_stops_the_server() -> None:
    class Server:
        should_exit = False

    request = cli.RestartRequest()
    request()
    assert request.requested is True
    server = Server()
    request.server = server  # type: ignore[assignment]
    request()
    assert server.should_exit is True


def test_newest_mtime_skips_dependencies(tmp_path: Path) -> None:
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.py").write_text("", encoding="utf-8")
    (tmp_path / "own.py").write_text("", encoding="utf-8")
    os.utime(tmp_path / "own.py", (1000, 1000))
    assert newest_mtime([tmp_path], suffix=".py") == pytest.approx(1000)
    assert newest_mtime([tmp_path / "missing"]) is None


def test_a_real_server_restarts_on_the_same_port_with_the_same_token(workspace: Path) -> None:
    import json
    import re
    import subprocess
    import urllib.request

    process = subprocess.Popen(
        [str(Path(sys.executable).parent / "alfred-ui"), "--config", str(workspace), "--port", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={key: value for key, value in os.environ.items() if key != "ALFRED_UI_TOKEN"},
    )
    try:
        assert process.stdout is not None
        link = ""
        while not link:
            line = process.stdout.readline()
            assert line, "alfred-ui exited before printing its link"
            if match := re.search(r"http://127\.0\.0\.1:(\d+)/\?token=(\S+)", line):
                link = match.group(0)
                port, token = match.group(1), match.group(2)

        def call(path: str, method: str = "GET") -> dict[str, object]:
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api{path}",
                method=method,
                headers={"X-Alfred-Token": token, "Content-Type": "application/json"},
                data=b"{}" if method == "POST" else None,
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.loads(response.read())  # type: ignore[no-any-return]

        first = call("/server")["started_at"]
        assert call("/server/restart", "POST")["message"] == "Restarting the server"

        def restarted() -> bool:
            try:
                return call("/server")["started_at"] != first
            except OSError:
                return False

        assert wait_for(restarted, timeout=30)
        # The same process image was replaced in place, and the old token still works.
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=10)
