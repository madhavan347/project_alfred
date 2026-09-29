"""Read-mostly tmux inspection and explicit operator input for Alfred sessions.

Every target uses tmux's exact-match form (``=name`` for sessions, ``=name:`` for panes) because
a bare ``-t name`` also matches any session whose name merely starts with ``name``.
"""

import re
import shutil
import uuid
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from alfred.adapters.process import SubprocessRunner
from alfred.ports.process import ProcessResult, ProcessRunner
from alfred.utils.files import atomic_write_text

SEPARATOR = "\x1f"
SESSION_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
NAMED_KEYS = frozenset(
    {
        "Enter",
        "Escape",
        "Tab",
        "BTab",
        "Space",
        "BSpace",
        "Up",
        "Down",
        "Left",
        "Right",
        "Home",
        "End",
        "PageUp",
        "PageDown",
        "DC",
    }
)
SIMPLE_KEY = re.compile(r"[A-Za-z0-9]|C-[a-z]|M-[a-z]|F(?:[1-9]|1[0-2])")

SESSION_FIELDS = (
    "session_name",
    "session_created",
    "session_activity",
    "session_attached",
    "session_windows",
)
PANE_FIELDS = (
    "session_name",
    "window_index",
    "pane_index",
    "pane_active",
    "window_active",
    "pane_id",
    "pane_pid",
    "pane_current_command",
    "pane_dead",
    "pane_dead_status",
    "pane_width",
    "pane_height",
    "cursor_x",
    "cursor_y",
    "history_size",
    "pane_in_mode",
    "alternate_on",
    "pane_current_path",
    "pane_title",
)


class TmuxUnavailableError(RuntimeError):
    """Raised when an operation needs tmux but it cannot be found on PATH."""


@dataclass(frozen=True, slots=True)
class PaneInfo:
    """Observable state of one tmux pane."""

    session_name: str
    window_index: int
    pane_index: int
    active: bool
    pane_id: str
    pid: int
    current_command: str
    dead: bool
    dead_status: int | None
    width: int
    height: int
    cursor_x: int
    cursor_y: int
    history_size: int
    in_mode: bool
    alternate_screen: bool
    current_path: str
    title: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SessionInfo:
    """One tmux session and its panes."""

    name: str
    created: int
    activity: int
    attached: int
    windows: int
    panes: tuple[PaneInfo, ...]

    @property
    def active_pane(self) -> PaneInfo | None:
        """Return the active pane of the active window, or the first pane."""
        return next((pane for pane in self.panes if pane.active), None) or next(
            iter(self.panes), None
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation including the active pane."""
        pane = self.active_pane
        return {
            "name": self.name,
            "created": self.created,
            "activity": self.activity,
            "attached": self.attached,
            "windows": self.windows,
            "pane": pane.to_dict() if pane else None,
            "pane_count": len(self.panes),
        }


class TmuxInspector:
    """Inspect sessions and deliver explicitly requested operator input."""

    def __init__(
        self,
        runner: ProcessRunner | None = None,
        *,
        executable_finder: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self.runner: ProcessRunner = runner or SubprocessRunner()
        self.executable_finder = executable_finder

    def available(self) -> bool:
        """Return whether tmux can be located on PATH."""
        return self.executable_finder("tmux") is not None

    def version(self) -> str:
        """Return the tmux version string, or an empty string when unavailable."""
        if not self.available():
            return ""
        return self._run(("-V",), check=False).stdout.strip()

    def server_running(self) -> bool:
        """Return whether a tmux server is reachable on the current socket."""
        if not self.available():
            return False
        return self._run(("list-sessions", "-F", "#{session_name}"), check=False).returncode == 0

    def sessions(self) -> tuple[SessionInfo, ...]:
        """Return every session on the server, sorted by name."""
        if not self.available():
            return ()
        listing = self._run(("list-sessions", "-F", _format(SESSION_FIELDS)), check=False)
        if listing.returncode != 0:
            return ()
        panes = self._run(("list-panes", "-a", "-F", _format(PANE_FIELDS)), check=False)
        by_session: dict[str, list[PaneInfo]] = defaultdict(list)
        if panes.returncode == 0:
            for line in panes.stdout.splitlines():
                pane = _parse_pane(line)
                if pane is not None:
                    by_session[pane.session_name].append(pane)
        sessions: list[SessionInfo] = []
        for line in listing.stdout.splitlines():
            values = line.split(SEPARATOR)
            if len(values) != len(SESSION_FIELDS):
                continue
            name, created, activity, attached, windows = values
            sessions.append(
                SessionInfo(
                    name=name,
                    created=_int(created),
                    activity=_int(activity),
                    attached=_int(attached),
                    windows=_int(windows),
                    panes=tuple(by_session.get(name, ())),
                )
            )
        return tuple(sorted(sessions, key=lambda item: item.name))

    def exists(self, name: str) -> bool:
        """Return whether a session with exactly this name exists."""
        validate_session_name(name)
        if not self.available():
            return False
        return self._run(("has-session", "-t", f"={name}"), check=False).returncode == 0

    def pane(self, name: str) -> PaneInfo | None:
        """Return the active pane of one session."""
        validate_session_name(name)
        self._require_available()
        result = self._run(
            ("list-panes", "-t", f"={name}", "-F", _format(PANE_FIELDS)), check=False
        )
        if result.returncode != 0:
            return None
        panes = [pane for pane in map(_parse_pane, result.stdout.splitlines()) if pane]
        return next((pane for pane in panes if pane.active), None) or next(iter(panes), None)

    def capture(
        self,
        name: str,
        *,
        history: int | None = 0,
        ansi: bool = True,
        join: bool = False,
    ) -> str:
        """Capture the visible screen, recent history, or (``history=None``) everything."""
        validate_session_name(name)
        self._require_available()
        arguments = ["capture-pane", "-p", "-t", f"={name}:"]
        if ansi:
            arguments.append("-e")
        if join:
            arguments.append("-J")
        if history is None:
            arguments.extend(["-S", "-", "-E", "-"])
        elif history > 0:
            arguments.extend(["-S", str(-history)])
        return self._run(tuple(arguments)).stdout

    def send_text(
        self,
        name: str,
        text: str,
        *,
        submit: bool,
        scratch_directory: Path,
        bracketed: bool = True,
    ) -> None:
        """Paste text through a session-private buffer, then optionally press Enter."""
        validate_session_name(name)
        self._require_available()
        if not text and not submit:
            raise ValueError("Enter a message or choose to press Enter")
        target = f"={name}:"
        if text:
            buffer = f"alfred-ui-{name}"
            path = scratch_directory / f"message-{uuid.uuid4().hex}.txt"
            atomic_write_text(path, text)
            try:
                self._run(("load-buffer", "-b", buffer, str(path)))
                paste = ["paste-buffer", "-d", "-b", buffer, "-t", target]
                if bracketed:
                    paste.insert(1, "-p")
                self._run(tuple(paste))
            finally:
                path.unlink(missing_ok=True)
        if submit:
            self._run(("send-keys", "-t", target, "Enter"))

    def send_keys(self, name: str, keys: Sequence[str]) -> None:
        """Send validated named keys, such as Enter, Escape, C-c, or single characters."""
        validate_session_name(name)
        self._require_available()
        if not keys:
            raise ValueError("Choose at least one key to send")
        for key in keys:
            validate_key(key)
        self._run(("send-keys", "-t", f"={name}:", *keys))

    def kill(self, name: str) -> None:
        """Stop one session by exact name."""
        validate_session_name(name)
        self._require_available()
        self._run(("kill-session", "-t", f"={name}"))

    def global_environment(self, variable: str) -> str | None:
        """Return a variable from the tmux server's global environment when set."""
        _validate_environment_name(variable)
        if not self.server_running():
            return None
        result = self._run(("show-environment", "-g", variable), check=False)
        line = result.stdout.strip()
        prefix = f"{variable}="
        if result.returncode != 0 or not line.startswith(prefix):
            return None
        return line[len(prefix) :]

    def set_global_environment(self, variable: str, value: str) -> None:
        """Set a variable in the running tmux server's global environment."""
        _validate_environment_name(variable)
        if not self.server_running():
            raise TmuxUnavailableError("No tmux server is running")
        if value.endswith(";"):
            raise ValueError("Environment values cannot end with ';'")
        self._run(("set-environment", "-g", variable, value))

    def _require_available(self) -> None:
        if not self.available():
            raise TmuxUnavailableError("tmux is not installed or is not available on PATH")

    def _run(self, arguments: tuple[str, ...], *, check: bool = True) -> ProcessResult:
        return self.runner.run(("tmux", *arguments), check=check)


def validate_session_name(name: str) -> None:
    """Reject names outside the character set Alfred uses for sessions."""
    if not SESSION_NAME.fullmatch(name):
        raise ValueError(
            "Session name must start with an alphanumeric character and contain only "
            "letters, numbers, underscores, or hyphens"
        )


def validate_key(key: str) -> None:
    """Reject keys that are not a known tmux key name or a single safe character."""
    if key not in NAMED_KEYS and not SIMPLE_KEY.fullmatch(key):
        raise ValueError(f"Unsupported key {key!r}")


def _validate_environment_name(name: str) -> None:
    if not ENVIRONMENT_NAME.fullmatch(name):
        raise ValueError(f"Invalid environment variable name {name!r}")


def _format(fields: Sequence[str]) -> str:
    return SEPARATOR.join(f"#{{{field}}}" for field in fields)


def _parse_pane(line: str) -> PaneInfo | None:
    values = line.split(SEPARATOR)
    if len(values) < len(PANE_FIELDS):
        return None
    # The title is last so a stray separator inside it cannot shift other fields.
    fixed = values[: len(PANE_FIELDS) - 1]
    title = SEPARATOR.join(values[len(PANE_FIELDS) - 1 :])
    (
        session_name,
        window_index,
        pane_index,
        pane_active,
        window_active,
        pane_id,
        pid,
        current_command,
        dead,
        dead_status,
        width,
        height,
        cursor_x,
        cursor_y,
        history_size,
        in_mode,
        alternate_on,
        current_path,
    ) = fixed
    return PaneInfo(
        session_name=session_name,
        window_index=_int(window_index),
        pane_index=_int(pane_index),
        active=pane_active == "1" and window_active == "1",
        pane_id=pane_id,
        pid=_int(pid),
        current_command=current_command,
        dead=dead == "1",
        dead_status=_int(dead_status) if dead_status.strip() else None,
        width=_int(width),
        height=_int(height),
        cursor_x=_int(cursor_x),
        cursor_y=_int(cursor_y),
        history_size=_int(history_size),
        in_mode=in_mode == "1",
        alternate_screen=alternate_on == "1",
        current_path=current_path,
        title=title,
    )


def _int(value: str) -> int:
    try:
        return int(value.strip())
    except ValueError:
        return 0
