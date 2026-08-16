"""Run orchestration workflow tests."""

from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from alfred.adapters.completion import CompletionFileStore
from alfred.adapters.git.worktrees import WorktreeStatus
from alfred.adapters.markdown import DisabledTracker
from alfred.adapters.state import JsonStateStore
from alfred.application.dispatch import AgentDispatcher
from alfred.application.knowledge import KnowledgeService
from alfred.application.runs import RunService
from alfred.application.tasks import TaskService
from alfred.config.models import AgentConfig, AlfredConfig, CommandConfig, RuntimeConfig, WorkspaceConfig
from alfred.domain.constants import CompletionStatus, ExecutionMode, PlanningState, RunStatus, TaskStatus
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

    def create(self, task: Task, repositories=None) -> dict[str, Path]:
        self.created += 1
        return {"app": self.root / f"task-{task.task_number}/app"}

    def statuses(self, task_number: int) -> tuple[WorktreeStatus, ...]:
        return (
            WorktreeStatus(
                repository="app",
                path=self.root / f"task-{task_number}/app",
                branch="feature/example",
                changes="",
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

    def test_queue_fallback_persists_task_and_run(self) -> None:
        self.sessions.is_available = False
        self.add_task()
        run = self.service.trigger((7,))[0]
        self.assertEqual(run.run_status, RunStatus.QUEUED)
        self.assertEqual(self.store.queue(), [7])
        self.assertEqual(self.tasks.require(7).status, TaskStatus.QUEUED)

    def test_parallel_limit_is_deterministic(self) -> None:
        self.add_task(number=7)
        self.add_task(number=8)
        runs = self.service.trigger((7, 8), parallel=1)
        self.assertEqual(tuple(run.task_number for run in runs), (7,))

    def test_complete_checks_actor_and_writes_report(self) -> None:
        self.add_task()
        self.service.trigger((7,))
        with self.assertRaisesRegex(PermissionError, "agent:builder"):
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


if __name__ == "__main__":
    unittest.main()
