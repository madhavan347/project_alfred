"""Pure task reporting projections for CLI and integrations."""

from dataclasses import dataclass

from alfred.domain.constants import TaskStatus
from alfred.domain.models import Task


@dataclass(frozen=True, slots=True)
class VelocityReport:
    """Simple completion totals for the current task state."""

    completed: int
    total: int


def today(tasks: tuple[Task, ...]) -> tuple[Task, ...]:
    """Return active tasks in task-number order."""
    terminal = {TaskStatus.COMPLETED, TaskStatus.CONSOLIDATED}
    return tuple(sorted((task for task in tasks if task.status not in terminal), key=_number))


def risks(tasks: tuple[Task, ...]) -> tuple[Task, ...]:
    """Return blocked, held, or high-priority tasks."""
    risky_statuses = {TaskStatus.BLOCKED, TaskStatus.ON_HOLD}
    return tuple(
        sorted(
            (
                task
                for task in tasks
                if task.status in risky_statuses or task.priority in {"P0", "P1"}
            ),
            key=lambda task: (task.priority, task.task_number),
        )
    )


def dependencies(tasks: tuple[Task, ...]) -> tuple[Task, ...]:
    """Return tasks declaring at least one dependency."""
    return tuple(sorted((task for task in tasks if task.dependencies), key=_number))


def velocity(tasks: tuple[Task, ...]) -> VelocityReport:
    """Count tasks in a completed or consolidated terminal state."""
    completed = sum(
        task.status in {TaskStatus.COMPLETED, TaskStatus.CONSOLIDATED} for task in tasks
    )
    return VelocityReport(completed=completed, total=len(tasks))


def _number(task: Task) -> int:
    return task.task_number
