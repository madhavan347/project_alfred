"""Versioned JSON persistence for local Alfred state."""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from alfred.utils.files import atomic_write_json


STATE_VERSION = 1
DEFAULT_DOCUMENTS: Mapping[str, object] = {
    "tasks": {"schema_version": STATE_VERSION, "tasks": []},
    "runs": {"schema_version": STATE_VERSION, "runs": []},
    "queue": {"schema_version": STATE_VERSION, "queued_tasks": []},
    "notifications": {"schema_version": STATE_VERSION, "notifications": []},
}


class StateError(ValueError):
    """Raised when persisted state cannot be read safely."""


class JsonStateStore:
    """Read and atomically replace versioned state documents."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def initialize(self) -> None:
        """Create missing state documents without overwriting existing data."""
        self.directory.mkdir(parents=True, exist_ok=True)
        for name, default in DEFAULT_DOCUMENTS.items():
            path = self.path(name)
            if not path.exists():
                atomic_write_json(path, default)

    def path(self, name: str) -> Path:
        """Resolve a known state document name."""
        if name not in DEFAULT_DOCUMENTS:
            known = ", ".join(sorted(DEFAULT_DOCUMENTS))
            raise KeyError(f"Unknown state document {name!r}; expected one of: {known}")
        return self.directory / f"{name}.json"

    def read_document(self, name: str) -> dict[str, Any]:
        """Read a state document and validate its schema envelope."""
        path = self.path(name)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise StateError(f"State document does not exist: {path}") from exc
        except json.JSONDecodeError as exc:
            raise StateError(f"State document is invalid JSON: {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise StateError(f"State document must contain an object: {path}")
        version = value.get("schema_version")
        if version != STATE_VERSION:
            raise StateError(
                f"Unsupported state version {version!r} in {path}; expected {STATE_VERSION}"
            )
        return value

    def write_document(self, name: str, value: Mapping[str, Any]) -> None:
        """Validate and atomically replace one state document."""
        payload = dict(value)
        payload["schema_version"] = STATE_VERSION
        atomic_write_json(self.path(name), payload)

    def tasks(self) -> list[dict[str, Any]]:
        """Return task records."""
        return _record_list(self.read_document("tasks"), "tasks")

    def save_tasks(self, tasks: Sequence[Mapping[str, Any]]) -> None:
        """Replace task records."""
        self.write_document("tasks", {"tasks": [dict(task) for task in tasks]})

    def runs(self) -> list[dict[str, Any]]:
        """Return run records."""
        return _record_list(self.read_document("runs"), "runs")

    def save_runs(self, runs: Sequence[Mapping[str, Any]]) -> None:
        """Replace run records."""
        self.write_document("runs", {"runs": [dict(run) for run in runs]})

    def queue(self) -> list[int]:
        """Return unique queued task numbers in stored order."""
        value = self.read_document("queue").get("queued_tasks")
        if not isinstance(value, list) or not all(isinstance(item, int) for item in value):
            raise StateError("queue.json queued_tasks must be an integer array")
        return value

    def save_queue(self, task_numbers: Sequence[int]) -> None:
        """Replace the queue with sorted unique task numbers."""
        self.write_document("queue", {"queued_tasks": sorted(set(task_numbers))})


def _record_list(document: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    value = document.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise StateError(f"{key}.json {key} must be an object array")
    return [dict(item) for item in value]
