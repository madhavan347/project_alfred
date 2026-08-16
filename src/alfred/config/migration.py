"""One-way, non-destructive migration from Alfred's legacy runtime layout."""

import json
import shlex
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alfred.adapters.state import JsonStateStore
from alfred.utils.files import atomic_write_json, atomic_write_text


LEGACY_FILES = ("tasks.json", "runs.json", "queue.json", "agent_map.json")
MIGRATION_NAME = "legacy-runtime-v1"


class MigrationError(ValueError):
    """Raised when legacy state cannot be migrated without data loss."""


@dataclass(frozen=True, slots=True)
class MigrationResult:
    """Paths and counts produced by one migration attempt."""

    backup_directory: Path
    marker_path: Path
    agent_fragment: Path | None
    tasks: int
    runs: int
    queued_tasks: int
    already_migrated: bool = False


def migrate_legacy_runtime(
    legacy_directory: Path,
    store: JsonStateStore,
    migration_directory: Path,
    *,
    timestamp: str | None = None,
) -> MigrationResult:
    """Back up and normalize legacy state without deleting its source files."""
    marker_path = migration_directory / f"{MIGRATION_NAME}.json"
    if marker_path.exists():
        return _result_from_marker(marker_path, already_migrated=True)

    source = legacy_directory.expanduser().resolve()
    if not source.is_dir():
        raise MigrationError(f"Legacy runtime directory does not exist: {source}")

    raw = {name: _read_json(source / name) for name in LEGACY_FILES if (source / name).is_file()}
    if not raw:
        raise MigrationError(f"No legacy state files found in {source}")

    tasks = _records(raw.get("tasks.json", []), "tasks")
    runs = _records(raw.get("runs.json", []), "runs")
    queue = _integers(raw.get("queue.json", []), "queued_tasks")
    agent_map = _agent_map(raw.get("agent_map.json", {}))

    _require_empty_destination(store)
    stamp = timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_directory = migration_directory / f"{MIGRATION_NAME}-{stamp}"
    backup_directory.mkdir(parents=True, exist_ok=False)
    for name in LEGACY_FILES:
        path = source / name
        if path.is_file():
            shutil.copy2(path, backup_directory / name)

    store.save_tasks(tasks)
    store.save_runs(runs)
    store.save_queue(queue)

    agent_fragment = None
    if agent_map:
        agent_fragment = backup_directory / "agents.migrated.toml"
        atomic_write_text(agent_fragment, _render_agent_fragment(agent_map))

    payload = {
        "migration": MIGRATION_NAME,
        "source": str(source),
        "backup_directory": str(backup_directory),
        "agent_fragment": str(agent_fragment) if agent_fragment else None,
        "tasks": len(tasks),
        "runs": len(runs),
        "queued_tasks": len(queue),
        "created_at": stamp,
    }
    migration_directory.mkdir(parents=True, exist_ok=True)
    atomic_write_json(marker_path, payload)
    return _result_from_marker(marker_path, already_migrated=False)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MigrationError(f"Legacy file is invalid JSON: {path}: {exc}") from exc


def _records(value: object, key: str) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        value = value.get(key, [])
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise MigrationError(f"Legacy {key} must be an array or an object containing {key}")
    if not all(isinstance(item, Mapping) for item in value):
        raise MigrationError(f"Legacy {key} must contain objects")
    return [dict(item) for item in value]


def _integers(value: object, key: str) -> list[int]:
    if isinstance(value, Mapping):
        value = value.get(key, [])
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise MigrationError(f"Legacy {key} must be an integer array")
    if not all(isinstance(item, int) and not isinstance(item, bool) for item in value):
        raise MigrationError(f"Legacy {key} must contain integers")
    return list(value)


def _agent_map(value: object) -> dict[str, Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        raise MigrationError("Legacy agent_map.json must contain an object")
    result: dict[str, Mapping[str, Any]] = {}
    for alias, config in value.items():
        if not isinstance(alias, str) or not isinstance(config, Mapping):
            raise MigrationError("Legacy agent_map.json entries must be named objects")
        result[alias] = config
    return result


def _require_empty_destination(store: JsonStateStore) -> None:
    store.initialize()
    if store.tasks() or store.runs() or store.queue():
        raise MigrationError(
            f"Destination state is not empty: {store.directory}; refusing to overwrite it"
        )


def _render_agent_fragment(agent_map: Mapping[str, Mapping[str, Any]]) -> str:
    lines = ["# Review and merge these migrated agents into .alfred/config.toml."]
    for alias in sorted(agent_map):
        config = agent_map[alias]
        target = config.get("runtime_target", alias)
        templates = config.get("dispatch_templates", {})
        if not isinstance(target, str) or not isinstance(templates, Mapping):
            raise MigrationError(f"Invalid legacy agent configuration: {alias}")
        lines.extend(["", f"[agents.{alias}]", f"runtime_target = {json.dumps(target)}"])
        lines.append("")
        lines.append(f"[agents.{alias}.commands]")
        for phase in ("direct", "plan", "execution"):
            command = templates.get(phase)
            if not isinstance(command, str) or not command.strip():
                raise MigrationError(f"Legacy agent {alias} is missing a {phase} command")
            arguments = ", ".join(json.dumps(item) for item in shlex.split(command))
            lines.append(f"{phase} = [{arguments}]")
    return "\n".join(lines) + "\n"


def _result_from_marker(marker_path: Path, *, already_migrated: bool) -> MigrationResult:
    payload = _read_json(marker_path)
    if not isinstance(payload, Mapping):
        raise MigrationError(f"Migration marker is invalid: {marker_path}")
    agent_value = payload.get("agent_fragment")
    return MigrationResult(
        backup_directory=Path(str(payload["backup_directory"])),
        marker_path=marker_path,
        agent_fragment=Path(str(agent_value)) if agent_value else None,
        tasks=int(payload["tasks"]),
        runs=int(payload["runs"]),
        queued_tasks=int(payload["queued_tasks"]),
        already_migrated=already_migrated,
    )
