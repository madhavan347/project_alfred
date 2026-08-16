"""Support command handler tests."""

import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace

from alfred.cli.support_commands import handle_notifications, handle_report, handle_sync
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


if __name__ == "__main__":
    unittest.main()
