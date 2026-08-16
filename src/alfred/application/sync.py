"""Optional Markdown tracker validation and explicit reconciliation."""

import re
from pathlib import Path

from alfred.application.tasks import TaskService
from alfred.config.models import MarkdownTrackerConfig


class SyncService:
    """Detect tracker drift without mutating files unless explicitly applied."""

    def __init__(self, config: MarkdownTrackerConfig, tasks: TaskService) -> None:
        self.config = config
        self.tasks = tasks

    def validate(self, task_number: int | None = None) -> tuple[str, ...]:
        """Return deterministic configuration, file, and task-row issues."""
        if not self.config.enabled:
            return ("Markdown tracker is disabled in .alfred/config.toml",)
        configured = {
            "canonical": self.config.canonical,
            "agents": self.config.agents,
            "daily_notes": self.config.daily_notes,
        }
        issues: list[str] = []
        for label, path in configured.items():
            if path is None:
                issues.append(f"Markdown tracker path is not configured: {label}")
            elif label == "daily_notes":
                if not path.is_dir():
                    issues.append(f"Markdown tracker directory is missing: {path}")
            elif not path.is_file():
                issues.append(f"Markdown tracker file is missing: {path}")
        if issues or self.config.canonical is None or self.config.agents is None:
            return tuple(issues)

        selected = (
            (self.tasks.require(task_number),) if task_number is not None else self.tasks.list()
        )
        canonical = _read(self.config.canonical)
        agents = _read(self.config.agents)
        for task in selected:
            if not _has_first_column(canonical, str(task.task_number)):
                issues.append(f"Task {task.task_number} is missing from the canonical tracker")
            alias = task.assigned_agent_alias or "unassigned"
            if not _has_first_column(agents, alias):
                issues.append(f"Agent row {alias!r} is missing for task {task.task_number}")
        return tuple(issues)

    def apply(self, task_number: int, *, actor: str = "manager") -> tuple[Path, ...]:
        """Re-emit a task event through the configured tracker transaction."""
        if not self.config.enabled:
            raise ValueError("Markdown tracker is disabled in .alfred/config.toml")
        task = self.tasks.require(task_number)
        self.tasks.record(
            task,
            "SYNC_APPLIED",
            "Tracker state explicitly reconciled.",
            actor=actor,
        )
        return tuple(
            path
            for path in (self.config.canonical, self.config.agents)
            if path is not None
        )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _has_first_column(content: str, value: str) -> bool:
    pattern = re.compile(rf"^\|\s*(?:\*\*)?{re.escape(value)}(?:\*\*)?\s*\|", re.MULTILINE)
    return bool(pattern.search(content))
