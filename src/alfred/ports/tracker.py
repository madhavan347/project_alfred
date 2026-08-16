"""Tracker synchronization interface."""

from pathlib import Path
from typing import Protocol

from alfred.domain.models import Task, TaskEvent


class Tracker(Protocol):
    """Synchronize a task event to configured external tracker files."""

    def sync(self, task: Task, event: TaskEvent) -> tuple[Path, ...]:
        """Apply an event and return updated paths."""
        ...
