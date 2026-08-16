"""Versioned JSON state-store tests."""

import json
from pathlib import Path
import tempfile
import unittest

from alfred.adapters.state import JsonStateStore, StateError


class JsonStateStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name) / "state"
        self.store = JsonStateStore(self.directory)
        self.store.initialize()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_initialize_creates_versioned_documents(self) -> None:
        self.assertEqual(self.store.tasks(), [])
        self.assertEqual(self.store.runs(), [])
        self.assertEqual(self.store.queue(), [])
        self.assertEqual(self.store.read_document("notifications")["notifications"], [])

    def test_round_trip_normalizes_queue(self) -> None:
        self.store.save_tasks([{"task_number": 7, "title": "Example"}])
        self.store.save_queue([7, 2, 7])

        self.assertEqual(self.store.tasks()[0]["task_number"], 7)
        self.assertEqual(self.store.queue(), [2, 7])

    def test_initialize_does_not_overwrite_existing_state(self) -> None:
        self.store.save_tasks([{"task_number": 8}])
        self.store.initialize()
        self.assertEqual(self.store.tasks(), [{"task_number": 8}])

    def test_invalid_json_is_not_replaced(self) -> None:
        path = self.store.path("tasks")
        path.write_text("not-json", encoding="utf-8")
        with self.assertRaisesRegex(StateError, "invalid JSON"):
            self.store.tasks()
        self.assertEqual(path.read_text(encoding="utf-8"), "not-json")

    def test_writes_leave_no_temporary_files(self) -> None:
        self.store.save_runs([{"run_id": "run-1"}])
        payload = json.loads(self.store.path("runs").read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(list(self.directory.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
