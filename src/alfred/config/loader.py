"""Discover and load versioned project-local Alfred configuration."""

import os
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any

from alfred.config.constants import (
    CONFIG_DIRECTORY,
    CONFIG_FILENAME,
    CONFIG_VERSION,
    DEFAULT_COMMIT_TAGS,
    DEFAULT_SESSION_PREFIX,
    DEFAULT_STATE_DIRECTORY,
    DEFAULT_TEMP_DIRECTORY,
    DEFAULT_TIMEZONE,
    DEFAULT_TMUX_POLICY,
    VALID_TMUX_POLICIES,
)
from alfred.config.models import (
    AgentConfig,
    AlfredConfig,
    CommandConfig,
    CommitConfig,
    KnowledgeConfig,
    MarkdownTrackerConfig,
    RepositoryConfig,
    RuntimeConfig,
    TrackerConfig,
    WorkspaceConfig,
)


class ConfigError(ValueError):
    """Raised when Alfred configuration is missing or invalid."""


def discover_config(
    start: Path | None = None,
    *,
    explicit: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> Path:
    """Resolve config using explicit path, environment, then parent discovery."""
    if explicit is not None:
        return _require_file(explicit.expanduser()).resolve()

    environment = os.environ if environment is None else environment
    configured = environment.get("ALFRED_CONFIG")
    if configured:
        return _require_file(Path(configured).expanduser()).resolve()

    current = (start or Path.cwd()).expanduser().resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        candidate = directory / CONFIG_DIRECTORY / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    raise ConfigError(
        "No Alfred configuration found. Run 'alfred init' or pass --config PATH."
    )


def load_config(path: Path) -> AlfredConfig:
    """Parse and validate a TOML configuration file."""
    config_path = _require_file(path.expanduser()).resolve()
    try:
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {config_path}: {exc}") from exc

    _reject_unknown(
        payload,
        {"version", "alfred", "workspace", "repositories", "agents", "trackers", "commit", "knowledge"},
        "configuration",
    )
    version = _integer(payload, "version", default=CONFIG_VERSION)
    if version != CONFIG_VERSION:
        raise ConfigError(f"Unsupported config version {version}; expected {CONFIG_VERSION}")

    workspace_table = _table(payload, "workspace")
    _reject_unknown(workspace_table, {"root"}, "workspace")
    root_value = _string(workspace_table, "root", default="..")
    workspace_root = _resolve_path(root_value, config_path.parent)

    repositories = _load_repositories(payload.get("repositories", ()), workspace_root)
    workspace = WorkspaceConfig(root=workspace_root, repositories=repositories)

    alfred_table = _table(payload, "alfred")
    _reject_unknown(
        alfred_table,
        {
            "timezone",
            "state_directory",
            "temp_directory",
            "session_prefix",
            "tmux_unavailable_policy",
        },
        "alfred",
    )
    tmux_policy = _string(
        alfred_table, "tmux_unavailable_policy", default=DEFAULT_TMUX_POLICY
    )
    if tmux_policy not in VALID_TMUX_POLICIES:
        expected = ", ".join(sorted(VALID_TMUX_POLICIES))
        raise ConfigError(f"alfred.tmux_unavailable_policy must be one of: {expected}")
    runtime = RuntimeConfig(
        timezone=_string(alfred_table, "timezone", default=DEFAULT_TIMEZONE),
        state_directory=_resolve_path(
            _string(alfred_table, "state_directory", default=str(DEFAULT_STATE_DIRECTORY)),
            workspace_root,
        ),
        temp_directory=_resolve_path(
            _string(alfred_table, "temp_directory", default=str(DEFAULT_TEMP_DIRECTORY)),
            workspace_root,
        ),
        session_prefix=_string(
            alfred_table, "session_prefix", default=DEFAULT_SESSION_PREFIX
        ),
        tmux_unavailable_policy=tmux_policy,
    )

    agents = _load_agents(_table(payload, "agents"))
    trackers = _load_trackers(_table(payload, "trackers"), workspace_root)
    commits = _load_commits(_table(payload, "commit"))
    knowledge = _load_knowledge(_table(payload, "knowledge"), workspace_root)

    return AlfredConfig(
        config_path=config_path,
        workspace=workspace,
        runtime=runtime,
        agents=MappingProxyType(agents),
        trackers=trackers,
        commits=commits,
        knowledge=knowledge,
        version=version,
    )


def _load_repositories(value: object, root: Path) -> tuple[RepositoryConfig, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ConfigError("repositories must be an array of tables")
    repositories: list[RepositoryConfig] = []
    names: set[str] = set()
    for index, item in enumerate(value):
        table = _as_table(item, f"repositories[{index}]")
        _reject_unknown(
            table,
            {"name", "path", "default_branch", "remote", "selected_by_default"},
            f"repositories[{index}]",
        )
        name = _string(table, "name")
        if name in names:
            raise ConfigError(f"Duplicate repository name: {name}")
        names.add(name)
        repositories.append(
            RepositoryConfig(
                name=name,
                path=_resolve_path(_string(table, "path"), root),
                default_branch=_string(table, "default_branch", default="main"),
                remote=_string(table, "remote", default="origin"),
                selected_by_default=_boolean(table, "selected_by_default", default=False),
            )
        )
    return tuple(repositories)


def _load_agents(value: Mapping[str, Any]) -> dict[str, AgentConfig]:
    agents: dict[str, AgentConfig] = {}
    for alias, raw in value.items():
        table = _as_table(raw, f"agents.{alias}")
        _reject_unknown(table, {"runtime_target", "commands"}, f"agents.{alias}")
        commands = _table(table, "commands")
        _reject_unknown(commands, {"direct", "plan", "execution"}, f"agents.{alias}.commands")
        agents[alias] = AgentConfig(
            alias=alias,
            runtime_target=_string(table, "runtime_target", default=alias),
            commands=CommandConfig(
                direct=_string_tuple(commands, "direct"),
                plan=_string_tuple(commands, "plan"),
                execution=_string_tuple(commands, "execution"),
            ),
        )
    return agents


def _load_trackers(value: Mapping[str, Any], root: Path) -> TrackerConfig:
    _reject_unknown(value, {"markdown"}, "trackers")
    markdown = _table(value, "markdown")
    _reject_unknown(markdown, {"enabled", "canonical", "agents", "daily_notes"}, "trackers.markdown")
    enabled = _boolean(markdown, "enabled", default=False)
    canonical = _optional_path(markdown, "canonical", root)
    agents = _optional_path(markdown, "agents", root)
    daily_notes = _optional_path(markdown, "daily_notes", root)
    if enabled and None in (canonical, agents, daily_notes):
        raise ConfigError(
            "Enabled Markdown tracking requires canonical, agents, and daily_notes paths"
        )
    return TrackerConfig(
        markdown=MarkdownTrackerConfig(
            enabled=enabled,
            canonical=canonical,
            agents=agents,
            daily_notes=daily_notes,
        )
    )


def _load_commits(value: Mapping[str, Any]) -> CommitConfig:
    _reject_unknown(value, {"tags"}, "commit")
    raw_tags = _table(value, "tags")
    tags = dict(DEFAULT_COMMIT_TAGS) if not raw_tags else {}
    for name, tag in raw_tags.items():
        if not isinstance(tag, str) or not tag.strip():
            raise ConfigError(f"commit.tags.{name} must be a non-empty string")
        tags[name.upper()] = tag.strip()
    return CommitConfig(tags=MappingProxyType(tags))


def _load_knowledge(value: Mapping[str, Any], root: Path) -> KnowledgeConfig:
    _reject_unknown(value, {"directory", "required_completion_entries"}, "knowledge")
    return KnowledgeConfig(
        directory=_resolve_path(
            _string(value, "directory", default=".alfred/knowledge"), root
        ),
        required_completion_entries=_integer(
            value, "required_completion_entries", default=0
        ),
    )


def _require_file(path: Path) -> Path:
    if not path.is_file():
        raise ConfigError(f"Alfred configuration does not exist: {path}")
    return path


def _resolve_path(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else base / path).resolve()


def _optional_path(table: Mapping[str, Any], key: str, base: Path) -> Path | None:
    value = table.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{key} must be a non-empty path string")
    return _resolve_path(value, base)


def _table(table: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = table.get(key, {})
    return _as_table(value, key)


def _as_table(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigError(f"{label} must be a table")
    return value


def _string(table: Mapping[str, Any], key: str, *, default: str | None = None) -> str:
    value = table.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{key} must be a non-empty string")
    return value.strip()


def _string_tuple(table: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = table.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ConfigError(f"{key} must be an argument array")
    if not value or not all(isinstance(item, str) and item for item in value):
        raise ConfigError(f"{key} must contain non-empty string arguments")
    return tuple(value)


def _boolean(table: Mapping[str, Any], key: str, *, default: bool) -> bool:
    value = table.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"{key} must be true or false")
    return value


def _integer(table: Mapping[str, Any], key: str, *, default: int) -> int:
    value = table.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ConfigError(f"{key} must be a non-negative integer")
    return value


def _reject_unknown(table: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise ConfigError(f"Unknown keys in {label}: {', '.join(unknown)}")
