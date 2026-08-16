"""Tmux implementation of Alfred's interactive session port."""

import re
import shlex
import shutil
from collections.abc import Callable
from pathlib import Path

from alfred.ports.process import ProcessRunner


class SessionUnavailable(RuntimeError):
    """Raised when a tmux operation is requested without tmux installed."""


class TmuxSessionBackend:
    """Manage detached tmux sessions using structured process execution."""

    def __init__(
        self,
        runner: ProcessRunner,
        *,
        executable_finder: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self.runner = runner
        self.executable_finder = executable_finder

    def available(self) -> bool:
        """Return whether tmux can be located on PATH."""
        return self.executable_finder("tmux") is not None

    def exists(self, name: str) -> bool:
        """Check a validated tmux session name."""
        self._require_available()
        _validate_name(name)
        result = self.runner.run(
            ("tmux", "has-session", "-t", name),
            check=False,
        )
        return result.returncode == 0

    def create(self, name: str, workdir: Path, command: tuple[str, ...]) -> None:
        """Create a detached session running one safely quoted command."""
        self._require_available()
        _validate_name(name)
        if not command:
            raise ValueError("Session command cannot be empty")
        workdir.mkdir(parents=True, exist_ok=True)
        self.runner.run(
            (
                "tmux",
                "new-session",
                "-d",
                "-s",
                name,
                "-c",
                str(workdir),
                shlex.join(command),
            )
        )

    def send_prompt(self, name: str, prompt_file: Path) -> None:
        """Load a prompt into tmux's buffer, paste it, and press Enter."""
        self._require_available()
        _validate_name(name)
        if not prompt_file.is_file():
            raise ValueError(f"Prompt file does not exist: {prompt_file}")
        self.runner.run(("tmux", "load-buffer", str(prompt_file)))
        self.runner.run(("tmux", "paste-buffer", "-t", name))
        self.runner.run(("tmux", "send-keys", "-t", name, "Enter"))

    def stop(self, name: str) -> None:
        """Stop a validated named session."""
        self._require_available()
        _validate_name(name)
        self.runner.run(("tmux", "kill-session", "-t", name))

    def list(self, prefix: str = "") -> tuple[str, ...]:
        """List sessions, returning an empty tuple when no tmux server exists."""
        self._require_available()
        result = self.runner.run(
            ("tmux", "list-sessions", "-F", "#{session_name}"),
            check=False,
        )
        if result.returncode != 0:
            return ()
        names = tuple(line for line in result.stdout.splitlines() if line)
        return tuple(name for name in names if not prefix or name.startswith(prefix))

    def _require_available(self) -> None:
        if not self.available():
            raise SessionUnavailable("tmux is not installed or is not available on PATH")


def _validate_name(name: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        raise ValueError(
            "Session name must start with an alphanumeric character and contain only "
            "letters, numbers, underscores, or hyphens"
        )
