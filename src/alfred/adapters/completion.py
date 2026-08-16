"""Atomic file handoff for task completion reports."""

import json
from pathlib import Path

from alfred.domain.models import CompletionReport
from alfred.utils.files import atomic_write_json


class CompletionFileStore:
    """Write pending reports and archive them after coordinator processing."""

    def __init__(self, directory: Path) -> None:
        self.pending_directory = directory / "completions" / "pending"
        self.processed_directory = directory / "completions" / "processed"

    def write(self, report: CompletionReport) -> Path:
        """Atomically replace the pending report for one task."""
        path = self.pending_directory / f"task-{report.task_number}.json"
        atomic_write_json(path, report.to_dict())
        return path

    def pending(self) -> tuple[Path, ...]:
        """Return pending reports in deterministic order."""
        if not self.pending_directory.is_dir():
            return ()
        return tuple(sorted(self.pending_directory.glob("task-*.json")))

    def read(self, path: Path) -> CompletionReport:
        """Read and normalize a pending completion report."""
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid completion report {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"Completion report must contain an object: {path}")
        return CompletionReport.from_dict(value)

    def mark_processed(self, path: Path) -> Path:
        """Move a processed report out of the pending queue."""
        self.processed_directory.mkdir(parents=True, exist_ok=True)
        destination = self.processed_directory / path.name
        path.replace(destination)
        return destination
