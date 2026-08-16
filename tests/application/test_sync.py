"""Markdown synchronization validation tests."""

from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from alfred.adapters.markdown import DisabledTracker, MarkdownTracker
from alfred.adapters.state import JsonStateStore
from alfred.application.sync import SyncService
from alfred.application.tasks import TaskService
from alfred.config.models import MarkdownTrackerConfig
from alfred.domain.models import Task
from alfred.utils.time import Clock


class FixedClock(Clock):
    def now(self) -> datetime:
        return datetime(2026, 8, 16, 10, 30, tzinfo=ZoneInfo("UTC"))


class SyncServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config = MarkdownTrackerConfig(
            enabled=True,
            canonical=self.root / "tasks.md",
            agents=self.root / "agents.md",
            daily_notes=self.root / "daily",
        )
        self.store = JsonStateStore(self.root / "state")
        self.store.initialize()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_disabled_tracker_is_reported(self) -> None:
        tasks = TaskService(
            self.store,
            DisabledTracker(),
            FixedClock(ZoneInfo("UTC")),
        )
        service = SyncService(MarkdownTrackerConfig(), tasks)
        self.assertIn("disabled", service.validate()[0])

    def test_synced_task_has_no_drift_and_missing_row_is_detected(self) -> None:
        tasks = TaskService(
            self.store,
            MarkdownTracker(self.config),
            FixedClock(ZoneInfo("UTC")),
        )
        tasks.upsert(
            Task(
                7,
                "Example",
                "Details",
                assigned_agent_alias="builder",
                branch_name="feature/example",
            )
        )
        service = SyncService(self.config, tasks)
        self.assertEqual(service.validate(7), ())
        self.config.canonical.write_text("| Task |\n", encoding="utf-8")
        self.assertIn("Task 7 is missing", service.validate(7)[0])

    def test_apply_reconciles_current_task(self) -> None:
        tasks = TaskService(
            self.store,
            MarkdownTracker(self.config),
            FixedClock(ZoneInfo("UTC")),
        )
        tasks.upsert(Task(7, "Example", "Details", branch_name="feature/example"))
        paths = SyncService(self.config, tasks).apply(7)
        self.assertEqual(paths, (self.config.canonical, self.config.agents))
        self.assertEqual(tasks.events(7)[-1].event_type, "SYNC_APPLIED")


if __name__ == "__main__":
    unittest.main()
