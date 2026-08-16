"""Run and worktree command handler tests."""

from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import unittest

from alfred.adapters.git.commits import CommitResult, PushResult
from alfred.adapters.git.worktrees import WorktreeStatus
from alfred.cli.run_commands import handle_run, handle_worktree
from alfred.domain.constants import RunStatus, TaskStatus
from alfred.domain.models import AgentRun, Task


class FakeRuns:
    def __init__(self) -> None:
        self.run = AgentRun("run-1", 7, "builder", "local", RunStatus.RUNNING)

    def trigger(self, task_numbers, *, parallel, actor):
        return (self.run,)

    def list(self):
        return (self.run,)


class FakeWorktrees:
    def create(self, task, repositories):
        return {"app": Path("/tmp/worktrees/app")}

    def statuses(self, task_number):
        return (WorktreeStatus("app", Path("/tmp/worktrees/app"), "feature/x", ""),)


class FakeCommits:
    def commit(self, task_number, commit_type, message, *, repository=None):
        return (CommitResult("app", "abc123", "[PATCH] Small change"),)

    def push(self, task_number, *, repository=None):
        return (PushResult("app", "origin", "feature/x"),)


class RunCommandTests(unittest.TestCase):
    def output(self, callback, args, services) -> tuple[int, str]:
        stream = StringIO()
        with redirect_stdout(stream):
            code = callback(args, services)
        return code, stream.getvalue()

    def test_trigger_and_list_render_runs(self) -> None:
        task = Task(7, "Example", "Details", status=TaskStatus.QUEUED)
        services = SimpleNamespace(
            runs=FakeRuns(),
            tasks=SimpleNamespace(list=lambda: (task,)),
        )
        trigger = Namespace(
            action="trigger",
            all=True,
            tasks="",
            parallel=1,
            actor="manager",
        )
        self.assertIn("run-1", self.output(handle_run, trigger, services)[1])
        listing = Namespace(action="list", status="running")
        self.assertIn("task=7", self.output(handle_run, listing, services)[1])

    def test_worktree_status_commit_and_push_render_results(self) -> None:
        services = SimpleNamespace(
            tasks=SimpleNamespace(require=lambda number: Task(number, "Example", "Details")),
            worktrees=FakeWorktrees(),
            commits=FakeCommits(),
        )
        status = Namespace(action="status", task=7)
        self.assertIn("clean", self.output(handle_worktree, status, services)[1])
        commit = Namespace(
            action="commit",
            task=7,
            type="PATCH",
            message="Small change",
            repo=None,
        )
        self.assertIn("abc123", self.output(handle_worktree, commit, services)[1])
        push = Namespace(action="push", task=7, repo=None)
        self.assertIn("origin", self.output(handle_worktree, push, services)[1])


if __name__ == "__main__":
    unittest.main()
