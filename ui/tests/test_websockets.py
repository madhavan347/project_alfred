"""The live channel and the terminal bridge, over real WebSockets, tmux, and the alfred CLI."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import wait_for
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def alfred(config: Path, *arguments: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "alfred", "--config", str(config), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout + result.stderr


def next_snapshot(socket: object) -> dict[str, object]:
    while True:
        message = json.loads(socket.receive_text())  # type: ignore[attr-defined]
        if message["type"] == "snapshot":
            return message["data"]  # type: ignore[no-any-return]


def test_live_channel_streams_changes_made_by_the_cli(client: TestClient, workspace: Path) -> None:
    with client.websocket_connect("/api/live") as socket:
        first = next_snapshot(socket)
        assert first["error"] is None
        assert first["tasks"] == []
        assert first["config"]["runtime"]["session_prefix"]
        output = alfred(
            workspace,
            "task",
            "create",
            "--task",
            "9",
            "--title",
            "From the CLI",
            "--description",
            "External",
            "--branch",
            "feature/cli-9",
            "--assign",
            "fake",
        )
        assert "Created task 9" in output
        update = next_snapshot(socket)
        while not update["tasks"]:
            update = next_snapshot(socket)
        task = update["tasks"][0]
        assert task["title"] == "From the CLI"
        assert task["derived"]["actions"]["trigger"]["enabled"] is True
        assert update["events"][-1]["event_type"] == "TASK_UPSERTED"
        socket.send_text(json.dumps({"type": "refresh"}))


def test_terminal_bridge_types_into_a_session_and_resizes_it(
    client: TestClient, prefix: str, workspace: Path
) -> None:
    name = f"{prefix}-5-fake"
    subprocess.run(["tmux", "new-session", "-d", "-s", name, "cat"], check=True)
    with client.websocket_connect(
        f"/api/terminal/{name}?mode=interactive&cols=90&rows=20"
    ) as socket:
        assert json.loads(socket.receive_text()) == {"type": "ready", "session": name}
        socket.send_text(json.dumps({"type": "resize", "cols": 101, "rows": 31}))
        socket.send_text(json.dumps({"type": "input", "data": "typed through the bridge\r"}))
        socket.send_bytes(b"raw bytes\r")

        def screen() -> str:
            result = subprocess.run(
                ["tmux", "capture-pane", "-p", "-t", f"={name}:"], capture_output=True, text=True
            )
            return result.stdout

        wait_for(lambda: "typed through the bridge" in screen() and "raw bytes" in screen())
        size = subprocess.run(
            ["tmux", "display", "-p", "-t", f"={name}:", "#{pane_width}x#{pane_height}"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert size == "101x30"
        socket.receive_bytes()
    wait_for(
        lambda: (
            subprocess.run(
                ["tmux", "display", "-p", "-t", f"={name}:", "#{session_attached}"],
                capture_output=True,
                text=True,
            ).stdout.strip()
            == "0"
        )
    )
    subprocess.run(["tmux", "kill-session", "-t", f"={name}"], check=True)


def test_terminal_reports_exit_when_the_session_ends(client: TestClient, prefix: str) -> None:
    name = f"{prefix}-6-fake"
    subprocess.run(["tmux", "new-session", "-d", "-s", name, "sleep 30"], check=True)
    with client.websocket_connect(f"/api/terminal/{name}?mode=readonly") as socket:
        assert json.loads(socket.receive_text())["type"] == "ready"
        subprocess.run(["tmux", "kill-session", "-t", f"={name}"], check=True)
        notices = []
        while True:
            message = socket.receive()
            if message["type"] == "websocket.close":
                break
            if message.get("text"):
                notices.append(json.loads(message["text"])["type"])
        assert "exit" in notices


@pytest.mark.parametrize(
    ("name", "expected"),
    [("missing-session", "does not belong"), ("{prefix}-99-fake", "is not running")],
)
def test_terminal_refuses_foreign_and_missing_sessions(
    client: TestClient, prefix: str, name: str, expected: str
) -> None:
    with client.websocket_connect(f"/api/terminal/{name.format(prefix=prefix)}") as socket:
        notice = json.loads(socket.receive_text())
        assert notice["type"] == "error"
        assert expected in notice["message"]
        with pytest.raises(WebSocketDisconnect):
            socket.receive_text()
