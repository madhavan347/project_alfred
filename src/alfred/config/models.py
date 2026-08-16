"""Immutable configuration detail objects used by Alfred services."""

from dataclasses import dataclass, field
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping

from alfred.config.constants import (
    CONFIG_VERSION,
    DEFAULT_COMMIT_TAGS,
    DEFAULT_SESSION_PREFIX,
    DEFAULT_STATE_DIRECTORY,
    DEFAULT_TEMP_DIRECTORY,
    DEFAULT_TIMEZONE,
    DEFAULT_TMUX_POLICY,
)


@dataclass(frozen=True, slots=True)
class CommandConfig:
    """Argument-vector templates for an agent runtime."""

    direct: tuple[str, ...]
    plan: tuple[str, ...]
    execution: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AgentConfig:
    """A named command-line agent available to Alfred."""

    alias: str
    runtime_target: str
    commands: CommandConfig

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", self.alias):
            raise ValueError(
                "Agent alias must start with an alphanumeric character and contain only "
                "letters, numbers, underscores, or hyphens"
            )


@dataclass(frozen=True, slots=True)
class RepositoryConfig:
    """A repository Alfred may place in a task worktree."""

    name: str
    path: Path
    default_branch: str = "main"
    remote: str = "origin"
    selected_by_default: bool = False

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", self.name):
            raise ValueError(
                "Repository name must start with an alphanumeric character and contain only "
                "letters, numbers, dots, underscores, or hyphens"
            )


@dataclass(frozen=True, slots=True)
class WorkspaceConfig:
    """Workspace root and configured repositories."""

    root: Path
    repositories: tuple[RepositoryConfig, ...] = ()

    def repository(self, name: str) -> RepositoryConfig:
        """Return a repository by name or raise an actionable error."""
        for repository in self.repositories:
            if repository.name == name:
                return repository
        available = ", ".join(item.name for item in self.repositories) or "none"
        raise KeyError(f"Unknown repository {name!r}; configured repositories: {available}")


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Filesystem, time, and session behavior for one workspace."""

    timezone: str = DEFAULT_TIMEZONE
    state_directory: Path = DEFAULT_STATE_DIRECTORY
    temp_directory: Path = DEFAULT_TEMP_DIRECTORY
    session_prefix: str = DEFAULT_SESSION_PREFIX
    tmux_unavailable_policy: str = DEFAULT_TMUX_POLICY


@dataclass(frozen=True, slots=True)
class MarkdownTrackerConfig:
    """Optional Markdown tracker paths."""

    enabled: bool = False
    canonical: Path | None = None
    agents: Path | None = None
    daily_notes: Path | None = None


@dataclass(frozen=True, slots=True)
class TrackerConfig:
    """Configured tracker integrations."""

    markdown: MarkdownTrackerConfig = field(default_factory=MarkdownTrackerConfig)


@dataclass(frozen=True, slots=True)
class CommitConfig:
    """Allowed commit types and their rendered bracket tags."""

    tags: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType(dict(DEFAULT_COMMIT_TAGS))
    )


@dataclass(frozen=True, slots=True)
class KnowledgeConfig:
    """Knowledge-store behavior for completed tasks."""

    directory: Path = Path(".alfred/knowledge")
    required_completion_entries: int = 0


@dataclass(frozen=True, slots=True)
class AlfredConfig:
    """Complete validated configuration for one Alfred workspace."""

    config_path: Path
    workspace: WorkspaceConfig
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    agents: Mapping[str, AgentConfig] = field(default_factory=lambda: MappingProxyType({}))
    trackers: TrackerConfig = field(default_factory=TrackerConfig)
    commits: CommitConfig = field(default_factory=CommitConfig)
    knowledge: KnowledgeConfig = field(default_factory=KnowledgeConfig)
    version: int = CONFIG_VERSION
