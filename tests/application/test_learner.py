"""Configurable learner session tests."""

from pathlib import Path
from types import MappingProxyType
import tempfile
import unittest

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
        return (LearnerService.SESSION_NAME,) if self.running else ()


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
            runtime=RuntimeConfig(
                state_directory=root / "state", temp_directory=root / "tmp"
            ),
            agents=MappingProxyType({"learner": agent}),
            knowledge=KnowledgeConfig(directory=root / "knowledge"),
        )
        self.sessions = FakeSessions()
        self.service = LearnerService(self.config, self.sessions)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_start_status_and_stop(self) -> None:
        self.assertTrue(self.service.start("learner"))
        self.assertFalse(self.service.start("learner"))
        self.assertTrue(self.service.status().running)
        self.assertIn("Knowledge directory", self.sessions.prompt_file.read_text())  # type: ignore[union-attr]
        self.assertTrue(self.service.stop())
        self.assertFalse(self.service.status().running)

    def test_unknown_agent_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "configured agents: learner"):
            self.service.start("missing")


if __name__ == "__main__":
    unittest.main()
