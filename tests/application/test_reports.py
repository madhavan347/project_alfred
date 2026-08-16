"""Task reporting projection tests."""

import unittest

from alfred.application.reports import dependencies, risks, today, velocity
from alfred.domain.constants import TaskStatus
from alfred.domain.models import Task


def task(number: int, **changes: object) -> Task:
    value = Task(number, f"Task {number}", "Example")
    for name, change in changes.items():
        setattr(value, name, change)
    return value


class ReportTests(unittest.TestCase):
    def test_report_projections_are_filtered_and_ordered(self) -> None:
        tasks = (
            task(3, status=TaskStatus.COMPLETED),
            task(2, status=TaskStatus.BLOCKED),
            task(1, priority="P0", dependencies=[3]),
        )
        self.assertEqual([item.task_number for item in today(tasks)], [1, 2])
        self.assertEqual([item.task_number for item in risks(tasks)], [1, 2])
        self.assertEqual([item.task_number for item in dependencies(tasks)], [1])
        self.assertEqual(velocity(tasks).completed, 1)
        self.assertEqual(velocity(tasks).total, 3)


if __name__ == "__main__":
    unittest.main()
