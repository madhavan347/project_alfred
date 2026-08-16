"""Coordinator and learner command handler tests."""

import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace

from alfred.application.coordinator import CoordinatorCycle
from alfred.application.learner import LearnerStatus
from alfred.cli.daemon_commands import handle_coordinator, handle_learner


class FakeSessions:
    def __init__(self) -> None:
        self.names: set[str] = set()

    def available(self) -> bool:
        return True

    def exists(self, name: str) -> bool:
        return name in self.names

    def create(self, name, workdir, command) -> None:
        self.names.add(name)

    def stop(self, name: str) -> None:
        self.names.discard(name)


class FakeLearner:
    def __init__(self) -> None:
        self.running = False
        self.alias = ""

    def start(self, alias: str) -> bool:
        self.running = True
        self.alias = alias
        return True

    def stop(self) -> bool:
        previous = self.running
        self.running = False
        return previous

    def status(self) -> LearnerStatus:
        return LearnerStatus(self.running, "alfred-learner", self.alias)


class DaemonCommandTests(unittest.TestCase):
    def output(self, callback, args, services) -> str:
        stream = StringIO()
        with redirect_stdout(stream):
            self.assertEqual(callback(args, services), 0)
        return stream.getvalue()

    def services(self):
        return SimpleNamespace(
            config=SimpleNamespace(
                runtime=SimpleNamespace(session_prefix="alfred-task"),
                config_path="/tmp/config.toml",
                workspace=SimpleNamespace(root="/tmp"),
                agents={"builder": object()},
            ),
            sessions=FakeSessions(),
            coordinator=SimpleNamespace(process_once=lambda: CoordinatorCycle(processed=2)),
            learner=FakeLearner(),
        )

    def test_coordinator_start_status_stop(self) -> None:
        services = self.services()
        self.assertIn(
            "started",
            self.output(handle_coordinator, Namespace(action="start"), services),
        )
        self.assertIn(
            "running",
            self.output(handle_coordinator, Namespace(action="status"), services),
        )
        self.assertIn(
            "stopped",
            self.output(handle_coordinator, Namespace(action="stop"), services),
        )

    def test_coordinator_once_and_learner_lifecycle(self) -> None:
        services = self.services()
        self.assertIn(
            "Processed=2",
            self.output(handle_coordinator, Namespace(action="once"), services),
        )
        self.assertIn(
            "started",
            self.output(
                handle_learner,
                Namespace(action="start", agent="builder"),
                services,
            ),
        )
        self.assertIn(
            "running",
            self.output(handle_learner, Namespace(action="status"), services),
        )


if __name__ == "__main__":
    unittest.main()
