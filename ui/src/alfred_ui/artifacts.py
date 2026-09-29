"""Read Alfred's runtime files: prompts, completion handoffs, knowledge, tracker, and state."""

import json
import re
from pathlib import Path
from typing import Any

from alfred.adapters.state.json_store import DEFAULT_DOCUMENTS
from alfred.config.models import AlfredConfig
from alfred.domain.constants import KnowledgeCategory

COMPLETION_BUCKETS = ("pending", "processed", "invalid")
COMPLETION_NAME = re.compile(r"task-(\d+)(?:-(\d+))?\.json")
KNOWLEDGE_TASK = re.compile(r"-task-(\d+)-")
DAILY_NOTE = re.compile(r"\d{4}-\d{2}-\d{2}\.md")
PROMPT_NAME = re.compile(r"(?:task-\d+-(?:plan|execution)|learner)\.md")
MAX_TEXT_BYTES = 2_000_000


def contained(base: Path, relative: str) -> Path:
    """Resolve ``relative`` under ``base`` and reject any path that escapes it."""
    root = base.resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError(f"Path is outside {root}")
    return candidate


def read_text(path: Path) -> str:
    """Read UTF-8 text, replacing undecodable bytes and truncating very large files."""
    with path.open("rb") as handle:
        data = handle.read(MAX_TEXT_BYTES + 1)
    text = data[:MAX_TEXT_BYTES].decode("utf-8", errors="replace")
    if len(data) > MAX_TEXT_BYTES:
        text += "\n… (truncated)\n"
    return text


def file_info(path: Path, root: Path | None = None) -> dict[str, Any]:
    """Describe a file with its path, size, and modification time."""
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path),
        "relative": str(path.relative_to(root)) if root else path.name,
        "size": stat.st_size,
        "modified": stat.st_mtime,
    }


def prompts_directory(config: AlfredConfig) -> Path:
    """Return the directory where Alfred writes rendered prompts."""
    return config.runtime.temp_directory / "prompts"


def prompt_files(config: AlfredConfig, task_number: int) -> list[dict[str, Any]]:
    """Return the plan and execution prompts rendered for one task."""
    prompts: list[dict[str, Any]] = []
    for phase in ("plan", "execution"):
        path = prompts_directory(config) / f"task-{task_number}-{phase}.md"
        if path.is_file():
            prompts.append({"phase": phase, **file_info(path), "content": read_text(path)})
    return prompts


def read_prompt(config: AlfredConfig, name: str) -> dict[str, Any]:
    """Read one prompt file by its file name; a prompt not written yet reports ``exists``."""
    if not PROMPT_NAME.fullmatch(name):
        raise ValueError(f"Unknown prompt file {name!r}")
    path = contained(prompts_directory(config), name)
    if not path.is_file():
        return {"name": name, "path": str(path), "exists": False, "content": ""}
    return {**file_info(path), "exists": True, "content": read_text(path)}


def completion_files(config: AlfredConfig, task_number: int | None = None) -> dict[str, Any]:
    """Return pending, processed, and invalid completion handoffs with their contents."""
    root = config.runtime.temp_directory / "completions"
    buckets: dict[str, list[dict[str, Any]]] = {}
    for bucket in COMPLETION_BUCKETS:
        directory = root / bucket
        entries: list[dict[str, Any]] = []
        if directory.is_dir():
            for path in sorted(directory.glob("task-*.json")):
                match = COMPLETION_NAME.fullmatch(path.name)
                number = int(match.group(1)) if match else None
                if task_number is not None and number != task_number:
                    continue
                entries.append(_completion_entry(path, bucket, number))
        buckets[bucket] = sorted(entries, key=lambda item: item["modified"], reverse=True)
    return {"directory": str(root), **buckets}


def _completion_entry(path: Path, bucket: str, task_number: int | None) -> dict[str, Any]:
    raw = read_text(path)
    report: Any = None
    error = ""
    try:
        report = json.loads(raw)
    except json.JSONDecodeError as exc:
        error = str(exc)
    return {
        **file_info(path),
        "bucket": bucket,
        "task_number": task_number,
        "report": report if isinstance(report, dict) else None,
        "raw": raw,
        "error": error or ("" if isinstance(report, dict) else "Report is not a JSON object"),
    }


def knowledge_entries(
    config: AlfredConfig,
    *,
    category: str | None = None,
    task_number: int | None = None,
) -> list[dict[str, Any]]:
    """Return parsed knowledge entries, newest first."""
    root = config.knowledge.directory
    categories = (KnowledgeCategory(category),) if category else tuple(KnowledgeCategory)
    entries: list[dict[str, Any]] = []
    for item in categories:
        directory = root / item.value
        if not directory.is_dir():
            continue
        for path in directory.glob("*.md"):
            entry = parse_knowledge(path, root)
            if task_number is None or entry["task_number"] == task_number:
                entries.append(entry)
    return sorted(entries, key=lambda entry: (entry["created"], entry["relative"]), reverse=True)


def knowledge_counts(config: AlfredConfig) -> dict[int, int]:
    """Count knowledge entries per task using Alfred's stable file-name convention."""
    counts: dict[int, int] = {}
    root = config.knowledge.directory
    for item in KnowledgeCategory:
        directory = root / item.value
        if not directory.is_dir():
            continue
        for path in directory.glob("*.md"):
            match = KNOWLEDGE_TASK.search(path.name)
            if match:
                number = int(match.group(1))
                counts[number] = counts.get(number, 0) + 1
    return counts


def parse_knowledge(path: Path, root: Path) -> dict[str, Any]:
    """Parse the Markdown layout written by Alfred's knowledge service."""
    text = read_text(path)
    lines = text.splitlines()
    title = next((line[2:].strip() for line in lines if line.startswith("# ")), path.stem)
    meta: dict[str, str] = {}
    for line in lines:
        match = re.match(r"- (Task|Category|Created|Agent|Files|Repositories): (.*)", line)
        if match:
            meta[match.group(1).lower()] = match.group(2).strip()
    summary = _section(text, "Summary")
    number_match = KNOWLEDGE_TASK.search(path.name)
    task_value = meta.get("task", "")
    task_number = (
        int(task_value)
        if task_value.isdigit()
        else (int(number_match.group(1)) if number_match else None)
    )
    return {
        **file_info(path, root),
        "title": title,
        "task_number": task_number,
        "category": meta.get("category", path.parent.name),
        "created": meta.get("created", ""),
        "agent": meta.get("agent", ""),
        "summary": summary,
        "files": _split(meta.get("files", "")),
        "repositories": _split(meta.get("repositories", "")),
        "content": text,
    }


def read_knowledge(config: AlfredConfig, relative: str) -> dict[str, Any]:
    """Read one knowledge entry by its path relative to the knowledge directory."""
    root = config.knowledge.directory
    path = contained(root, relative)
    if path.suffix != ".md" or not path.is_file():
        raise ValueError(f"Knowledge entry does not exist: {relative}")
    return parse_knowledge(path, root)


def tracker_files(config: AlfredConfig) -> dict[str, Any]:
    """Return the configured Markdown tracker files and the list of daily notes."""
    tracker = config.trackers.markdown
    result: dict[str, Any] = {"enabled": tracker.enabled}
    for label in ("canonical", "agents"):
        path: Path | None = getattr(tracker, label)
        result[label] = _optional_file(path)
    daily = tracker.daily_notes
    notes: list[dict[str, Any]] = []
    if daily is not None and daily.is_dir():
        notes = [
            file_info(path)
            for path in sorted(daily.glob("*.md"), reverse=True)
            if DAILY_NOTE.fullmatch(path.name)
        ]
    result["daily_notes"] = {
        "path": str(daily) if daily else "",
        "exists": bool(daily and daily.is_dir()),
        "files": notes,
    }
    return result


def read_daily_note(config: AlfredConfig, name: str) -> dict[str, Any]:
    """Read one daily note by file name (``YYYY-MM-DD.md``)."""
    daily = config.trackers.markdown.daily_notes
    if daily is None:
        raise ValueError("Daily notes are not configured")
    if not DAILY_NOTE.fullmatch(name):
        raise ValueError(f"Daily note names look like 2026-01-31.md, not {name!r}")
    path = contained(daily, name)
    if not path.is_file():
        raise ValueError(f"Daily note does not exist: {name}")
    return {**file_info(path), "content": read_text(path)}


def state_document(config: AlfredConfig, name: str) -> dict[str, Any]:
    """Return one raw versioned state document for read-only inspection."""
    if name not in DEFAULT_DOCUMENTS:
        known = ", ".join(sorted(DEFAULT_DOCUMENTS))
        raise ValueError(f"Unknown state document {name!r}; expected one of: {known}")
    path = config.runtime.state_directory / f"{name}.json"
    if not path.is_file():
        return {"name": f"{name}.json", "path": str(path), "exists": False, "content": ""}
    return {**file_info(path), "exists": True, "content": read_text(path)}


def _optional_file(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"path": "", "exists": False, "content": ""}
    if not path.is_file():
        return {"path": str(path), "exists": False, "content": ""}
    return {**file_info(path), "exists": True, "content": read_text(path)}


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return match.group(1).strip() if match else ""


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
