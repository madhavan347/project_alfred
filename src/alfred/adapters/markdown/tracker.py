"""Optional coordinated synchronization to three Markdown files."""

import re
from collections.abc import Callable
from pathlib import Path

from alfred.config.models import MarkdownTrackerConfig
from alfred.domain.models import Task, TaskEvent
from alfred.utils.files import atomic_write_text


TASK_HEADER = "| Task | Title | Status | Priority | Agent | Updated |\n|---:|---|---|---|---|---|"
AGENT_HEADER = "| Agent | Task | Status | Updated |\n|---|---:|---|---|"


class DisabledTracker:
    """No-op tracker used when Markdown synchronization is not configured."""

    def sync(self, task: Task, event: TaskEvent) -> tuple[Path, ...]:
        """Intentionally update no external files."""
        return ()


class MarkdownTracker:
    """Synchronize tasks, agents, and daily notes with rollback on failure."""

    def __init__(
        self,
        config: MarkdownTrackerConfig,
        *,
        writer: Callable[[Path, str], None] = atomic_write_text,
    ) -> None:
        if not config.enabled:
            raise ValueError("MarkdownTracker requires enabled configuration")
        if None in (config.canonical, config.agents, config.daily_notes):
            raise ValueError("MarkdownTracker requires all three configured paths")
        self.canonical = _path(config.canonical)
        self.agents = _path(config.agents)
        self.daily_notes = _path(config.daily_notes)
        self.writer = writer

    def sync(self, task: Task, event: TaskEvent) -> tuple[Path, ...]:
        """Build all updates first, then write with best-effort rollback."""
        daily_file = self.daily_notes / f"{event.timestamp[:10]}.md"
        paths = (self.canonical, self.agents, daily_file)
        originals = {path: _read_or_default(path) for path in paths}
        updates = {
            self.canonical: _update_task_table(originals[self.canonical], task),
            self.agents: _update_agent_table(originals[self.agents], task),
            daily_file: _update_daily_note(originals[daily_file], task, event),
        }

        written: list[Path] = []
        try:
            for path in paths:
                self.writer(path, updates[path])
                written.append(path)
        except Exception:
            for path in reversed(written):
                self.writer(path, originals[path])
            raise
        return paths


def _path(value: Path | None) -> Path:
    if value is None:
        raise ValueError("Tracker path is missing")
    return value


def _read_or_default(path: Path) -> str:
    if path.is_file():
        return path.read_text(encoding="utf-8")
    if path.name.endswith(".md") and path.parent.name != "daily":
        return ""
    return f"# {path.stem}\n\n## Timeline\n"


def _update_task_table(content: str, task: Task) -> str:
    row = (
        f"| {task.task_number} | {_cell(task.title)} | {task.status!s} | "
        f"{_cell(task.priority)} | {_cell(task.assigned_agent_alias or '-')} | "
        f"{_cell(task.updated_at or '-')} |"
    )
    pattern = re.compile(rf"^\|\s*(?:\*\*)?{task.task_number}(?:\*\*)?\s*\|.*$", re.MULTILINE)
    return _upsert_table(content, TASK_HEADER, row, pattern)


def _update_agent_table(content: str, task: Task) -> str:
    alias = task.assigned_agent_alias or "unassigned"
    row = (
        f"| {_cell(alias)} | {task.task_number} | {task.status!s} | "
        f"{_cell(task.updated_at or '-')} |"
    )
    pattern = re.compile(rf"^\|\s*{re.escape(alias)}\s*\|.*$", re.MULTILINE)
    return _upsert_table(content, AGENT_HEADER, row, pattern)


def _upsert_table(content: str, header: str, row: str, pattern: re.Pattern[str]) -> str:
    if pattern.search(content):
        return pattern.sub(row, content, count=1).rstrip() + "\n"
    if not content.strip():
        return f"{header}\n{row}\n"
    return f"{content.rstrip()}\n{row}\n"


def _update_daily_note(content: str, task: Task, event: TaskEvent) -> str:
    entry = (
        f"- {event.timestamp} — Task {task.task_number} — "
        f"{_cell(event.details)} (`{event.actor}` / `{event.event_type}`)"
    )
    if "## EOD Summary" in content:
        prefix, suffix = content.split("## EOD Summary", maxsplit=1)
        return f"{prefix.rstrip()}\n{entry}\n\n## EOD Summary{suffix}"
    if "## Timeline" in content:
        return f"{content.rstrip()}\n{entry}\n"
    return f"{content.rstrip()}\n\n## Timeline\n{entry}\n"


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()
