"""Support command handler tests."""

import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace

from alfred.cli.support_commands import (
    handle_knowledge,
    handle_notifications,
    handle_report,
    handle_sync,
)
from alfred.domain.constants import TaskStatus
from alfred.domain.models import Notification, Task


class SupportCommandTests(unittest.TestCase):
    def output(self, callback, args, services) -> tuple[int, str]:
        stream = StringIO()
        with redirect_stdout(stream):
            code = callback(args, services)
        return code, stream.getvalue()

    def test_sync_issues_return_nonzero(self) -> None:
        services = SimpleNamespace(sync=SimpleNamespace(validate=lambda task: ("missing",)))
        code, output = self.output(
            handle_sync,
            Namespace(action="validate", task=None),
            services,
        )
        self.assertEqual(code, 1)
        self.assertIn("missing", output)

    def test_risk_and_velocity_reports(self) -> None:
        tasks = (
            Task(1, "Risk", "Details", priority="P0"),
            Task(2, "Done", "Details", status=TaskStatus.COMPLETED),
        )
        services = SimpleNamespace(tasks=SimpleNamespace(list=lambda: tasks))
        risk = self.output(handle_report, Namespace(action="risk"), services)[1]
        speed = self.output(handle_report, Namespace(action="velocity"), services)[1]
        self.assertIn("Task 1", risk)
        self.assertIn("Completed 1/2", speed)

    def test_pending_notifications_render_summary(self) -> None:
        notification = Notification(
            "notice-1",
            "task_completed",
            7,
            "2026-08-16T10:30:00+00:00",
            {"summary": "Ready for review"},
        )
        services = SimpleNamespace(notifications=SimpleNamespace(pending=lambda: (notification,)))
        output = self.output(
            handle_notifications,
            Namespace(action=None),
            services,
        )[1]
        self.assertIn("Ready for review", output)

    def test_notifications_show_context_and_validation_issues(self) -> None:
        notification = Notification(
            "notice-2",
            "task_completed",
            7,
            "2026-08-16T10:30:00+00:00",
            {
                "summary": "Ready for review",
                "status": "success",
                "agent": "builder",
                "repositories": ["api", "web"],
                "validation_issues": ["knowledge_entries must be at least 1; got 0"],
            },
        )
        services = SimpleNamespace(notifications=SimpleNamespace(pending=lambda: (notification,)))
        output = self.output(handle_notifications, Namespace(action=None), services)[1]
        self.assertIn("  status=success agent=builder repositories=api,web\n", output)
        self.assertIn("  VALIDATION: knowledge_entries must be at least 1; got 0", output)

    def test_sync_apply_and_success(self) -> None:
        applied: list[int] = []
        tasks = (Task(1, "One", "Details"), Task(2, "Two", "Details"))
        services = SimpleNamespace(
            sync=SimpleNamespace(
                validate=lambda task: (),
                apply=lambda task: applied.append(task),
            ),
            tasks=SimpleNamespace(list=lambda: tasks),
        )
        validation = Namespace(action="validate", task=None)
        self.assertIn("passed", self.output(handle_sync, validation, services)[1])
        apply = Namespace(action="apply", task=None)
        self.assertEqual(self.output(handle_sync, apply, services)[0], 0)
        self.assertEqual(applied, [1, 2])

    def test_knowledge_add_and_empty_list(self) -> None:
        knowledge = SimpleNamespace(
            add=lambda *args, **kwargs: "/tmp/knowledge/example.md",
            list=lambda category: (),
        )
        services = SimpleNamespace(knowledge=knowledge)
        add = Namespace(
            action="add",
            task=7,
            category="patterns",
            title="Example",
            content="Details",
            agent="builder",
            files="src/app.py,tests/test_app.py",
            modules="app",
        )
        self.assertIn("example.md", self.output(handle_knowledge, add, services)[1])
        listing = Namespace(action="list", category=None)
        self.assertIn("No knowledge", self.output(handle_knowledge, listing, services)[1])

    def test_notification_ack_clear_and_empty_list(self) -> None:
        services = SimpleNamespace(
            notifications=SimpleNamespace(
                acknowledge=lambda task: 2,
                clear_acknowledged=lambda: 2,
                pending=lambda: (),
            )
        )
        self.assertIn(
            "Acknowledged 2",
            self.output(
                handle_notifications,
                Namespace(action="ack", task=7),
                services,
            )[1],
        )
        self.assertIn(
            "Cleared 2",
            self.output(
                handle_notifications,
                Namespace(action="clear"),
                services,
            )[1],
        )
        self.assertIn(
            "No pending",
            self.output(
                handle_notifications,
                Namespace(action=None),
                services,
            )[1],
        )


if __name__ == "__main__":
    unittest.main()
