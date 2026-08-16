"""Persistent notification workflow tests."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from alfred.adapters.state import JsonStateStore
from alfred.application.notifications import NotificationService
from alfred.utils.time import Clock


class FixedClock(Clock):
    def now(self) -> datetime:
        return datetime(2026, 8, 16, 10, 30, tzinfo=ZoneInfo("UTC"))


class NotificationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = JsonStateStore(Path(self.temporary.name) / "state")
        self.store.initialize()
        self.service = NotificationService(self.store, FixedClock(ZoneInfo("UTC")))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_create_acknowledge_and_clear(self) -> None:
        created = self.service.create("review", 7, {"summary": "Ready"})
        self.assertEqual(self.service.pending(), (created,))
        self.assertEqual(self.service.acknowledge(7), 1)
        self.assertEqual(self.service.pending(), ())
        self.assertEqual(self.service.clear_acknowledged(), 1)
        self.assertEqual(self.store.notifications(), [])

    def test_acknowledge_only_matches_requested_task(self) -> None:
        self.service.create("review", 7, {})
        self.service.create("review", 8, {})
        self.assertEqual(self.service.acknowledge(7), 1)
        self.assertEqual([item.task_number for item in self.service.pending()], [8])


if __name__ == "__main__":
    unittest.main()
