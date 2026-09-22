"""Configurable learner session tests."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

from alfred.application.learner import LearnerService
from alfred.config.models import (
    AgentConfig,
    AlfredConfig,
    CommandConfig,
    KnowledgeConfig,
    RuntimeConfig,
    WorkspaceConfig,
)


class FakeSessions:
    def __init__(self) -> None:
        self.running = False
        self.created: list[tuple[str, Path, tuple[str, ...]]] = []
        self.prompt_file: Path | None = None

    def available(self) -> bool:
        return True

    def exists(self, name: str) -> bool:
        return self.running

    def create(self, name: str, workdir: Path, command: tuple[str, ...]) -> None:
        self.running = True
        self.created.append((name, workdir, command))

    def send_prompt(self, name: str, prompt_file: Path) -> None:
        self.prompt_file = prompt_file

    def stop(self, name: str) -> None:
        self.running = False

    def list(self, prefix: str = "") -> tuple[str, ...]:
        return ("alfred-task-learner",) if self.running else ()


class NamedSessions:
    """One shared tmux server: sessions are tracked by name across workspaces."""

    def __init__(self) -> None:
        self.names: set[str] = set()

    def available(self) -> bool:
        return True

    def exists(self, name: str) -> bool:
        return name in self.names

    def create(self, name: str, workdir: Path, command: tuple[str, ...]) -> None:
        self.names.add(name)

    def send_prompt(self, name: str, prompt_file: Path) -> None:
        pass

    def stop(self, name: str) -> None:
        self.names.discard(name)

    def list(self, prefix: str = "") -> tuple[str, ...]:
        return tuple(sorted(name for name in self.names if name.startswith(prefix)))


class LearnerServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        agent = AgentConfig(
            alias="learner",
            runtime_target="local",
            commands=CommandConfig(
                direct=("agent-cli",),
                plan=("agent-cli", "--plan"),
                execution=("agent-cli", "--execute"),
            ),
        )
        self.config = AlfredConfig(
            config_path=root / "config.toml",
            workspace=WorkspaceConfig(root=root),
            runtime=RuntimeConfig(state_directory=root / "state", temp_directory=root / "tmp"),
            agents=MappingProxyType({"learner": agent}),
            knowledge=KnowledgeConfig(directory=root / "knowledge"),
        )
        self.sessions = FakeSessions()
        self.service = LearnerService(self.config, self.sessions)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_learner_session_is_scoped_to_the_workspace_prefix(self) -> None:
        shared = NamedSessions()
        other_config = replace(
            self.config,
            runtime=replace(self.config.runtime, session_prefix="other-ws"),
        )
        this = LearnerService(self.config, shared)
        other = LearnerService(other_config, shared)
        self.assertTrue(this.start("learner"))
        self.assertEqual(this.status().session_name, "alfred-task-learner")
        self.assertFalse(other.status().running)
        self.assertFalse(other.stop())
        self.assertTrue(this.status().running)
        self.assertTrue(other.start("learner"))
        self.assertEqual(shared.names, {"alfred-task-learner", "other-ws-learner"})

    def test_start_status_and_stop(self) -> None:
        self.assertTrue(self.service.start("learner"))
        self.assertFalse(self.service.start("learner"))
        self.assertTrue(self.service.status().running)
        prompt = self.sessions.prompt_file.read_text()  # type: ignore[union-attr]
        self.assertIn("Knowledge directory", prompt)
        self.assertIn("Never edit, merge, move, or delete existing entries", prompt)
        self.assertTrue(self.service.stop())
        self.assertFalse(self.service.status().running)

    def _learner_with_direct(self, *direct: str) -> LearnerService:
        agent = AgentConfig(
            alias="learner",
            runtime_target="local",
            commands=CommandConfig(direct=direct, plan=("agent-cli",), execution=("agent-cli",)),
        )
        config = AlfredConfig(
            config_path=self.config.config_path,
            workspace=self.config.workspace,
            runtime=self.config.runtime,
            agents=MappingProxyType({"learner": agent}),
            knowledge=self.config.knowledge,
        )
        return LearnerService(config, self.sessions)

    def test_prompt_placeholder_starts_learner_without_pasting(self) -> None:
        self.assertTrue(self._learner_with_direct("agent-cli", "{prompt}").start("learner"))
        command = self.sessions.created[0][2]
        self.assertIn("# Alfred Knowledge Learner", command[-1])
        self.assertIsNone(self.sessions.prompt_file)

    def test_direct_command_without_prompt_placeholder_stays_verbatim(self) -> None:
        self.assertTrue(self._learner_with_direct("agent-cli", "{literal}").start("learner"))
        self.assertEqual(self.sessions.created[0][2], ("agent-cli", "{literal}"))
        self.assertIsNotNone(self.sessions.prompt_file)

    def test_task_placeholders_are_rejected_beside_prompt(self) -> None:
        service = self._learner_with_direct("agent-cli", "{prompt}", "{task_number}")
        with self.assertRaisesRegex(ValueError, "only {prompt} and {prompt_file}: task_number"):
            service.start("learner")
        self.assertEqual(self.sessions.created, [])

    def test_unknown_agent_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "configured agents: learner"):
            self.service.start("missing")


if __name__ == "__main__":
    unittest.main()
