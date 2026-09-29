"""Report projections: Alfred's four CLI reports plus throughput and workload breakdowns."""

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from alfred.application.reports import dependencies, risks, today, velocity
from alfred.domain.constants import RunStatus
from alfred.domain.models import AgentRun, Task

COMPLETION_EVENTS = frozenset({"STATUS_COMPLETED", "PHASE_ARCHIVED", "PHASE_CONSOLIDATED"})


def build_reports(
    tasks: tuple[Task, ...],
    runs: tuple[AgentRun, ...],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return every report the interface shows, computed from current state."""
    speed = velocity(tasks)
    return {
        "today": [_row(task) for task in today(tasks)],
        "risk": [_row(task) for task in risks(tasks)],
        "dependency": [
            {**_row(task), "dependencies": list(task.dependencies)} for task in dependencies(tasks)
        ],
        "velocity": {"completed": speed.completed, "total": speed.total},
        "by_status": dict(Counter(str(task.status) for task in tasks)),
        "by_phase": dict(Counter(str(task.lifecycle_phase) for task in tasks)),
        "by_priority": dict(Counter(task.priority for task in tasks)),
        "by_category": dict(Counter(task.category for task in tasks)),
        "by_agent": dict(Counter(task.assigned_agent_alias or "unassigned" for task in tasks)),
        "throughput": _throughput(events),
        "cycle_times": _cycle_times(tasks, events),
        "runs": _run_stats(runs),
    }


def _row(task: Task) -> dict[str, Any]:
    return {
        "task_number": task.task_number,
        "title": task.title,
        "status": str(task.status),
        "priority": task.priority,
        "agent": task.assigned_agent_alias,
        "phase": str(task.lifecycle_phase),
    }


def _throughput(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Count tasks reaching a terminal state per day (each task counted once per day)."""
    per_day: dict[str, set[int]] = defaultdict(set)
    for event in events:
        if event.get("event_type") in COMPLETION_EVENTS:
            day = str(event.get("timestamp", ""))[:10]
            number = event.get("task_number")
            if day and isinstance(number, int):
                per_day[day].add(number)
    return [{"day": day, "count": len(numbers)} for day, numbers in sorted(per_day.items())]


def _cycle_times(tasks: tuple[Task, ...], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hours from creation to the first terminal event for each finished task."""
    finished: dict[int, str] = {}
    for event in events:
        number = event.get("task_number")
        if event.get("event_type") in COMPLETION_EVENTS and isinstance(number, int):
            finished.setdefault(number, str(event.get("timestamp", "")))
    rows: list[dict[str, Any]] = []
    for task in tasks:
        end = finished.get(task.task_number)
        hours = _hours_between(task.created_at, end) if end else None
        if hours is not None:
            rows.append({"task_number": task.task_number, "title": task.title, "hours": hours})
    return rows


def _run_stats(runs: tuple[AgentRun, ...]) -> dict[str, Any]:
    durations: dict[str, list[float]] = defaultdict(list)
    for run in runs:
        hours = _hours_between(run.started_at, run.ended_at) if run.ended_at else None
        if hours is not None and run.run_status != RunStatus.STOPPED:
            durations[run.agent_alias].append(hours)
    return {
        "by_status": dict(Counter(str(run.run_status) for run in runs)),
        "by_agent": dict(Counter(run.agent_alias for run in runs)),
        "average_hours_by_agent": {
            agent: round(sum(values) / len(values), 3) for agent, values in durations.items()
        },
    }


def _hours_between(start: str, end: str | None) -> float | None:
    if not start or not end:
        return None
    try:
        delta = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    except ValueError:
        return None
    return round(max(delta.total_seconds(), 0) / 3600, 3)
