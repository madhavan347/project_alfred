"""Prompt and agent dispatch workflow tests."""

from pathlib import Path
from types import MappingProxyType
import tempfile
import unittest

from alfred.application.dispatch import AgentDispatcher, PromptBuilder
from alfred.config.models import (
    AgentConfig,
    AlfredConfig,
    CommandConfig,
    RuntimeConfig,
    WorkspaceConfig,
)
from alfred.domain.constants import PromptPhase
from alfred.domain.models import Task


class RecordingSessions:
    def __init__(self, *, available: bool = True, existing: bool = False) -> None:
        self.is_available = available
        self.existing = existing
        self.created: list[tuple[str, Path, tuple[str, ...]]] = []
        self.prompts: list[tuple[str, Path]] = []

    def available(self) -> bool:
        return self.is_available

    def exists(self, name: str) -> bool:
        return self.existing

    def create(self, name: str, workdir: Path, command: tuple[str, ...]) -> None:
        self.created.append((name, workdir, command))

    def send_prompt(self, name: str, prompt_file: Path) -> None:
        self.prompts.append((name, prompt_file))

    def stop(self, name: str) -> None:
        return None

    def list(self, prefix: str = "") -> tuple[str, ...]:
        return ()


class AgentDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        agent = AgentConfig(
            alias="builder",
            runtime_target="local",
            commands=CommandConfig(
                direct=("agent-cli",),
                plan=("agent-cli", "--phase", "{phase}"),
                execution=("agent-cli", "--workdir", "{workdir}"),
            ),
        )
        self.config = AlfredConfig(
            config_path=self.root / ".alfred/config.toml",
            workspace=WorkspaceConfig(root=self.root),
            runtime=RuntimeConfig(
                temp_directory=self.root / ".alfred/tmp",
                state_directory=self.root / ".alfred/state",
            ),
            agents=MappingProxyType({"builder": agent}),
        )
        self.task = Task(
            task_number=7,
            title="Example",
            description="Implement an example",
            assigned_agent_alias="builder",
            branch_name="feature/example",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_builder_contains_generic_task_context(self) -> None:
        prompt = PromptBuilder(self.config).build(self.task, PromptPhase.PLAN, {})
        self.assertIn("# Task 7: Example", prompt)
        self.assertIn("Produce an implementation plan only", prompt)
        self.assertIn(str(self.root), prompt)

    def test_dispatch_starts_session_with_rendered_arguments(self) -> None:
        sessions = RecordingSessions()
        outcome = AgentDispatcher(self.config, sessions).dispatch(
            self.task,
            PromptPhase.EXECUTION,
            {"api": self.root / "worktrees/api"},
        )
        self.assertTrue(outcome.started)
        self.assertFalse(outcome.reused)
        self.assertEqual(sessions.created[0][2][-1], str(self.root / "worktrees/api"))
        self.assertTrue(outcome.prompt_file.is_file())

    def test_existing_session_is_reused_for_next_phase(self) -> None:
        sessions = RecordingSessions(existing=True)
        outcome = AgentDispatcher(self.config, sessions).dispatch(
            self.task, PromptPhase.EXECUTION, {}
        )
        self.assertTrue(outcome.reused)
        self.assertEqual(sessions.created, [])
        self.assertEqual(len(sessions.prompts), 1)

    def test_unavailable_backend_queues_without_creating_session(self) -> None:
        sessions = RecordingSessions(available=False)
        outcome = AgentDispatcher(self.config, sessions).dispatch(
            self.task, PromptPhase.PLAN, {}
        )
        self.assertTrue(outcome.queued)
        self.assertFalse(outcome.started)
        self.assertEqual(sessions.created, [])

    def test_unknown_placeholder_is_actionable(self) -> None:
        agent = self.config.agents["builder"]
        invalid = AgentConfig(
            alias=agent.alias,
            runtime_target=agent.runtime_target,
            commands=CommandConfig(
                direct=agent.commands.direct,
                plan=("agent-cli", "{missing}"),
                execution=agent.commands.execution,
            ),
        )
        config = AlfredConfig(
            config_path=self.config.config_path,
            workspace=self.config.workspace,
            runtime=self.config.runtime,
            agents=MappingProxyType({"builder": invalid}),
        )
        with self.assertRaisesRegex(ValueError, "unknown placeholder: missing"):
            AgentDispatcher(config, RecordingSessions()).dispatch(
                self.task, PromptPhase.PLAN, {}
            )


if __name__ == "__main__":
    unittest.main()
