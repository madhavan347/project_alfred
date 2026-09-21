"""Legacy runtime migration tests."""

import json
import tempfile
import unittest
from pathlib import Path

from alfred.adapters.state import JsonStateStore
from alfred.config.migration import MigrationError, migrate_legacy_runtime
from alfred.domain.models import AgentRun, Task

LEGACY_TASK = {
    "task_number": 7,
    "title": "Legacy task",
    "description": "Imported from the legacy runtime",
    "status": "In Progress",
    "repos": ["api"],
    "branch_name": "legacy/task-7",
    "created_at_ist": "2025-01-02T10:00:00+05:30",
}
LEGACY_RUN = {
    "run_id": "run-1",
    "task_number": 7,
    "agent_alias": "builder",
    "runtime_target": "local",
    "run_status": "running",
    "started_at_ist": "2025-01-02T10:05:00+05:30",
}


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
        self.write_json("tasks.json", {"tasks": [LEGACY_TASK]})
        self.write_json("runs.json", {"runs": [LEGACY_RUN]})
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

        task = Task.from_dict(self.state.tasks()[0])
        run = AgentRun.from_dict(self.state.runs()[0])
        self.assertEqual(task.target_repositories, ["api"])
        self.assertEqual(task.created_at, "2025-01-02T10:00:00+05:30")
        self.assertNotIn("repos", self.state.tasks()[0])
        self.assertEqual(run.started_at, "2025-01-02T10:05:00+05:30")
        self.assertEqual(self.state.queue(), [7])
        self.assertTrue((result.backup_directory / "tasks.json").is_file())
        self.assertIn(
            'plan = ["local-cli", "--plan"]',
            result.agent_fragment.read_text(encoding="utf-8"),  # type: ignore[union-attr]
        )
        self.assertTrue((self.legacy / "tasks.json").is_file())

    def test_accepts_legacy_list_documents(self) -> None:
        self.write_json("tasks.json", [dict(LEGACY_TASK, task_number=9)])
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

    def test_unloadable_records_are_rejected_before_writing(self) -> None:
        self.write_json("tasks.json", [LEGACY_TASK])
        incomplete = {key: value for key, value in LEGACY_RUN.items() if key != "runtime_target"}
        self.write_json("runs.json", [LEGACY_RUN, incomplete])
        with self.assertRaisesRegex(MigrationError, "Legacy run at index 1 cannot be migrated"):
            migrate_legacy_runtime(self.legacy, self.state, self.migrations)
        self.assertFalse(self.state.directory.exists())
        self.assertFalse(self.migrations.exists())

    def test_nonempty_destination_is_not_overwritten(self) -> None:
        self.state.initialize()
        self.state.save_tasks([{"task_number": 10}])
        self.write_json("tasks.json", [dict(LEGACY_TASK, task_number=11)])
        with self.assertRaisesRegex(MigrationError, "not empty"):
            migrate_legacy_runtime(self.legacy, self.state, self.migrations)
        self.assertEqual(self.state.tasks(), [{"task_number": 10}])


if __name__ == "__main__":
    unittest.main()
