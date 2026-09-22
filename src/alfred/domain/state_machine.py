"""Task status and lifecycle transition policy."""

from collections.abc import Mapping

from alfred.domain.constants import (
    CompletionStatus,
    LifecyclePhase,
    RunStatus,
    TaskStatus,
)

STATUS_TRANSITIONS: Mapping[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PENDING: frozenset(
        {
            TaskStatus.RUNNING,
            TaskStatus.IN_PROGRESS,
            TaskStatus.QUEUED,
            TaskStatus.BLOCKED,
            TaskStatus.ON_HOLD,
        }
    ),
    TaskStatus.QUEUED: frozenset(
        {
            TaskStatus.PENDING,
            TaskStatus.RUNNING,
            TaskStatus.IN_PROGRESS,
            TaskStatus.BLOCKED,
            TaskStatus.ON_HOLD,
        }
    ),
    TaskStatus.RUNNING: frozenset(
        {
            TaskStatus.PENDING,
            TaskStatus.IN_PROGRESS,
            TaskStatus.BLOCKED,
            TaskStatus.ON_HOLD,
            TaskStatus.IN_REVIEW,
        }
    ),
    TaskStatus.IN_PROGRESS: frozenset(
        {
            TaskStatus.RUNNING,
            TaskStatus.BLOCKED,
            TaskStatus.ON_HOLD,
            TaskStatus.IN_REVIEW,
            TaskStatus.PENDING,
        }
    ),
    TaskStatus.IN_REVIEW: frozenset(
        {TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED, TaskStatus.BLOCKED}
    ),
    TaskStatus.BLOCKED: frozenset({TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.QUEUED}),
    TaskStatus.ON_HOLD: frozenset({TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.QUEUED}),
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.CONSOLIDATED: frozenset(),
}

PHASE_TRANSITIONS: Mapping[LifecyclePhase, frozenset[LifecyclePhase]] = {
    LifecyclePhase.ACTIVE: frozenset(
        {LifecyclePhase.TESTING_DEPLOYMENT, LifecyclePhase.CONSOLIDATED}
    ),
    LifecyclePhase.TESTING_DEPLOYMENT: frozenset({LifecyclePhase.ACTIVE, LifecyclePhase.ARCHIVED}),
    LifecyclePhase.ARCHIVED: frozenset(),
    LifecyclePhase.CONSOLIDATED: frozenset(),
}

ACTIVE_RUN_STATUSES = frozenset({RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.BLOCKED})

COMPLETION_TASK_STATUS: Mapping[CompletionStatus, TaskStatus] = {
    CompletionStatus.SUCCESS: TaskStatus.IN_REVIEW,
    CompletionStatus.FAILED: TaskStatus.IN_PROGRESS,
    CompletionStatus.BLOCKED: TaskStatus.BLOCKED,
}

COMPLETION_RUN_STATUS: Mapping[CompletionStatus, RunStatus] = {
    CompletionStatus.SUCCESS: RunStatus.COMPLETED,
    CompletionStatus.FAILED: RunStatus.FAILED,
    CompletionStatus.BLOCKED: RunStatus.BLOCKED,
}


class TransitionError(ValueError):
    """Raised when a requested lifecycle transition is not allowed."""


def can_transition(current: TaskStatus, target: TaskStatus) -> bool:
    """Return whether ``current`` may move to ``target``."""
    return current == target or target in STATUS_TRANSITIONS[current]


def require_transition(current: TaskStatus, target: TaskStatus) -> None:
    """Raise a clear error if a task status transition is invalid."""
    if not can_transition(current, target):
        raise TransitionError(f"Task status cannot transition from {current!s} to {target!s}")


def can_transition_phase(current: LifecyclePhase, target: LifecyclePhase) -> bool:
    """Return whether a lifecycle phase transition is allowed."""
    return current == target or target in PHASE_TRANSITIONS[current]


def require_phase_transition(current: LifecyclePhase, target: LifecyclePhase) -> None:
    """Raise a clear error if a lifecycle phase transition is invalid."""
    if not can_transition_phase(current, target):
        raise TransitionError(f"Lifecycle cannot transition from {current!s} to {target!s}")


def normalize_completion_status(value: str | CompletionStatus) -> CompletionStatus:
    """Normalize the legacy ``failure`` spelling to canonical ``failed``."""
    if value == "failure":
        return CompletionStatus.FAILED
    return CompletionStatus(value)
