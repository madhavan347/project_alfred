"""Legacy runtime migration tests."""

import json
import tempfile
import unittest
from pathlib import Path

from alfred.adapters.state import JsonStateStore
from alfred.config.migration import MigrationError, migrate_legacy_runtime


class LegacyMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.legacy = self.root / "data/runtime"
        self.legacy.mkdir(parents=True)
        self.state = JsonStateStore(self.root / ".alfred/state")
        self.migrations = self.root / ".alfred/migrations"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_json(self, name: str, value: object) -> None:
        (self.legacy / name).write_text(json.dumps(value), encoding="utf-8")

    def test_migrates_wrapped_state_and_agent_commands(self) -> None:
        self.write_json("tasks.json", {"tasks": [{"task_number": 7}]})
        self.write_json("runs.json", {"runs": [{"run_id": "run-1"}]})
        self.write_json("queue.json", {"queued_tasks": [7]})
        self.write_json(
            "agent_map.json",
            {
                "builder": {
                    "runtime_target": "local",
                    "dispatch_templates": {
                        "direct": "local-cli",
                        "plan": "local-cli --plan",
                        "execution": "local-cli --execute",
                    },
                }
            },
        )

        result = migrate_legacy_runtime(
            self.legacy,
            self.state,
            self.migrations,
            timestamp="20260816T000000Z",
        )

        self.assertEqual(self.state.tasks(), [{"task_number": 7}])
        self.assertEqual(self.state.runs(), [{"run_id": "run-1"}])
        self.assertEqual(self.state.queue(), [7])
        self.assertTrue((result.backup_directory / "tasks.json").is_file())
        self.assertIn(
            'plan = ["local-cli", "--plan"]',
            result.agent_fragment.read_text(encoding="utf-8"),  # type: ignore[union-attr]
        )
        self.assertTrue((self.legacy / "tasks.json").is_file())

    def test_accepts_legacy_list_documents(self) -> None:
        self.write_json("tasks.json", [{"task_number": 9}])
        self.write_json("runs.json", [])
        self.write_json("queue.json", [9])
        result = migrate_legacy_runtime(self.legacy, self.state, self.migrations)
        self.assertEqual(result.tasks, 1)
        self.assertEqual(self.state.queue(), [9])

    def test_migration_is_idempotent_after_marker(self) -> None:
        self.write_json("tasks.json", [])
        first = migrate_legacy_runtime(self.legacy, self.state, self.migrations)
        second = migrate_legacy_runtime(self.legacy, self.state, self.migrations)
        self.assertEqual(second.backup_directory, first.backup_directory)
        self.assertTrue(second.already_migrated)

    def test_invalid_source_does_not_create_destination(self) -> None:
        (self.legacy / "tasks.json").write_text("broken", encoding="utf-8")
        with self.assertRaisesRegex(MigrationError, "invalid JSON"):
            migrate_legacy_runtime(self.legacy, self.state, self.migrations)
        self.assertFalse(self.state.directory.exists())
        self.assertTrue((self.legacy / "tasks.json").is_file())

    def test_nonempty_destination_is_not_overwritten(self) -> None:
        self.state.initialize()
        self.state.save_tasks([{"task_number": 10}])
        self.write_json("tasks.json", [{"task_number": 11}])
        with self.assertRaisesRegex(MigrationError, "not empty"):
            migrate_legacy_runtime(self.legacy, self.state, self.migrations)
        self.assertEqual(self.state.tasks(), [{"task_number": 10}])


if __name__ == "__main__":
    unittest.main()
