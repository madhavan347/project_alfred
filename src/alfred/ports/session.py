"""Interactive session backend interface."""

from pathlib import Path
from typing import Protocol


class SessionBackend(Protocol):
    """Manage named interactive command sessions."""

    def available(self) -> bool:
        """Return whether the backend executable is available."""
        ...

    def exists(self, name: str) -> bool:
        """Return whether a named session exists."""
        ...

    def create(self, name: str, workdir: Path, command: tuple[str, ...]) -> None:
        """Create a detached named session."""
        ...

    def send_prompt(self, name: str, prompt_file: Path) -> None:
        """Paste a prompt file and submit it to a session."""
        ...

    def stop(self, name: str) -> None:
        """Stop a named session."""
        ...

    def list(self, prefix: str = "") -> tuple[str, ...]:
        """Return matching session names."""
        ...
