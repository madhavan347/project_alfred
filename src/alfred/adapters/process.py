"""Subprocess implementation of Alfred's process port."""

import subprocess
from pathlib import Path

from alfred.ports.process import ProcessResult


class ProcessError(RuntimeError):
    """Raised when a checked child process exits unsuccessfully."""

    def __init__(self, result: ProcessResult, cwd: Path | None) -> None:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        location = f" in {cwd}" if cwd else ""
        command = " ".join(result.arguments)
        super().__init__(
            f"Command failed{location} with status {result.returncode}: {command}: {detail}"
        )
        self.result = result
        self.cwd = cwd


class SubprocessRunner:
    """Execute argument arrays with captured UTF-8 text output."""

    def run(
        self,
        arguments: tuple[str, ...],
        *,
        cwd: Path | None = None,
        check: bool = True,
    ) -> ProcessResult:
        """Run a command without invoking a shell."""
        if not arguments:
            raise ValueError("Process arguments cannot be empty")
        completed = subprocess.run(
            arguments,
            cwd=cwd,
            capture_output=True,
            check=False,
            text=True,
        )
        result = ProcessResult(
            arguments=arguments,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if check and result.returncode != 0:
            raise ProcessError(result, cwd)
        return result
