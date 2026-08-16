"""Structured process execution interface."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ProcessResult:
    """Captured result of one argument-vector process invocation."""

    arguments: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class ProcessRunner(Protocol):
    """Run trusted argument vectors without shell interpolation."""

    def run(
        self,
        arguments: tuple[str, ...],
        *,
        cwd: Path | None = None,
        check: bool = True,
    ) -> ProcessResult:
        """Execute and optionally raise for a nonzero status."""
        ...
