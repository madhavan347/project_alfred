"""Pure validation rules for task details."""

from alfred.domain.constants import PRIORITIES, ExecutionMode, PlanningState, WorktreeMode
from alfred.domain.models import Task


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
