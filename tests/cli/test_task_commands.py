"""Task and agent CLI integration tests."""

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from alfred.cli.main import main
from alfred.config.initializer import initialize_workspace


class TaskCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config = initialize_workspace(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def call(self, *arguments: str) -> tuple[int, str]:
        output = StringIO()
        with redirect_stdout(output):
            code = main(("--config", str(self.config), *arguments))
        return code, output.getvalue()

    def test_key_errors_print_without_repr_quotes(self) -> None:
        text = self.config.read_text().replace('timezone = "UTC"', 'timezone = "Mars/Base"')
        self.config.write_text(text)
        code, output = self.call("report", "velocity")
        self.assertEqual(code, 1)
        self.assertEqual(output, "ERROR: No time zone found with key Mars/Base\n")

    def test_create_update_and_start_task(self) -> None:
        code, output = self.call(
            "task",
            "create",
            "--task",
            "7",
            "--title",
            "Example",
            "--description",
            "Details",
            "--worktree",
            "disabled",
            "--dependencies",
            "1,2",
        )
        self.assertEqual(code, 0)
        self.assertIn("Created task 7", output)
        self.assertEqual(self.call("task", "update", "--task", "7", "--title", "New")[0], 0)
        self.assertEqual(self.call("task", "start", "--task", "7")[0], 0)

    def test_agent_assignment_and_status(self) -> None:
        self.call(
            "task",
            "create",
            "--task",
            "7",
            "--title",
            "Example",
            "--description",
            "Details",
            "--worktree",
            "disabled",
        )
        self.assertEqual(self.call("agent", "assign", "--task", "7", "--to", "builder")[0], 0)
        code, output = self.call("agent", "status", "--task", "7")
        self.assertEqual(code, 0)
        self.assertIn("builder", output)

    def test_review_deploy_and_archive_lifecycle(self) -> None:
        self.call(
            "task",
            "create",
            "--task",
            "7",
            "--title",
            "Lifecycle",
            "--description",
            "Exercise lifecycle commands",
            "--worktree",
            "disabled",
        )
        commands = (
            ("start",),
            ("block", "--reason", "Waiting"),
            ("unblock", "--note", "Ready"),
            ("start",),
            ("review", "--decision", "approved", "--note", "Reviewed"),
            ("merge", "--mr", "42"),
            ("deploy", "--env", "staging", "--result", "passed"),
            ("archive", "--note", "Retained"),
        )
        for command in commands:
            with self.subTest(action=command[0]):
                self.assertEqual(self.call("task", *command, "--task", "7")[0], 0)

    def test_update_modes_and_consolidate(self) -> None:
        self.call(
            "task",
            "create",
            "--task",
            "8",
            "--title",
            "Child",
            "--description",
            "Consolidate this task",
            "--worktree",
            "disabled",
        )
        code, _ = self.call(
            "task",
            "update",
            "--task",
            "8",
            "--mode",
            "plan-execution",
            "--worktree",
            "enabled",
            "--branch",
            "feature/child",
            "--repos",
            "app,docs",
            "--dependencies",
            "1,2",
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            self.call("task", "consolidate", "--task", "8", "--note", "Parent 1")[0],
            0,
        )


if __name__ == "__main__":
    unittest.main()
