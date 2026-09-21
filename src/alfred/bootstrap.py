"""Side-effect-light composition root for Alfred's configured services."""

from dataclasses import dataclass
from pathlib import Path

from alfred.adapters.completion import CompletionFileStore
from alfred.adapters.git.commits import GitCommitManager
from alfred.adapters.git.worktrees import GitWorktreeManager
from alfred.adapters.markdown import DisabledTracker, MarkdownTracker
from alfred.adapters.process import SubprocessRunner
from alfred.adapters.state import JsonStateStore
from alfred.adapters.tmux import TmuxSessionBackend
from alfred.application.coordinator import Coordinator
from alfred.application.dispatch import AgentDispatcher
from alfred.application.knowledge import KnowledgeService
from alfred.application.learner import LearnerService
from alfred.application.notifications import NotificationService
from alfred.application.runs import RunService
from alfred.application.sync import SyncService
from alfred.application.tasks import TaskService
from alfred.config.loader import discover_config, load_config
from alfred.config.models import AlfredConfig
from alfred.utils.time import Clock


@dataclass(frozen=True, slots=True)
class AlfredServices:
    """Fully configured application services used by command handlers."""

    config: AlfredConfig
    store: JsonStateStore
    tasks: TaskService
    worktrees: GitWorktreeManager
    commits: GitCommitManager
    runs: RunService
    sync: SyncService
    knowledge: KnowledgeService
    notifications: NotificationService
    coordinator: Coordinator
    learner: LearnerService
    sessions: TmuxSessionBackend


def build_services(
    *,
    config_path: Path | None = None,
    start: Path | None = None,
) -> AlfredServices:
    """Discover configuration, initialize local state, and connect adapters."""
    config = load_config(discover_config(start, explicit=config_path))
    clock = Clock.from_name(config.runtime.timezone)
    store = JsonStateStore(config.runtime.state_directory)
    store.initialize()
    tracker = (
        MarkdownTracker(config.trackers.markdown)
        if config.trackers.markdown.enabled
        else DisabledTracker()
    )
    runner = SubprocessRunner()
    sessions = TmuxSessionBackend(runner)
    tasks = TaskService(
        store,
        tracker,
        clock,
        agent_aliases=config.agents,
        repository_names=(repository.name for repository in config.workspace.repositories),
    )
    worktrees = GitWorktreeManager(
        config.workspace,
        config.runtime.worktree_directory,
        runner,
    )
    commits = GitCommitManager(worktrees, config.workspace, config.commits, runner)
    dispatcher = AgentDispatcher(config, sessions)
    completions = CompletionFileStore(config.runtime.temp_directory)
    knowledge = KnowledgeService(config.knowledge.directory, clock)
    notifications = NotificationService(store, clock)
    runs = RunService(
        tasks,
        store,
        worktrees,
        dispatcher,
        sessions,
        completions,
        knowledge,
        clock,
    )
    return AlfredServices(
        config=config,
        store=store,
        tasks=tasks,
        worktrees=worktrees,
        commits=commits,
        runs=runs,
        sync=SyncService(config.trackers.markdown, tasks),
        knowledge=knowledge,
        notifications=notifications,
        coordinator=Coordinator(config, store, completions, notifications, sessions),
        learner=LearnerService(config, sessions),
        sessions=sessions,
    )
