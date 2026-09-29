"""Saved plain-text transcripts of agent sessions.

Alfred keeps an agent's plan and work only inside its tmux session, so the UI saves the full
scrollback when a plan is reported, when a run finishes, before the UI stops a run, or on request.
Transcripts live under the private temp directory next to Alfred's prompts.
"""

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alfred.config.models import AlfredConfig
from alfred.utils.files import atomic_write_text

from alfred_ui.artifacts import contained, file_info, read_text
from alfred_ui.tmux_inspector import TmuxInspector, validate_session_name

REASON = re.compile(r"[a-z][a-z_]{0,31}")
TRANSCRIPT_NAME = re.compile(r"(\d{8}T\d{12}Z)-([a-z_]+)-([A-Za-z0-9_-]+)\.txt")


class TranscriptStore:
    """Capture and list session transcripts for one workspace."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    @classmethod
    def for_config(cls, config: AlfredConfig) -> "TranscriptStore":
        """Return the store for a workspace configuration."""
        return cls(config.runtime.temp_directory / "ui" / "transcripts")

    def capture(
        self,
        inspector: TmuxInspector,
        session_name: str,
        *,
        task_number: int | None,
        reason: str,
    ) -> dict[str, Any]:
        """Save the complete scrollback of a live session."""
        validate_session_name(session_name)
        if not REASON.fullmatch(reason):
            raise ValueError(f"Invalid transcript reason {reason!r}")
        if not inspector.exists(session_name):
            raise ValueError(f"Session {session_name} is not running")
        pane = inspector.pane(session_name)
        content = inspector.capture(session_name, history=None, ansi=False, join=True)
        captured = datetime.now(UTC)
        stamp = captured.strftime("%Y%m%dT%H%M%S%fZ")
        folder = self.directory / (f"task-{task_number}" if task_number is not None else "sessions")
        path = folder / f"{stamp}-{reason}-{session_name}.txt"
        header = [
            "# Alfred session transcript",
            f"# Session: {session_name}",
            f"# Task: {task_number if task_number is not None else '-'}",
            f"# Reason: {reason}",
            f"# Captured: {captured.isoformat(timespec='seconds')}",
        ]
        if pane is not None:
            header.append(f"# Pane: {pane.width}x{pane.height}, running {pane.current_command}")
        atomic_write_text(path, "\n".join(header) + "\n\n" + content.rstrip() + "\n")
        return self.describe(path)

    def list(self, task_number: int | None = None) -> list[dict[str, Any]]:
        """Return transcripts, newest first, optionally for one task."""
        if not self.directory.is_dir():
            return []
        folders = (
            [self.directory / f"task-{task_number}"]
            if task_number is not None
            else [item for item in self.directory.iterdir() if item.is_dir()]
        )
        transcripts = [
            self.describe(path)
            for folder in folders
            if folder.is_dir()
            for path in folder.glob("*.txt")
            if TRANSCRIPT_NAME.fullmatch(path.name)
        ]
        return sorted(transcripts, key=lambda item: item["relative"].split("/")[-1], reverse=True)

    def read(self, relative: str) -> dict[str, Any]:
        """Read one transcript by its path relative to the transcript directory."""
        path = contained(self.directory, relative)
        if not path.is_file() or not TRANSCRIPT_NAME.fullmatch(path.name):
            raise ValueError(f"Transcript does not exist: {relative}")
        return {**self.describe(path), "content": read_text(path)}

    def describe(self, path: Path) -> dict[str, Any]:
        """Describe one transcript file."""
        match = TRANSCRIPT_NAME.fullmatch(path.name)
        folder = path.parent.name
        suffix = folder.removeprefix("task-")
        task_number = int(suffix) if folder.startswith("task-") and suffix.isdigit() else None
        return {
            **file_info(path, self.directory),
            "task_number": task_number,
            "reason": match.group(2) if match else "",
            "session_name": match.group(3) if match else "",
            "captured_at": _stamp(match.group(1)) if match else "",
        }


def _stamp(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=UTC).isoformat()
    except ValueError:
        return ""
