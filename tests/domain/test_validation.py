"""Pure task validation tests."""

import unittest

from alfred.domain.constants import ExecutionMode, PlanningState, WorktreeMode
from alfred.domain.models import Task
from alfred.domain.validation import require_valid_task, validate_task


def valid_task() -> Task:
    return Task(
        task_number=7,
        title="Example",
        description="Implement an example",
        branch_name="feature/example",
    )


class TaskValidationTests(unittest.TestCase):
    def test_valid_task_has_no_errors(self) -> None:
        self.assertEqual(validate_task(valid_task()), [])

    def test_reports_all_independent_errors(self) -> None:
        task = Task(task_number=0, title="", description="", priority="urgent")
        errors = validate_task(task)
        self.assertIn("task_number must be positive", errors)
        self.assertIn("title is required", errors)
        self.assertIn("description is required", errors)
        self.assertTrue(any(error.startswith("priority must") for error in errors))
        self.assertIn("branch_name is required when worktree_mode is enabled", errors)

    def test_plan_execution_requires_planning_state(self) -> None:
        task = valid_task()
        task.execution_mode = ExecutionMode.PLAN_EXECUTION
        self.assertIn("plan-execution requires a planning state", validate_task(task))
        task.planning_state = PlanningState.PENDING
        self.assertEqual(validate_task(task), [])

    def test_disabled_worktrees_do_not_require_branch(self) -> None:
        task = valid_task()
        task.worktree_mode = WorktreeMode.DISABLED
        task.branch_name = ""
        self.assertEqual(validate_task(task), [])

    def test_require_valid_task_raises_joined_message(self) -> None:
        task = valid_task()
        task.dependencies = [7]
        with self.assertRaisesRegex(ValueError, "cannot depend on itself"):
            require_valid_task(task)


if __name__ == "__main__":
    unittest.main()
