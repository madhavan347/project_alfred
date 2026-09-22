"""Task and assignment workflow tests."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from alfred.adapters.markdown import DisabledTracker
from alfred.adapters.state import JsonStateStore
from alfred.application.tasks import TaskService
from alfred.domain.constants import DispatchMode, LifecyclePhase, TaskStatus
from alfred.domain.models import Task
from alfred.utils.time import Clock


class FixedClock(Clock):
    def now(self) -> datetime:
        return datetime(2026, 8, 16, 10, 30, tzinfo=ZoneInfo("UTC"))


class FailingTracker:
    def sync(self, task, event):
        raise OSError("tracker failed")


class TaskServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = JsonStateStore(Path(self.temporary.name) / "state")
        self.store.initialize()
        self.service = TaskService(
            self.store,
            DisabledTracker(),
            FixedClock(ZoneInfo("UTC")),
            agent_aliases=("builder", "reviewer"),
            repository_names=("api", "web"),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def task(self, number: int = 7) -> Task:
        return Task(
            task_number=number,
            title="Example",
            description="Implement an example",
            branch_name="feature/example",
        )

    def test_upsert_preserves_created_timestamp(self) -> None:
        first = self.service.upsert(self.task())
        replacement = self.task()
        replacement.title = "Updated"
        second = self.service.upsert(replacement)
        self.assertEqual(second.created_at, first.created_at)
        self.assertEqual(self.service.require(7).title, "Updated")
        self.assertEqual(len(self.service.events(7)), 2)

    def test_queued_task_and_agent_assignment(self) -> None:
        task = self.task()
        task.dispatch_mode = DispatchMode.QUEUED
        self.service.upsert(task)
        assigned = self.service.assign(7, "builder")
        self.assertEqual(assigned.status, TaskStatus.QUEUED)
        self.assertEqual(assigned.assigned_agent_alias, "builder")

    def test_reassignment_and_update_keep_started_and_terminal_status(self) -> None:
        for status in (TaskStatus.RUNNING, TaskStatus.CONSOLIDATED):
            with self.subTest(status=status):
                task = self.task()
                task.dispatch_mode = DispatchMode.QUEUED
                task.status = status
                self.service.upsert(task)
                assigned = self.service.assign(7, "builder")
                self.assertEqual(assigned.status, status)
                updated = self.service.require(7)
                updated.title = "Renamed"
                self.assertEqual(self.service.upsert(updated).status, status)

    def test_upsert_rejects_unconfigured_agent_and_repository(self) -> None:
        task = self.task()
        task.assigned_agent_alias = "ghost"
        with self.assertRaisesRegex(ValueError, "Unknown agent 'ghost'; configured agents"):
            self.service.upsert(task)
        task = self.task()
        task.target_repositories = ["api", "nope"]
        with self.assertRaisesRegex(ValueError, "Unknown repository 'nope'; configured"):
            self.service.upsert(task)
        self.assertIsNone(self.service.get(7))

    def test_upsert_keeps_previously_stored_values_editable(self) -> None:
        self.service.upsert(self.task())
        stored = self.store.tasks()
        stored[0]["assigned_agent_alias"] = "retired"
        stored[0]["target_repositories"] = ["archived"]
        self.store.save_tasks(stored)
        task = self.service.require(7)
        task.title = "Renamed"
        self.assertEqual(self.service.upsert(task).title, "Renamed")

    def test_progress_block_unblock_and_review(self) -> None:
        self.service.upsert(self.task())
        self.service.progress(7, "Started", actor="agent:builder")
        self.service.block(7, "Waiting")
        self.service.unblock(7)
        self.service.progress(7, "Resumed")
        reviewed = self.service.review(7, "approved", "Looks good")
        self.assertEqual(reviewed.status, TaskStatus.IN_REVIEW)

    def test_lifecycle_archive_sets_completed_status(self) -> None:
        self.service.upsert(self.task())
        self.service.update_phase(7, LifecyclePhase.TESTING_DEPLOYMENT)
        archived = self.service.update_phase(7, LifecyclePhase.ARCHIVED)
        self.assertEqual(archived.status, TaskStatus.COMPLETED)

    def test_merge_requires_an_approved_review(self) -> None:
        self.service.upsert(self.task())
        with self.assertRaisesRegex(ValueError, "must be approved .MR in Review. before merge"):
            self.service.merge(7, "42")
        task = self.service.require(7)
        self.assertEqual((task.status, task.lifecycle_phase), (TaskStatus.PENDING, "active"))
        self.service.progress(7, "Started")
        self.service.review(7, "approved", "Looks good")
        merged = self.service.merge(7, "42")
        self.assertEqual(merged.status, TaskStatus.IN_REVIEW)
        self.assertEqual(merged.lifecycle_phase, LifecyclePhase.TESTING_DEPLOYMENT)
        self.assertIn("MERGED", [event.event_type for event in self.service.events(7)])

    def test_deploy_requires_merge_and_completed_task_cannot_be_merged_again(self) -> None:
        self.service.upsert(self.task())
        self.service.progress(7, "Started")
        self.service.review(7, "approved", "Looks good")
        with self.assertRaisesRegex(ValueError, "must be merged .* before deploy"):
            self.service.deploy(7, "sandbox", "passed")
        self.assertEqual(self.service.require(7).status, TaskStatus.IN_REVIEW)
        self.service.merge(7)
        deployed = self.service.deploy(7, "sandbox", "passed")
        self.assertEqual(deployed.status, TaskStatus.COMPLETED)
        with self.assertRaisesRegex(ValueError, "before merge"):
            self.service.merge(7)
        self.assertEqual(self.service.require(7).status, TaskStatus.COMPLETED)

    def test_tracker_failure_rolls_back_task_and_event(self) -> None:
        failing = TaskService(
            self.store,
            FailingTracker(),
            FixedClock(ZoneInfo("UTC")),
        )
        with self.assertRaisesRegex(OSError, "tracker failed"):
            failing.upsert(self.task())
        self.assertEqual(self.store.tasks(), [])
        self.assertEqual(self.store.events(), [])

    def test_unknown_agent_is_rejected(self) -> None:
        self.service.upsert(self.task())
        with self.assertRaisesRegex(ValueError, "configured agents"):
            self.service.assign(7, "missing")


if __name__ == "__main__":
    unittest.main()
