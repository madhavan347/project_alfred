"""Optional Markdown tracker behavior tests."""

from pathlib import Path
import tempfile
import unittest

from alfred.adapters.markdown import DisabledTracker, MarkdownTracker
from alfred.config.models import MarkdownTrackerConfig
from alfred.domain.constants import TaskStatus
from alfred.domain.models import Task, TaskEvent


class MarkdownTrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config = MarkdownTrackerConfig(
            enabled=True,
            canonical=self.root / "tasks.md",
            agents=self.root / "agents.md",
            daily_notes=self.root / "daily",
        )
        self.task = Task(
            task_number=7,
            title="Example | task",
            description="A task",
            status=TaskStatus.RUNNING,
            priority="P1",
            assigned_agent_alias="builder",
            branch_name="feature/example",
            updated_at="2026-08-16T10:00:00+00:00",
        )
        self.event = TaskEvent(
            "2026-08-16T10:00:00+00:00", "agent:builder", "PROGRESS", "Implemented"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_disabled_tracker_is_a_true_noop(self) -> None:
        self.assertEqual(DisabledTracker().sync(self.task, self.event), ())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_sync_creates_and_updates_all_targets(self) -> None:
        paths = MarkdownTracker(self.config).sync(self.task, self.event)
        self.assertEqual(len(paths), 3)
        self.assertIn("Example \\| task", (self.root / "tasks.md").read_text())
        self.assertIn("| builder | 7 | Running |", (self.root / "agents.md").read_text())
        self.assertIn("Task 7", (self.root / "daily/2026-08-16.md").read_text())

    def test_daily_event_is_inserted_before_eod_summary(self) -> None:
        daily = self.root / "daily/2026-08-16.md"
        daily.parent.mkdir()
        daily.write_text("# Day\n\n## Timeline\n\n## EOD Summary\nDone\n")
        MarkdownTracker(self.config).sync(self.task, self.event)
        content = daily.read_text()
        self.assertLess(content.index("Task 7"), content.index("## EOD Summary"))

    def test_failure_rolls_back_prior_writes(self) -> None:
        self.root.joinpath("tasks.md").write_text("original tasks\n")
        self.root.joinpath("agents.md").write_text("original agents\n")
        calls = 0

        def failing_writer(path: Path, content: str) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated failure")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

        with self.assertRaisesRegex(OSError, "simulated failure"):
            MarkdownTracker(self.config, writer=failing_writer).sync(self.task, self.event)
        self.assertEqual(self.root.joinpath("tasks.md").read_text(), "original tasks\n")
        self.assertEqual(self.root.joinpath("agents.md").read_text(), "original agents\n")


if __name__ == "__main__":
    unittest.main()
