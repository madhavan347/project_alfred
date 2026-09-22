"""Run orchestration workflow tests."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from alfred.adapters.completion import CompletionFileStore
from alfred.adapters.git.worktrees import WorktreeStatus
from alfred.adapters.markdown import DisabledTracker
from alfred.adapters.state import JsonStateStore
from alfred.application.dispatch import AgentDispatcher
from alfred.application.knowledge import KnowledgeService
from alfred.application.runs import RunService
from alfred.application.tasks import TaskService
from alfred.config.models import (
    AgentConfig,
    AlfredConfig,
    CommandConfig,
    RuntimeConfig,
    WorkspaceConfig,
)
from alfred.domain.constants import (
    CompletionStatus,
    ExecutionMode,
    PlanningState,
    RunStatus,
    TaskStatus,
)
from alfred.domain.models import Task
from alfred.utils.time import Clock


class FixedClock(Clock):
    def now(self) -> datetime:
        return datetime(2026, 8, 16, 10, 30, tzinfo=ZoneInfo("UTC"))


class RecordingSessions:
    def __init__(self, *, available: bool = True) -> None:
        self.is_available = available
        self.names: set[str] = set()
        self.prompts: list[tuple[str, Path]] = []

    def available(self) -> bool:
        return self.is_available

    def exists(self, name: str) -> bool:
        if not self.is_available:
            raise RuntimeError("session backend is unavailable")
        return name in self.names

    def create(self, name: str, workdir: Path, command: tuple[str, ...]) -> None:
        self.names.add(name)

    def send_prompt(self, name: str, prompt_file: Path) -> None:
        self.prompts.append((name, prompt_file))

    def stop(self, name: str) -> None:
        self.names.discard(name)

    def list(self, prefix: str = "") -> tuple[str, ...]:
        return tuple(sorted(name for name in self.names if name.startswith(prefix)))


class RecordingWorktrees:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.created = 0
        self.cleaned = 0
        self.changes = ""

    def create(self, task: Task, repositories=None) -> dict[str, Path]:
        self.created += 1
        return {"app": self.root / f"task-{task.task_number}/app"}

    def statuses(self, task_number: int) -> tuple[WorktreeStatus, ...]:
        return (
            WorktreeStatus(
                repository="app",
                path=self.root / f"task-{task_number}/app",
                branch="feature/example",
                changes=self.changes,
            ),
        )

    def cleanup(self, task_number: int, *, force: bool = False) -> tuple[Path, ...]:
        self.cleaned += 1
        return (self.root / f"task-{task_number}/app",)


class RunServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.clock = FixedClock(ZoneInfo("UTC"))
        self.store = JsonStateStore(self.root / "state")
        self.store.initialize()
        agent = AgentConfig(
            alias="builder",
            runtime_target="local",
            commands=CommandConfig(
                direct=("agent",),
                plan=("agent", "plan"),
                execution=("agent", "execute"),
            ),
        )
        self.config = AlfredConfig(
            config_path=self.root / ".alfred/config.toml",
            workspace=WorkspaceConfig(root=self.root),
            runtime=RuntimeConfig(
                state_directory=self.root / "state",
                temp_directory=self.root / "temp",
            ),
            agents={"builder": agent},
        )
        self.sessions = RecordingSessions()
        self.worktrees = RecordingWorktrees(self.root / "worktrees")
        self.tasks = TaskService(
            self.store,
            DisabledTracker(),
            self.clock,
            agent_aliases=("builder",),
        )
        self.service = RunService(
            self.tasks,
            self.store,
            self.worktrees,
            AgentDispatcher(self.config, self.sessions),
            self.sessions,
            CompletionFileStore(self.root / "temp"),
            KnowledgeService(self.root / "knowledge", self.clock),
            self.clock,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def add_task(self, *, planned: bool = False, number: int = 7) -> Task:
        task = Task(
            task_number=number,
            title="Example",
            description="Implement an example",
            assigned_agent_alias="builder",
            branch_name="feature/example",
            execution_mode=(ExecutionMode.PLAN_EXECUTION if planned else ExecutionMode.DIRECT),
        )
        return self.tasks.upsert(task)

    def test_direct_trigger_creates_worktree_and_running_run(self) -> None:
        self.add_task()
        run = self.service.trigger((7,))[0]
        self.assertEqual(run.phase, "execution")
        self.assertEqual(run.run_status, RunStatus.RUNNING)
        self.assertEqual(self.worktrees.created, 1)
        self.assertEqual(self.tasks.require(7).status, TaskStatus.RUNNING)

    def test_plan_trigger_waits_before_creating_worktrees(self) -> None:
        self.add_task(planned=True)
        run = self.service.trigger((7,))[0]
        self.assertEqual(run.phase, "plan")
        self.assertEqual(self.worktrees.created, 0)
        self.assertEqual(self.tasks.require(7).planning_state, PlanningState.STARTED)

    def test_continue_reuses_session_and_starts_execution(self) -> None:
        self.add_task(planned=True)
        plan_run = self.service.trigger((7,))[0]
        execution_run = self.service.continue_execution(7)
        self.assertEqual(execution_run.run_id, plan_run.run_id)
        self.assertEqual(execution_run.phase, "execution")
        self.assertEqual(self.worktrees.created, 1)
        self.assertEqual(len(self.sessions.names), 1)
        self.assertEqual(self.tasks.require(7).planning_state, PlanningState.COMPLETED)

    def test_continue_note_reaches_execution_prompt(self) -> None:
        self.add_task(planned=True)
        self.service.trigger((7,))
        self.service.continue_execution(7, "Approved; also cover the empty-key case")
        prompt_file = self.sessions.prompts[-1][1]
        self.assertIn("Approved; also cover the empty-key case", prompt_file.read_text())
        self.assertEqual(self.tasks.require(7).notes, "Approved; also cover the empty-key case")

    def test_undispatchable_task_is_rejected_before_creating_worktrees(self) -> None:
        self.add_task()
        strict = AlfredConfig(
            config_path=self.config.config_path,
            workspace=self.config.workspace,
            runtime=RuntimeConfig(
                state_directory=self.root / "state",
                temp_directory=self.root / "temp",
                tmux_unavailable_policy="error",
            ),
            agents=self.config.agents,
        )
        self.service.dispatcher = AgentDispatcher(strict, self.sessions)
        self.sessions.is_available = False
        with self.assertRaisesRegex(RuntimeError, "session backend is unavailable"):
            self.service.trigger((7,))
        self.sessions.is_available = True
        stored = self.store.tasks()
        stored[0]["assigned_agent_alias"] = "ghost"  # agent removed from config after assignment
        self.store.save_tasks(stored)
        with self.assertRaisesRegex(ValueError, "Unknown agent 'ghost'"):
            self.service.trigger((7,))
        self.assertEqual(self.worktrees.created, 0)
        self.assertEqual(self.service.list(7), ())

    def test_queue_fallback_persists_task_and_run(self) -> None:
        self.sessions.is_available = False
        self.add_task()
        run = self.service.trigger((7,))[0]
        self.assertEqual(run.run_status, RunStatus.QUEUED)
        self.assertEqual(self.store.queue(), [7])
        self.assertEqual(self.tasks.require(7).status, TaskStatus.QUEUED)

    def test_queued_run_can_stop_while_session_backend_is_unavailable(self) -> None:
        self.sessions.is_available = False
        self.add_task()
        self.service.trigger((7,))
        run = self.service.stop(7)
        self.assertEqual(run.run_status, RunStatus.STOPPED)
        self.assertEqual(self.store.queue(), [])
        self.assertEqual(self.tasks.require(7).status, TaskStatus.PENDING)

    def test_trigger_rejects_a_task_that_already_has_a_live_run(self) -> None:
        self.add_task()
        self.service.trigger((7,))
        prompts = len(self.sessions.prompts)
        with self.assertRaisesRegex(ValueError, "Task 7 already has an active run"):
            self.service.trigger((7,))
        self.assertEqual(len(self.service.list(7)), 1)
        self.assertEqual(self.worktrees.created, 1)
        self.assertEqual(len(self.sessions.prompts), prompts)

    def test_retrigger_supersedes_a_queued_run(self) -> None:
        self.sessions.is_available = False
        self.add_task()
        queued = self.service.trigger((7,))[0]
        self.sessions.is_available = True
        running = self.service.trigger((7,))[0]
        runs = {run.run_id: run for run in self.service.list(7)}
        self.assertEqual(runs[queued.run_id].run_status, RunStatus.STOPPED)
        self.assertEqual(runs[running.run_id].run_status, RunStatus.RUNNING)
        self.assertEqual(self.service.active(7), running)
        self.assertEqual(self.store.queue(), [])

    def test_retrigger_supersedes_a_queued_plan_run_in_the_plan_phase(self) -> None:
        self.sessions.is_available = False
        self.add_task(planned=True)
        queued = self.service.trigger((7,))[0]
        self.sessions.is_available = True
        running = self.service.trigger((7,))[0]
        self.assertEqual(running.phase, "plan")
        self.assertEqual(running.run_status, RunStatus.RUNNING)
        self.assertEqual(self.worktrees.created, 0)
        runs = {run.run_id: run for run in self.service.list(7)}
        self.assertEqual(runs[queued.run_id].run_status, RunStatus.STOPPED)
        self.assertEqual(self.tasks.require(7).planning_state, PlanningState.STARTED)

    def test_corrupt_run_state_is_rejected_before_dispatch_side_effects(self) -> None:
        self.add_task()
        self.store.path("runs").write_text('{"schema_version": 1, "runs": [', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            self.service.trigger((7,))
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            self.service.active(7)
        self.assertEqual(self.worktrees.created, 0)
        self.assertEqual(self.sessions.names, set())

    def test_parallel_limit_is_deterministic(self) -> None:
        self.add_task(number=7)
        self.add_task(number=8)
        runs = self.service.trigger((7, 8), parallel=1)
        self.assertEqual(tuple(run.task_number for run in runs), (7,))

    def test_complete_checks_actor_and_writes_report(self) -> None:
        self.add_task()
        self.service.trigger((7,))
        with self.assertRaisesRegex(PermissionError, "run updates require actor 'agent:builder'"):
            self.service.complete(7, "success", "Done", actor="manager")
        report = self.service.complete(7, "success", "Done", actor="agent:builder")
        self.assertEqual(report.status, CompletionStatus.SUCCESS)
        self.assertEqual(self.tasks.require(7).status, TaskStatus.IN_REVIEW)
        self.assertEqual(len(CompletionFileStore(self.root / "temp").pending()), 1)

    def test_stop_closes_session_and_resets_task(self) -> None:
        self.add_task()
        self.service.trigger((7,))
        run = self.service.stop(7, cleanup=True)
        self.assertEqual(run.run_status, RunStatus.STOPPED)
        self.assertEqual(self.tasks.require(7).status, TaskStatus.PENDING)
        self.assertEqual(self.sessions.names, set())
        self.assertEqual(self.worktrees.cleaned, 1)

    def test_stopping_an_orphaned_run_keeps_a_terminal_task_terminal(self) -> None:
        self.add_task()
        self.service.trigger((7,))
        stored = self.store.tasks()
        stored[0].update(status="Completed", lifecycle_phase="archived")  # e.g. legacy state
        self.store.save_tasks(stored)
        run = self.service.stop(7, "Close orphaned run")
        self.assertEqual(run.run_status, RunStatus.STOPPED)
        task = self.tasks.require(7)
        self.assertEqual((task.status, task.lifecycle_phase), (TaskStatus.COMPLETED, "archived"))
        self.assertEqual(self.tasks.events(7)[-1].event_type, "RUN_STOPPED")

    def test_unblocked_event_resumes_the_blocked_run(self) -> None:
        self.add_task()
        run = self.service.trigger((7,))[0]
        self.service.complete(7, "blocked", "Need a decision", actor="agent:builder")
        self.assertEqual(self.service.active(7).run_status, RunStatus.BLOCKED)
        task = self.service.record_event(7, "unblocked", "Decided", actor="agent:builder")
        self.assertEqual(task.status, TaskStatus.IN_PROGRESS)
        resumed = self.service.active(7)
        self.assertEqual(resumed.run_id, run.run_id)
        self.assertEqual(resumed.run_status, RunStatus.RUNNING)
        self.assertEqual(resumed.session_status, "active")

    def test_agent_events_are_actor_checked(self) -> None:
        self.add_task()
        self.service.trigger((7,))
        with self.assertRaises(PermissionError):
            self.service.record_event(7, "progress", actor="manager")
        task = self.service.record_event(
            7,
            "progress",
            "Halfway",
            actor="agent:builder",
        )
        self.assertEqual(task.status, TaskStatus.IN_PROGRESS)

    def test_stopped_task_can_be_reopened(self) -> None:
        self.add_task()
        first = self.service.trigger((7,))[0]
        self.service.stop(7)
        reopened = self.service.reopen(7)
        self.assertNotEqual(reopened.run_id, first.run_id)
        self.assertEqual(reopened.run_status, RunStatus.RUNNING)

    def test_dirty_cleanup_fails_before_stopping_the_session(self) -> None:
        self.add_task()
        run = self.service.trigger((7,))[0]
        self.worktrees.changes = "?? notes.txt"
        with self.assertRaisesRegex(ValueError, "uncommitted changes: app; commit them"):
            self.service.stop(7, cleanup=True)
        self.assertIn(run.session_name, self.sessions.names)
        self.assertEqual(self.worktrees.cleaned, 0)
        self.assertEqual(self.service.list(7)[-1].run_status, RunStatus.RUNNING)
        stopped = self.service.stop(7, cleanup=True, force=True)
        self.assertEqual(stopped.run_status, RunStatus.STOPPED)
        self.assertEqual(self.worktrees.cleaned, 1)

    def test_stopped_plan_task_reopens_in_execution_with_worktrees(self) -> None:
        self.add_task(planned=True)
        self.service.trigger((7,))
        self.service.continue_execution(7)
        self.service.stop(7)
        self.assertEqual(self.tasks.require(7).planning_state, PlanningState.PENDING)
        reopened = self.service.reopen(7)
        self.assertEqual(reopened.phase, "execution")
        self.assertEqual(self.worktrees.created, 2)
        self.assertEqual(self.tasks.require(7).planning_state, PlanningState.COMPLETED)

    def test_session_names_are_limited_to_the_configured_prefix(self) -> None:
        self.sessions.names.update({"alfred-task-7-builder", "unrelated-session"})
        self.assertEqual(self.service.session_names(), ("alfred-task-7-builder",))


if __name__ == "__main__":
    unittest.main()
