"""Pure validation rules for task details and Git names."""

import re

from alfred.domain.constants import PRIORITIES, ExecutionMode, PlanningState, WorktreeMode
from alfred.domain.models import Task

_FORBIDDEN_REF_CHARACTERS = re.compile(r"[\x00-\x20\x7f~^:?*\[\\]")


def ref_name_problem(value: str) -> str | None:
    """Return why ``value`` is not a safe Git branch or remote name, or ``None`` if it is.

    The rules follow ``git check-ref-format --branch`` and also reject a leading hyphen, so a
    configured or user-supplied name can never be read by Git as a command-line option.
    """
    if not value:
        return "must not be empty"
    if value.startswith("-"):
        return "must not start with '-'"
    if value == "@":
        return "must not be '@'"
    if _FORBIDDEN_REF_CHARACTERS.search(value):
        return "must not contain spaces, control characters, or any of ~ ^ : ? * [ \\"
    for sequence in ("..", "@{", "//"):
        if sequence in value:
            return f"must not contain '{sequence}'"
    if value.startswith("/") or value.endswith("/"):
        return "must not start or end with '/'"
    if value.endswith("."):
        return "must not end with '.'"
    for component in value.split("/"):
        if component.startswith("."):
            return "must not have a path component starting with '.'"
        if component.endswith(".lock"):
            return "must not have a path component ending with '.lock'"
    return None


def validate_task(task: Task) -> list[str]:
    """Return all actionable task validation errors."""
    errors: list[str] = []
    if task.task_number <= 0:
        errors.append("task_number must be positive")
    if not task.title.strip():
        errors.append("title is required")
    if not task.description.strip():
        errors.append("description is required")
    if task.priority not in PRIORITIES:
        errors.append(f"priority must be one of: {', '.join(sorted(PRIORITIES))}")
    if task.worktree_mode == WorktreeMode.ENABLED and not task.branch_name.strip():
        errors.append("branch_name is required when worktree_mode is enabled")
    if (
        task.execution_mode == ExecutionMode.DIRECT
        and task.planning_state != PlanningState.NOT_REQUIRED
    ):
        errors.append("direct execution requires planning_state=not_required")
    if (
        task.execution_mode == ExecutionMode.PLAN_EXECUTION
        and task.planning_state == PlanningState.NOT_REQUIRED
    ):
        errors.append("plan-execution requires a planning state")
    if task.task_number in task.dependencies:
        errors.append("a task cannot depend on itself")
    if len(task.dependencies) != len(set(task.dependencies)):
        errors.append("dependencies must be unique")
    if len(task.target_repositories) != len(set(task.target_repositories)):
        errors.append("target_repositories must be unique")
    return errors


def require_valid_task(task: Task) -> None:
    """Raise one error containing every failed task invariant."""
    errors = validate_task(task)
    if errors:
        raise ValueError("; ".join(errors))
