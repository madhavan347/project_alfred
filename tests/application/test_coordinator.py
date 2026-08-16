"""Coordinator completion and health-cycle tests."""

from pathlib import Path
from types import MappingProxyType
import tempfile
import unittest
from zoneinfo import ZoneInfo

from alfred.adapters.completion import CompletionFileStore
from alfred.adapters.state import JsonStateStore
from alfred.application.coordinator import Coordinator
from alfred.application.notifications import NotificationService
from alfred.config.models import AlfredConfig, KnowledgeConfig, RuntimeConfig, WorkspaceConfig
from alfred.domain.constants import CompletionStatus, RunStatus
from alfred.domain.models import AgentRun, CompletionReport
from alfred.utils.time import Clock


class FakeSessions:
    def __init__(self, names: tuple[str, ...] = ()) -> None:
        self.names = names

    def available(self) -> bool:
        return True

    def exists(self, name: str) -> bool:
        return name in self.names

    def create(self, name: str, workdir: Path, command: tuple[str, ...]) -> None:
        raise AssertionError("not used")

    def send_prompt(self, name: str, prompt_file: Path) -> None:
        raise AssertionError("not used")

    def stop(self, name: str) -> None:
        raise AssertionError("not used")

    def list(self, prefix: str = "") -> tuple[str, ...]:
        return tuple(name for name in self.names if name.startswith(prefix))


class CoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = JsonStateStore(self.root / "state")
        self.store.initialize()
        self.completions = CompletionFileStore(self.root / "tmp")
        self.notifications = NotificationService(self.store, Clock(ZoneInfo("UTC")))
        self.config = AlfredConfig(
            config_path=self.root / "config.toml",
            workspace=WorkspaceConfig(root=self.root),
            runtime=RuntimeConfig(
                state_directory=self.root / "state",
                temp_directory=self.root / "tmp",
                session_prefix="alfred-task",
            ),
            agents=MappingProxyType({}),
            knowledge=KnowledgeConfig(
                directory=self.root / "knowledge", required_completion_entries=1
            ),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def coordinator(self, sessions: FakeSessions | None = None) -> Coordinator:
        return Coordinator(
            self.config,
            self.store,
            self.completions,
            self.notifications,
            sessions or FakeSessions(),
        )

    def test_processes_completion_and_reports_validation_issues(self) -> None:
        self.completions.write(
            CompletionReport(
                task_number=7,
                agent="builder",
                status=CompletionStatus.SUCCESS,
                summary="Implemented",
                knowledge_entries=0,
            )
        )
        cycle = self.coordinator().process_once()
        pending = self.notifications.pending()
        self.assertEqual(cycle.processed, 1)
        self.assertEqual(len(self.completions.pending()), 0)
        self.assertIn("knowledge_entries", pending[0].details["validation_issues"][0])

    def test_quarantines_malformed_completion(self) -> None:
        self.completions.pending_directory.mkdir(parents=True)
        path = self.completions.pending_directory / "task-7.json"
        path.write_text("broken")
        cycle = self.coordinator().process_once()
        self.assertEqual(cycle.invalid, 1)
        self.assertTrue((self.completions.invalid_directory / path.name).is_file())

    def test_dead_session_notification_is_not_duplicated(self) -> None:
        run = AgentRun(
            run_id="run-1",
            task_number=7,
            agent_alias="builder",
            runtime_target="local",
            run_status=RunStatus.RUNNING,
            session_name="alfred-task-7-builder",
        )
        self.store.save_runs([run.to_dict()])
        first = self.coordinator().process_once()
        second = self.coordinator().process_once()
        self.assertEqual(first.dead_sessions, 1)
        self.assertEqual(second.dead_sessions, 0)
        self.assertEqual(len(self.notifications.pending()), 1)

    def test_live_session_does_not_notify(self) -> None:
        run = AgentRun(
            run_id="run-1",
            task_number=7,
            agent_alias="builder",
            runtime_target="local",
            run_status=RunStatus.RUNNING,
            session_name="alfred-task-7-builder",
        )
        self.store.save_runs([run.to_dict()])
        cycle = self.coordinator(FakeSessions((run.session_name,))).process_once()
        self.assertEqual(cycle.dead_sessions, 0)
        self.assertEqual(self.notifications.pending(), ())


if __name__ == "__main__":
    unittest.main()
