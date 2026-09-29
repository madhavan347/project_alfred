"""Git porcelain parsing, tmux output parsing and validation, and the command-line entry point."""

import errno
import json
import os
import signal
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest
from alfred.ports.process import ProcessResult

from alfred_ui import cli, gitinfo
from alfred_ui.tmux_inspector import (
    SEPARATOR,
    TmuxInspector,
    TmuxUnavailableError,
    validate_key,
    validate_session_name,
)


def test_porcelain_parses_renames_untracked_and_conflicts() -> None:
    output = "\0".join(
        ["R  new.txt", "old.txt", "?? notes.md", "UU both.py", " M edited.py", "D  gone.py", ""]
    )
    entries = gitinfo._porcelain(output)
    assert entries[0] == {
        "code": "R ",
        "path": "new.txt",
        "label": "renamed",
        "original": "old.txt",
    }
    assert [entry["label"] for entry in entries[1:]] == [
        "untracked",
        "conflict",
        "modified",
        "deleted",
    ]


def test_commit_log_and_counts_parsing() -> None:
    line = SEPARATOR.join(["abc123", "abc", "Ada", "2026-01-01T00:00:00Z", "Fix it"]).replace(
        SEPARATOR, "\x1f"
    )
    assert gitinfo._commits(line + "\nbroken") == [
        {
            "hash": "abc123",
            "short": "abc",
            "author": "Ada",
            "date": "2026-01-01T00:00:00Z",
            "subject": "Fix it",
        }
    ]
    assert gitinfo._capped("x" * 10) == {"text": "x" * 10, "truncated": False}
    capped = gitinfo._capped("y" * (gitinfo.MAX_DIFF_CHARACTERS + 5))
    assert capped["truncated"] is True


class FakeRunner:
    """Record tmux calls and answer from a script of outputs."""

    def __init__(self, outputs: dict[str, ProcessResult]) -> None:
        self.outputs = outputs
        self.calls: list[tuple[str, ...]] = []

    def run(
        self, arguments: tuple[str, ...], *, cwd: Path | None = None, check: bool = True
    ) -> ProcessResult:
        self.calls.append(arguments)
        result = self.outputs.get(arguments[1], ProcessResult(arguments, 0, "", ""))
        if check and result.returncode:
            raise RuntimeError("failed")
        return result


def fields(*values: str) -> str:
    return SEPARATOR.join(values)


def test_sessions_are_parsed_from_tmux_formats() -> None:
    pane = fields(
        "p-1-a",
        "0",
        "0",
        "1",
        "1",
        "%1",
        "42",
        "claude",
        "0",
        "",
        "120",
        "40",
        "3",
        "4",
        "100",
        "0",
        "1",
        "/work",
        "title",
        "with",
        "separators",
    )
    runner = FakeRunner(
        {
            "list-sessions": ProcessResult(
                (), 0, fields("p-1-a", "10", "20", "1", "1") + "\nmalformed\n", ""
            ),
            "list-panes": ProcessResult((), 0, pane + "\nshort\n", ""),
        }
    )
    inspector = TmuxInspector(runner, executable_finder=lambda _: "/usr/bin/tmux")
    (session,) = inspector.sessions()
    assert session.name == "p-1-a"
    assert session.active_pane is not None
    assert session.active_pane.current_command == "claude"
    assert session.active_pane.alternate_screen is True
    assert session.active_pane.title == fields("title", "with", "separators")
    assert session.to_dict()["pane"]["width"] == 120


def test_missing_tmux_is_handled() -> None:
    inspector = TmuxInspector(FakeRunner({}), executable_finder=lambda _: None)
    assert inspector.available() is False
    assert inspector.sessions() == ()
    assert inspector.version() == ""
    assert inspector.server_running() is False
    assert inspector.exists("p-1-a") is False
    assert inspector.global_environment("PATH") is None
    with pytest.raises(TmuxUnavailableError):
        inspector.capture("p-1-a")
    with pytest.raises(TmuxUnavailableError):
        inspector.set_global_environment("PATH", "/bin")


def test_no_server_means_no_sessions() -> None:
    runner = FakeRunner({"list-sessions": ProcessResult((), 1, "", "no server running")})
    inspector = TmuxInspector(runner, executable_finder=lambda _: "/usr/bin/tmux")
    assert inspector.sessions() == ()
    assert inspector.server_running() is False


def test_input_is_validated_before_reaching_tmux(tmp_path: Path) -> None:
    runner = FakeRunner({})
    inspector = TmuxInspector(runner, executable_finder=lambda _: "/usr/bin/tmux")
    for bad in ("", "has space", "semi;colon", "-dash"):
        with pytest.raises(ValueError):
            validate_session_name(bad)
    for bad in ("", "Enter;", "rm -rf", "C-", "ab"):
        with pytest.raises(ValueError):
            validate_key(bad)
    for good in ("Enter", "C-c", "y", "F12", "BTab"):
        validate_key(good)
    with pytest.raises(ValueError):
        inspector.send_keys("p-1-a", [])
    with pytest.raises(ValueError):
        inspector.send_text("p-1-a", "", submit=False, scratch_directory=tmp_path)
    with pytest.raises(ValueError):
        inspector.global_environment("BAD NAME")
    inspector.send_text(
        "p-1-a", "line one\nline two", submit=True, scratch_directory=tmp_path, bracketed=False
    )
    assert runner.calls[-3][1] == "load-buffer"
    assert runner.calls[-2][1:3] == ("paste-buffer", "-d")
    assert runner.calls[-1] == ("tmux", "send-keys", "-t", "=p-1-a:", "Enter")
    assert list(tmp_path.iterdir()) == []


def test_bind_moves_past_busy_ports() -> None:
    busy = socket.socket()
    busy.bind(("127.0.0.1", cli.DEFAULT_PORT))
    busy.listen()
    try:
        listener = cli.bind("127.0.0.1", None)
        assert listener.getsockname()[1] > cli.DEFAULT_PORT
        listener.close()
        with pytest.raises(OSError) as raised:
            cli.bind("127.0.0.1", cli.DEFAULT_PORT)
        assert raised.value.errno == errno.EADDRINUSE
    finally:
        busy.close()


def test_main_rejects_a_missing_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--config", str(tmp_path / "missing.toml")]) == 1
    assert "Alfred configuration does not exist" in capsys.readouterr().err


def test_expose_alfred_appends_only_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    cli.expose_alfred_to_sessions()
    entries = os.environ["PATH"].split(os.pathsep)
    assert entries[0] == str(tmp_path)
    assert len(entries) == 2
    cli.expose_alfred_to_sessions()
    assert os.environ["PATH"].split(os.pathsep) == entries


def test_url_host() -> None:
    assert cli._url_host("0.0.0.0") == "127.0.0.1"
    assert cli._url_host("::1") == "[::1]"
    assert cli._url_host("localhost") == "localhost"


def test_server_serves_and_stops_quietly_on_ctrl_c(workspace: Path) -> None:
    arguments = ["--config", str(workspace), "--port", "0", "--no-token"]
    process = subprocess.Popen(
        [sys.executable, "-m", "alfred_ui", *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        assert process.stdout is not None
        assert process.stdout.readline().startswith("Alfred UI ")
        url = process.stdout.readline().removeprefix("Open ").strip()
        with urllib.request.urlopen(f"{url}api/health", timeout=10) as response:
            assert json.load(response)["ok"] is True
        process.send_signal(signal.SIGINT)
        output, _ = process.communicate(timeout=20)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    assert process.returncode == 0
    assert "Traceback" not in output
