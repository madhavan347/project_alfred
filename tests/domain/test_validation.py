"""Pure task validation tests."""

import unittest

from alfred.domain.constants import ExecutionMode, PlanningState, WorktreeMode
from alfred.domain.models import Task
from alfred.domain.validation import ref_name_problem, require_valid_task, validate_task


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


class RefNameTests(unittest.TestCase):
    def test_accepts_ordinary_branch_and_remote_names(self) -> None:
        for name in ("main", "trunk", "origin", "feature/health", "release-1.2", "fix_7", "a/b/c"):
            with self.subTest(name=name):
                self.assertIsNone(ref_name_problem(name))

    def test_rejects_each_unsafe_form(self) -> None:
        cases = {
            "": "must not be empty",
            "-x": "must not start with '-'",
            "--upload-pack=evil": "must not start with '-'",
            "@": "must not be '@'",
            "a b": "must not contain spaces",
            "a\tb": "must not contain spaces",
            "a\x7fb": "must not contain spaces",
            "a~1": "must not contain spaces",
            "a^": "must not contain spaces",
            "a:b": "must not contain spaces",
            "a?b": "must not contain spaces",
            "a*b": "must not contain spaces",
            "a[b": "must not contain spaces",
            "a\\b": "must not contain spaces",
            "a..b": "must not contain '..'",
            "a@{b": "must not contain '@{'",
            "a//b": "must not contain '//'",
            "/a": "must not start or end with '/'",
            "a/": "must not start or end with '/'",
            "a.": "must not end with '.'",
            ".a": "path component starting with '.'",
            "a/.b": "path component starting with '.'",
            "a.lock": "path component ending with '.lock'",
            "a.lock/b": "path component ending with '.lock'",
        }
        for name, message in cases.items():
            with self.subTest(name=name):
                problem = ref_name_problem(name)
                self.assertIsNotNone(problem)
                self.assertIn(message, problem or "")


if __name__ == "__main__":
    unittest.main()
