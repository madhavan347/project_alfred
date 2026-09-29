"""Session transcripts and agent-to-agent handoff notes kept in the private temp directory."""

from pathlib import Path

from alfred.utils.files import atomic_write_text

TRANSCRIPT_TAIL_LINES = 120


class TranscriptStore:
    """Persist captured session output per task for handoffs and the learner."""

    def __init__(self, temp_directory: Path) -> None:
        self.directory = temp_directory / "transcripts"

    def save(self, task_number: int, stamp: str, reason: str, session: str, text: str) -> Path:
        """Write one captured transcript and return its path."""
        safe_stamp = "".join(char if char.isalnum() else "-" for char in stamp)
        path = self.directory / f"task-{task_number}" / f"{safe_stamp}-{reason}-{session}.txt"
        atomic_write_text(path, text)
        return path

    @staticmethod
    def tail(text: str, lines: int = TRANSCRIPT_TAIL_LINES) -> str:
        """Return the last ``lines`` lines of a transcript."""
        return "\n".join(text.rstrip().splitlines()[-lines:])


class HandoffStore:
    """Hold one pending handoff note per task until the next agent's prompt consumes it."""

    def __init__(self, temp_directory: Path) -> None:
        self.directory = temp_directory / "handoffs"

    def path(self, task_number: int) -> Path:
        """Return the handoff file path for a task."""
        return self.directory / f"task-{task_number}.md"

    def write(self, task_number: int, content: str) -> Path:
        """Atomically replace the pending handoff for a task."""
        path = self.path(task_number)
        atomic_write_text(path, content)
        return path

    def read(self, task_number: int) -> str:
        """Return the pending handoff, or an empty string when there is none."""
        path = self.path(task_number)
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def clear(self, task_number: int) -> None:
        """Discard the pending handoff once a new agent has received it."""
        self.path(task_number).unlink(missing_ok=True)
