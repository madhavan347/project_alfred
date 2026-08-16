"""Markdown knowledge-store workflow."""

from pathlib import Path

from alfred.domain.constants import KnowledgeCategory
from alfred.domain.models import KnowledgeEntry
from alfred.utils.files import atomic_write_text
from alfred.utils.text import slugify
from alfred.utils.time import Clock


class KnowledgeService:
    """Write and discover concise categorized Markdown knowledge entries."""

    def __init__(self, directory: Path, clock: Clock) -> None:
        self.directory = directory
        self.clock = clock

    def add(
        self,
        task_number: int,
        category: str | KnowledgeCategory,
        title: str,
        content: str,
        *,
        agent: str = "",
        related_files: tuple[str, ...] = (),
        related_repositories: tuple[str, ...] = (),
    ) -> Path:
        """Validate and atomically write one knowledge entry."""
        normalized_category = KnowledgeCategory(category)
        if not title.strip():
            raise ValueError("Knowledge title is required")
        if not content.strip():
            raise ValueError("Knowledge content is required")
        timestamp = self.clock.timestamp()
        entry = KnowledgeEntry(
            task_number=task_number,
            category=normalized_category.value,
            title=title.strip(),
            content=content.strip(),
            created_at=timestamp,
            agent=agent.strip(),
            related_files=related_files,
            related_repositories=related_repositories,
        )
        category_directory = self.directory / normalized_category.value
        filename = f"{timestamp[:10]}-task-{task_number}-{slugify(entry.title)}.md"
        path = category_directory / filename
        if path.exists():
            raise FileExistsError(f"Knowledge entry already exists: {path}")
        atomic_write_text(path, _render_entry(entry))
        return path

    def list(self, category: str | KnowledgeCategory | None = None) -> tuple[Path, ...]:
        """List entries in one category or the complete knowledge store."""
        if category is not None:
            directories: tuple[Path, ...] = (self.directory / KnowledgeCategory(category).value,)
        else:
            directories = tuple(self.directory / item.value for item in KnowledgeCategory)
        entries: list[Path] = []
        for directory in directories:
            if directory.is_dir():
                entries.extend(directory.glob("*.md"))
        return tuple(sorted(entries))

    def count_for_task(self, task_number: int) -> int:
        """Count entries whose stable filename identifies a task."""
        pattern = f"*-task-{task_number}-*.md"
        return sum(
            1
            for category in KnowledgeCategory
            for _ in (self.directory / category.value).glob(pattern)
        )


def _render_entry(entry: KnowledgeEntry) -> str:
    lines = [
        f"# {entry.title}",
        "",
        f"- Task: {entry.task_number}",
        f"- Category: {entry.category}",
        f"- Created: {entry.created_at}",
    ]
    if entry.agent:
        lines.append(f"- Agent: {entry.agent}")
    lines.extend(["", "## Summary", "", entry.content])
    if entry.related_files or entry.related_repositories:
        lines.extend(["", "## Related"])
        if entry.related_files:
            lines.append(f"- Files: {', '.join(entry.related_files)}")
        if entry.related_repositories:
            lines.append(f"- Repositories: {', '.join(entry.related_repositories)}")
    return "\n".join(lines) + "\n"
