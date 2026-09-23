"""Health checks for the conditions Alfred's workflows depend on in practice.

Most failures in real use are environmental: an agent session cannot find ``alfred`` or its CLI
on PATH, cannot discover the workspace configuration from its working directory, or tracker files
have drifted. Each check explains the problem and, where safe, offers a one-step fix.
"""

import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from alfred.adapters.process import SubprocessRunner
from alfred.adapters.state.json_store import DEFAULT_DOCUMENTS, JsonStateStore
from alfred.config.loader import ConfigError, discover_config
from alfred.config.models import AlfredConfig
from alfred.domain.constants import PromptPhase

from alfred_ui.agents import TASK_PLACEHOLDERS, delivers_prompt, placeholders
from alfred_ui.tmux_inspector import TmuxInspector
from alfred_ui.workspace import WorkspaceContext

INTERACTIVE_CLIS = frozenset(
    {"claude", "codex", "agy", "gemini", "cursor-agent", "opencode", "qwen"}
)
Check = dict[str, Any]
Add = Callable[..., None]


def run_checks(context: WorkspaceContext, inspector: TmuxInspector) -> list[Check]:
    """Return every check in display order."""
    checks: list[Check] = []

    def add(
        key: str,
        title: str,
        status: str,
        detail: str,
        fix: dict[str, str] | None = None,
    ) -> None:
        checks.append({"key": key, "title": title, "status": status, "detail": detail, "fix": fix})

    path = context.config_path
    if path is None:
        add(
            "workspace",
            "Workspace",
            "error",
            context.discovery_error or "No workspace is open.",
        )
        return checks
    try:
        config = context.config()
    except KeyError as exc:
        add("config", "Configuration", "error", str(exc.args[0] if exc.args else exc))
        return checks
    except (ValueError, OSError) as exc:
        add("config", "Configuration", "error", str(exc))
        return checks
    add("config", "Configuration", "ok", f"Loaded {path}")

    _state_checks(config, add)
    _git_checks(config, add)
    session_path = _tmux_checks(inspector, add)
    _agent_path_checks(config, inspector, session_path, add)
    _discovery_checks(config, inspector, path, add)
    _agent_command_checks(config, add)
    _tracker_checks(context, add)
    _knowledge_checks(config, add)
    return checks


def alfred_directory() -> Path | None:
    """Return the directory holding the ``alfred`` executable of this installation."""
    candidate = Path(sys.executable).parent / "alfred"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate.parent
    found = shutil.which("alfred")
    return Path(found).parent if found else None


def fix_tmux_path(inspector: TmuxInspector) -> str:
    """Append this installation's ``alfred`` directory to the tmux server's global PATH."""
    directory = alfred_directory()
    if directory is None:
        raise ValueError("Cannot find this installation's alfred executable")
    current = inspector.global_environment("PATH")
    if current is None:
        raise ValueError("No tmux server is running, so there is no global PATH to update yet")
    entries = [entry for entry in current.split(os.pathsep) if entry]
    if str(directory) in entries:
        return f"{directory} is already on the tmux PATH"
    inspector.set_global_environment("PATH", os.pathsep.join([*entries, str(directory)]))
    return f"Added {directory} to the tmux global PATH for new sessions"


def _state_checks(config: AlfredConfig, add: Add) -> None:
    store = JsonStateStore(config.runtime.state_directory)
    problems: list[str] = []
    missing: list[str] = []
    for name in DEFAULT_DOCUMENTS:
        if not store.path(name).exists():
            missing.append(name)
            continue
        try:
            store.read_document(name)
        except ValueError as exc:
            problems.append(str(exc))
    if problems:
        add("state", "State documents", "error", "; ".join(problems))
    elif missing:
        add(
            "state",
            "State documents",
            "info",
            f"Missing documents are created on first use: {', '.join(missing)}",
        )
    else:
        add("state", "State documents", "ok", f"All five documents are valid in {store.directory}")


def _git_checks(config: AlfredConfig, add: Add) -> None:
    git = shutil.which("git")
    if git is None:
        add("git", "Git", "error", "git is not on PATH; worktrees and commits will fail")
        return
    add("git", "Git", "ok", f"Using {git}")
    if not config.workspace.repositories:
        add(
            "repositories",
            "Repositories",
            "warn",
            "No repositories are configured. Add one in Settings before creating worktree tasks.",
        )
        return
    for repository in config.workspace.repositories:
        key = f"repository:{repository.name}"
        title = f"Repository {repository.name}"
        if not repository.path.is_dir() or not (repository.path / ".git").exists():
            add(key, title, "error", f"{repository.path} is missing or is not a Git repository")
            continue
        verify = _run(
            ("git", "rev-parse", "--verify", "--quiet", repository.default_branch), repository.path
        )
        remote = _run(("git", "remote", "get-url", repository.remote), repository.path)
        issues = []
        if verify[0] != 0:
            issues.append(f"default branch {repository.default_branch!r} does not exist")
        if remote[0] != 0:
            issues.append(f"remote {repository.remote!r} is not configured (push will fail)")
        if issues:
            add(key, title, "warn", f"{repository.path}: " + "; ".join(issues))
        else:
            add(
                key,
                title,
                "ok",
                f"{repository.path} on {repository.default_branch}, "
                f"remote {repository.remote} = {remote[1].strip()}",
            )


def _tmux_checks(inspector: TmuxInspector, add: Add) -> str:
    """Report tmux and return the PATH new agent sessions will receive."""
    if not inspector.available():
        add(
            "tmux",
            "tmux",
            "warn",
            "tmux is not on PATH. Dispatches follow tmux_unavailable_policy (queue or error), "
            "and live terminals are unavailable.",
        )
        return os.environ.get("PATH", "")
    version = inspector.version()
    if inspector.server_running():
        session_path = inspector.global_environment("PATH")
        add("tmux", "tmux", "ok", f"{version}; server running")
        return session_path if session_path is not None else os.environ.get("PATH", "")
    add(
        "tmux",
        "tmux",
        "ok",
        f"{version}; no server yet (the first dispatch starts one with this server's PATH)",
    )
    return os.environ.get("PATH", "")


def _agent_path_checks(
    config: AlfredConfig, inspector: TmuxInspector, session_path: str, add: Add
) -> None:
    found = shutil.which("alfred", path=session_path)
    directory = alfred_directory()
    fix = (
        {"action": "tmux-path", "label": "Add alfred to the tmux PATH"}
        if inspector.server_running() and directory is not None
        else None
    )
    if found is None:
        add(
            "alfred-path",
            "Agents can run alfred",
            "error",
            "Agent sessions cannot find the alfred command, so agents cannot report progress "
            "or completion. "
            + (f"This installation's alfred is in {directory}." if directory else ""),
            fix,
        )
    else:
        add("alfred-path", "Agents can run alfred", "ok", f"Agent sessions will run {found}")
    missing: list[str] = []
    for alias, agent in sorted(config.agents.items()):
        for phase, command in (
            ("direct", agent.commands.direct),
            ("plan", agent.commands.plan),
            ("execution", agent.commands.execution),
        ):
            executable = command[0]
            resolved = (
                executable
                if os.path.isabs(executable) and os.access(executable, os.X_OK)
                else shutil.which(executable, path=session_path)
            )
            if resolved is None:
                missing.append(f"{alias}.{phase}: {executable}")
    if missing:
        add(
            "agent-executables",
            "Agent commands are installed",
            "error",
            "Not found on the agent session PATH: " + "; ".join(missing),
        )
    elif config.agents:
        add(
            "agent-executables",
            "Agent commands are installed",
            "ok",
            "Every configured agent command resolves on the agent session PATH",
        )
    else:
        add(
            "agent-executables",
            "Agents",
            "warn",
            "No agents are configured. Add one in Settings before assigning tasks.",
        )


def _discovery_checks(
    config: AlfredConfig, inspector: TmuxInspector, config_path: Path, add: Add
) -> None:
    """Agents run ``alfred`` without --config, so discovery from their cwd must succeed."""
    configured = inspector.global_environment("ALFRED_CONFIG")
    environment = {"ALFRED_CONFIG": configured} if configured else {}
    starts = {
        "workspace root": config.workspace.root,
        "worktree directory": config.runtime.worktree_directory / "task-0" / "repository",
    }
    problems: list[str] = []
    for label, start in starts.items():
        try:
            found = discover_config(start, environment=environment)
        except ConfigError:
            problems.append(f"nothing found from the {label} ({start})")
            continue
        if found.resolve() != config_path.resolve():
            problems.append(f"the {label} resolves to {found}")
    if problems:
        add(
            "discovery",
            "Agents find this workspace",
            "error",
            "Commands an agent runs would not use this configuration: "
            + "; ".join(problems)
            + ". Keep worktrees under the workspace root or set ALFRED_CONFIG for tmux.",
        )
    else:
        add(
            "discovery",
            "Agents find this workspace",
            "ok",
            "alfred commands run from agent working directories use this configuration",
        )


def _agent_command_checks(config: AlfredConfig, add: Add) -> None:
    for alias, agent in sorted(config.agents.items()):
        key = f"agent:{alias}"
        title = f"Agent {alias}"
        unknown = {
            phase: sorted(placeholders(command) - TASK_PLACEHOLDERS)
            for phase, command in (
                ("plan", agent.commands.plan),
                ("execution", agent.commands.execution),
            )
        }
        bad = {phase: names for phase, names in unknown.items() if names}
        if bad:
            add(
                key,
                title,
                "error",
                "Unknown placeholders: "
                + "; ".join(f"{phase}: {', '.join(names)}" for phase, names in bad.items()),
            )
            continue
        learner_unknown = placeholders(agent.commands.direct) - {"prompt", "prompt_file"}
        notes: list[str] = []
        if learner_unknown and delivers_prompt(agent.commands.direct):
            notes.append(
                "the learner (direct) command may use only {prompt} or {prompt_file}; found "
                + ", ".join(sorted(learner_unknown))
            )
        interactive = Path(agent.commands.execution[0]).name in INTERACTIVE_CLIS
        pasted = [
            phase.value
            for phase in PromptPhase
            if not delivers_prompt(
                agent.commands.plan if phase == PromptPhase.PLAN else agent.commands.execution
            )
        ]
        if interactive and pasted:
            notes.append(
                f"{', '.join(pasted)} prompts are pasted into a new session; interactive CLIs can "
                "drop them while starting. Pass {prompt} or {prompt_file} as an argument instead"
            )
        if notes:
            add(key, title, "warn", "; ".join(notes))
        else:
            add(key, title, "ok", "Commands and prompt delivery look correct")


def _tracker_checks(context: WorkspaceContext, add: Add) -> None:
    try:
        services = context.services()
        issues = services.sync.validate()
    except (ValueError, KeyError, OSError) as exc:
        add("tracker", "Markdown tracker", "error", str(exc))
        return
    if not services.config.trackers.markdown.enabled:
        add("tracker", "Markdown tracker", "info", "Disabled in the configuration")
    elif issues:
        add("tracker", "Markdown tracker", "warn", "; ".join(issues))
    else:
        add("tracker", "Markdown tracker", "ok", "Tracker files and rows are in sync")


def _knowledge_checks(config: AlfredConfig, add: Add) -> None:
    required = config.knowledge.required_completion_entries
    detail = f"{config.knowledge.directory}; successful completions need {required} entr" + (
        "y" if required == 1 else "ies"
    )
    add("knowledge", "Knowledge", "ok" if required == 0 else "info", detail)


def _run(arguments: tuple[str, ...], cwd: Path) -> tuple[int, str]:
    result = SubprocessRunner().run(arguments, cwd=cwd, check=False)
    return result.returncode, result.stdout
