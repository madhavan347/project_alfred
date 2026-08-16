"""Configuration-driven prompt construction and interactive dispatch."""

import shlex
from dataclasses import dataclass
from pathlib import Path

from alfred.config.models import AgentConfig, AlfredConfig
from alfred.domain.constants import PromptPhase
from alfred.domain.models import Task
from alfred.ports.session import SessionBackend
from alfred.utils.files import atomic_write_text


@dataclass(frozen=True, slots=True)
class DispatchOutcome:
    """Observable result of one task dispatch attempt."""

    session_name: str
    prompt_file: Path
    command_preview: str
    started: bool
    reused: bool
    queued: bool


class PromptBuilder:
    """Build a vendor-neutral task prompt from typed details."""

    def __init__(self, config: AlfredConfig) -> None:
        self.config = config

    def build(
        self,
        task: Task,
        phase: PromptPhase,
        worktree_paths: dict[str, Path],
    ) -> str:
        """Render task, phase, paths, and lifecycle commands."""
        repository_lines = [
            f"- {name}: {path}" for name, path in sorted(worktree_paths.items())
        ] or [f"- workspace: {self.config.workspace.root}"]
        instruction = (
            "Produce an implementation plan only and wait for approval."
            if phase == PromptPhase.PLAN
            else "Implement the approved plan, validate it, and report completion."
        )
        lines = [
            f"# Task {task.task_number}: {task.title}",
            "",
            f"Agent: {task.assigned_agent_alias or 'unassigned'}",
            f"Branch: {task.branch_name or '-'}",
            f"Mode: {task.execution_mode!s}",
            "",
            "## Description",
            "",
            task.description or "(no description)",
            "",
            f"## Phase: {phase.value.upper()}",
            "",
            instruction,
            "",
            "## Working directories",
            "",
            *repository_lines,
            "",
            "## Alfred lifecycle commands",
            "",
            f"- Progress: alfred task progress --task {task.task_number} --note <message>",
            f"- Complete: alfred run complete --task {task.task_number} --result success",
            "",
        ]
        return "\n".join(lines)


class PromptStore:
    """Persist prompt files under Alfred's configured private temp directory."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def write(self, task_number: int, phase: PromptPhase, content: str) -> Path:
        """Atomically replace a task-phase prompt file."""
        path = self.directory / "prompts" / f"task-{task_number}-{phase.value}.md"
        atomic_write_text(path, content)
        return path


class AgentDispatcher:
    """Dispatch task prompts to configured agents through a session backend."""

    def __init__(
        self,
        config: AlfredConfig,
        sessions: SessionBackend,
        prompts: PromptStore | None = None,
    ) -> None:
        self.config = config
        self.sessions = sessions
        self.builder = PromptBuilder(config)
        self.prompts = prompts or PromptStore(config.runtime.temp_directory)

    def dispatch(
        self,
        task: Task,
        phase: PromptPhase,
        worktree_paths: dict[str, Path],
    ) -> DispatchOutcome:
        """Start or reuse a task session, or queue when configured to do so."""
        agent = self._agent(task.assigned_agent_alias)
        workdir = next(iter(worktree_paths.values()), self.config.workspace.root)
        command = _render_command(agent, task, phase, workdir)
        prompt_file = self.prompts.write(
            task.task_number,
            phase,
            self.builder.build(task, phase, worktree_paths),
        )
        session_name = f"{self.config.runtime.session_prefix}-{task.task_number}-{agent.alias}"
        preview = shlex.join(command)
        if not self.sessions.available():
            if self.config.runtime.tmux_unavailable_policy == "queue":
                return DispatchOutcome(session_name, prompt_file, preview, False, False, True)
            raise RuntimeError("The configured session backend is unavailable")

        reused = self.sessions.exists(session_name)
        if not reused:
            self.sessions.create(session_name, workdir, command)
        self.sessions.send_prompt(session_name, prompt_file)
        return DispatchOutcome(session_name, prompt_file, preview, True, reused, False)

    def _agent(self, alias: str) -> AgentConfig:
        if not alias:
            raise ValueError("Task must be assigned to an agent before dispatch")
        agent = self.config.agents.get(alias)
        if agent is None:
            available = ", ".join(sorted(self.config.agents)) or "none"
            raise ValueError(f"Unknown agent {alias!r}; configured agents: {available}")
        return agent


def _render_command(
    agent: AgentConfig,
    task: Task,
    phase: PromptPhase,
    workdir: Path,
) -> tuple[str, ...]:
    template = agent.commands.plan if phase == PromptPhase.PLAN else agent.commands.execution
    values = {
        "task_number": str(task.task_number),
        "task_title": task.title,
        "task_branch": task.branch_name,
        "phase": phase.value,
        "workdir": str(workdir),
    }
    try:
        return tuple(argument.format_map(values) for argument in template)
    except KeyError as exc:
        raise ValueError(
            f"Agent {agent.alias!r} command uses unknown placeholder: {exc.args[0]}"
        ) from exc
