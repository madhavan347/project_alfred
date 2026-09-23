"""Validate, describe, and save Alfred's TOML configuration from the UI.

Validation runs Alfred's own loader against a sibling temporary file so relative paths resolve
exactly as they will after saving. A save keeps the previous file as ``config.toml.bak``.
"""

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from alfred.config.loader import load_config
from alfred.config.models import AlfredConfig
from alfred.utils.files import atomic_write_text
from alfred.utils.time import Clock

from alfred_ui.agents import describe_agent

AGENT_PRESETS: dict[str, dict[str, Any]] = {
    "claude": {
        "label": "Claude Code",
        "runtime_target": "claude-code",
        "commands": {
            "direct": ["claude", "{prompt}"],
            "plan": ["claude", "{prompt}"],
            "execution": ["claude", "{prompt}"],
        },
    },
    "codex": {
        "label": "Codex CLI",
        "runtime_target": "codex",
        "commands": {
            "direct": ["codex", "{prompt}"],
            "plan": ["codex", "{prompt}"],
            "execution": ["codex", "{prompt}"],
        },
    },
    "agy": {
        "label": "Antigravity",
        "runtime_target": "antigravity",
        "commands": {
            "direct": ["agy", "-i", "{prompt}"],
            "plan": ["agy", "-i", "{prompt}"],
            "execution": ["agy", "-i", "{prompt}"],
        },
    },
    "recorder": {
        "label": "Recorder (test double that waits forever)",
        "runtime_target": "local-test",
        "commands": {
            "direct": ["tail", "-f", "/dev/null"],
            "plan": ["tail", "-f", "/dev/null"],
            "execution": ["tail", "-f", "/dev/null"],
        },
    },
}


def read_config_text(path: Path) -> str:
    """Return the configuration file's text."""
    return path.read_text(encoding="utf-8")


def validate_config_text(path: Path, text: str) -> dict[str, Any]:
    """Validate TOML text as if it were saved at ``path``."""
    candidate = path.parent / f".{path.name}.check-{uuid.uuid4().hex}.toml"
    try:
        atomic_write_text(candidate, text)
        config = load_config(candidate)
        Clock.from_name(config.runtime.timezone)
    except KeyError as exc:
        return {"valid": False, "error": str(exc.args[0] if exc.args else exc)}
    except (ValueError, TypeError, OSError) as exc:
        return {"valid": False, "error": str(exc).replace(str(candidate), str(path))}
    finally:
        candidate.unlink(missing_ok=True)
    return {"valid": True, "error": "", "summary": describe_config(config, config_path=path)}


def save_config_text(path: Path, text: str) -> dict[str, Any]:
    """Validate and atomically replace the configuration, keeping a backup."""
    result = validate_config_text(path, text)
    if not result["valid"]:
        raise ValueError(f"Configuration was not saved: {result['error']}")
    backup = path.with_name(f"{path.name}.bak")
    if path.is_file():
        shutil.copy2(path, backup)
    atomic_write_text(path, text if text.endswith("\n") else f"{text}\n")
    return {**result, "backup": str(backup)}


def describe_config(config: AlfredConfig, *, config_path: Path | None = None) -> dict[str, Any]:
    """Return a JSON-friendly view of a loaded configuration."""
    runtime = config.runtime
    tracker = config.trackers.markdown
    return {
        "config_path": str(config_path or config.config_path),
        "version": config.version,
        "workspace_root": str(config.workspace.root),
        "runtime": {
            "timezone": runtime.timezone,
            "state_directory": str(runtime.state_directory),
            "temp_directory": str(runtime.temp_directory),
            "worktree_directory": str(runtime.worktree_directory),
            "session_prefix": runtime.session_prefix,
            "tmux_unavailable_policy": runtime.tmux_unavailable_policy,
        },
        "repositories": [
            {
                "name": repository.name,
                "path": str(repository.path),
                "default_branch": repository.default_branch,
                "remote": repository.remote,
                "selected_by_default": repository.selected_by_default,
                "exists": repository.path.is_dir(),
                "is_git": (repository.path / ".git").exists(),
            }
            for repository in config.workspace.repositories
        ],
        "agents": [describe_agent(agent) for _, agent in sorted(config.agents.items())],
        "tracker": {
            "enabled": tracker.enabled,
            "canonical": str(tracker.canonical) if tracker.canonical else "",
            "agents": str(tracker.agents) if tracker.agents else "",
            "daily_notes": str(tracker.daily_notes) if tracker.daily_notes else "",
        },
        "commit_tags": dict(config.commits.tags),
        "knowledge": {
            "directory": str(config.knowledge.directory),
            "required_completion_entries": config.knowledge.required_completion_entries,
        },
    }


def repository_block(
    name: str,
    path: str,
    *,
    default_branch: str = "main",
    remote: str = "origin",
    selected_by_default: bool = False,
) -> str:
    """Render a ``[[repositories]]`` TOML block."""
    return "\n".join(
        [
            "[[repositories]]",
            f"name = {_string(name)}",
            f"path = {_string(path)}",
            f"default_branch = {_string(default_branch)}",
            f"remote = {_string(remote)}",
            f"selected_by_default = {'true' if selected_by_default else 'false'}",
            "",
        ]
    )


def agent_block(alias: str, runtime_target: str, commands: dict[str, list[str]]) -> str:
    """Render ``[agents.<alias>]`` and its command arrays as TOML."""
    lines = [f"[agents.{alias}]", f"runtime_target = {_string(runtime_target)}", ""]
    lines.append(f"[agents.{alias}.commands]")
    for phase in ("direct", "plan", "execution"):
        arguments = ", ".join(_string(item) for item in commands.get(phase, []))
        lines.append(f"{phase} = [{arguments}]")
    lines.append("")
    return "\n".join(lines)


def _string(value: str) -> str:
    # JSON string escaping is valid TOML basic-string escaping for these values.
    return json.dumps(value, ensure_ascii=False)
