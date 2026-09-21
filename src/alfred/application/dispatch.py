"""Configuration-driven prompt construction and interactive dispatch."""

import shlex
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from string import Formatter

from alfred.config.models import AgentConfig, AlfredConfig
from alfred.domain.constants import ExecutionMode, PromptPhase
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
        repository_lines = [f"- {name}: {path}" for name, path in sorted(worktree_paths.items())]
        if not repository_lines:
            label = "source, read-only until approval" if phase == PromptPhase.PLAN else "source"
            repository_lines = [f"- workspace: {self.config.workspace.root}"]
            repository_lines.extend(
                f"- {repository.name} ({label}): {repository.path}"
                for repository in self.config.workspace.repositories
                if repository.name in task.target_repositories
                or (not task.target_repositories and repository.selected_by_default)
            )
        if phase == PromptPhase.PLAN:
            instruction = "Produce an implementation plan only and wait for approval."
        elif task.execution_mode == ExecutionMode.PLAN_EXECUTION:
            instruction = "Implement the approved plan, validate it, and report completion."
        else:
            instruction = "Implement the task, validate it, and report completion."
        actor = f"agent:{task.assigned_agent_alias}"
        number = task.task_number
        lifecycle_commands: tuple[str, ...]
        if phase == PromptPhase.PLAN:
            lifecycle_commands = (
                f"- Plan ready: alfred run event --task {number} "
                f"--type plan_completed --note <summary> --actor {actor}",
            )
        else:
            lifecycle_commands = (
                f"- Progress: alfred task progress --task {number} "
                f"--note <message> --actor {actor}",
                f"- Blocked: alfred run event --task {number} --type blocked "
                f"--note <reason> --actor {actor}",
                f"- Knowledge (before completing): alfred knowledge add --task {number} "
                "--category <patterns|decisions|entities|issues|conventions> "
                f"--title <title> --content <learning> --agent {task.assigned_agent_alias}",
                f"- Complete: alfred run complete --task {number} --result success "
                f"--note <summary> --actor {actor}",
            )
        notes = ["## Latest notes", "", task.notes, ""] if task.notes.strip() else []
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
            *notes,
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
            *lifecycle_commands,
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
        prompt = self.builder.build(task, phase, worktree_paths)
        prompt_file = self.prompts.write(task.task_number, phase, prompt)
        command = _render_command(agent, task, phase, workdir, prompt, prompt_file)
        session_name = f"{self.config.runtime.session_prefix}-{task.task_number}-{agent.alias}"
        preview = shlex.join(_render_command(agent, task, phase, workdir, "<prompt>", prompt_file))
        if not self.sessions.available():
            if self.config.runtime.tmux_unavailable_policy == "queue":
                return DispatchOutcome(session_name, prompt_file, preview, False, False, True)
            raise RuntimeError("The configured session backend is unavailable")

        reused = self.sessions.exists(session_name)
        if not reused:
            self.sessions.create(session_name, workdir, command)
        if reused or not _delivers_prompt(_template(agent, phase)):
            self.sessions.send_prompt(session_name, prompt_file)
        return DispatchOutcome(session_name, prompt_file, preview, True, reused, False)

    def preflight(self, task: Task, phase: PromptPhase) -> None:
        """Reject a dispatch that cannot start before any worktree is created."""
        agent = self._agent(task.assigned_agent_alias)
        _render_command(agent, task, phase, self.config.workspace.root, "", Path())
        if self.config.runtime.tmux_unavailable_policy != "queue" and not self.sessions.available():
            raise RuntimeError("The configured session backend is unavailable")

    def _agent(self, alias: str) -> AgentConfig:
        if not alias:
            raise ValueError("Task must be assigned to an agent before dispatch")
        agent = self.config.agents.get(alias)
        if agent is None:
            available = ", ".join(sorted(self.config.agents)) or "none"
            raise ValueError(f"Unknown agent {alias!r}; configured agents: {available}")
        return agent


PROMPT_PLACEHOLDERS = frozenset({"prompt", "prompt_file"})


def _template(agent: AgentConfig, phase: PromptPhase) -> tuple[str, ...]:
    return agent.commands.plan if phase == PromptPhase.PLAN else agent.commands.execution


def _delivers_prompt(template: Sequence[str]) -> bool:
    """Return whether a command template passes the prompt to the agent at startup."""
    return any(
        field in PROMPT_PLACEHOLDERS
        for argument in template
        for _, field, _, _ in Formatter().parse(argument)
    )


def render_learner_command(
    template: Sequence[str],
    prompt: str,
    prompt_file: Path,
) -> tuple[tuple[str, ...], bool]:
    """Render a verbatim direct command, substituting prompt placeholders when present.

    Returns the command and whether it delivers the prompt itself. Templates without a
    prompt placeholder stay verbatim, so literal braces keep their previous meaning.
    """
    if not _delivers_prompt(template):
        return tuple(template), False
    values = {"prompt": prompt, "prompt_file": str(prompt_file)}
    try:
        return tuple(argument.format_map(values) for argument in template), True
    except KeyError as exc:
        raise ValueError(
            f"Learner command supports only {{prompt}} and {{prompt_file}}: {exc.args[0]}"
        ) from exc


def _render_command(
    agent: AgentConfig,
    task: Task,
    phase: PromptPhase,
    workdir: Path,
    prompt: str,
    prompt_file: Path,
) -> tuple[str, ...]:
    values = {
        "task_number": str(task.task_number),
        "task_title": task.title,
        "task_branch": task.branch_name,
        "phase": phase.value,
        "workdir": str(workdir),
        "prompt": prompt,
        "prompt_file": str(prompt_file),
    }
    try:
        return tuple(argument.format_map(values) for argument in _template(agent, phase))
    except KeyError as exc:
        raise ValueError(
            f"Agent {agent.alias!r} command uses unknown placeholder: {exc.args[0]}"
        ) from exc
