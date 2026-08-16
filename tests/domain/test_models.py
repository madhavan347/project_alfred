"""Domain model compatibility tests."""

import json
import unittest

from alfred.domain.constants import CompletionStatus, RunStatus, TaskStatus
from alfred.domain.models import AgentRun, CompletionReport, Task, TaskEvent


class DomainModelTests(unittest.TestCase):
    def test_task_loads_legacy_timestamp_fields(self) -> None:
        task = Task.from_dict(
            {
                "task_number": 7,
                "title": "Example",
                "description": "A task",
                "status": "Running",
                "created_at_ist": "old-created",
                "updated_at_ist": "old-updated",
            }
        )

        self.assertEqual(task.status, TaskStatus.RUNNING)
        self.assertEqual(task.created_at, "old-created")
        self.assertEqual(task.updated_at, "old-updated")
        self.assertNotIn("created_at_ist", task.to_dict())
        json.dumps(task.to_dict())

    def test_run_loads_legacy_defaults(self) -> None:
        run = AgentRun.from_dict(
            {
                "run_id": "run-1",
                "task_number": 7,
                "agent_alias": "builder",
                "runtime_target": "local",
                "run_status": "running",
                "started_at_ist": "old-start",
            }
        )
        self.assertEqual(run.run_status, RunStatus.RUNNING)
        self.assertEqual(run.started_at, "old-start")
        self.assertEqual(run.worktree_paths, {})

    def test_completion_normalizes_legacy_failure(self) -> None:
        report = CompletionReport.from_dict(
            {
                "task_number": 7,
                "agent": "builder",
                "status": "failure",
                "summary": "Tests failed",
                "repos_touched": ["api"],
                "knowledge_entries_written": 1,
            }
        )
        self.assertEqual(report.status, CompletionStatus.FAILED)
        self.assertEqual(report.repositories, ("api",))
        self.assertEqual(report.knowledge_entries, 1)

    def test_event_markdown_is_stable(self) -> None:
        event = TaskEvent("2026-08-16T10:00:00+00:00", "agent:builder", "PROGRESS", "Done")
        self.assertEqual(
            event.to_markdown(),
            "- **2026-08-16T10:00:00+00:00** | `agent:builder` | `PROGRESS` | Done",
        )


if __name__ == "__main__":
    unittest.main()
