"""Bracket-tag commit adapter integration tests."""

from pathlib import Path
from types import MappingProxyType
import tempfile
import unittest

from alfred.adapters.git import GitCommitManager, GitWorktreeManager
from alfred.adapters.process import SubprocessRunner
from alfred.config.models import CommitConfig, RepositoryConfig, WorkspaceConfig
from alfred.domain.models import Task


class GitCommitManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repository = self.root / "api"
        self.repository.mkdir()
        self.runner = SubprocessRunner()
        self.runner.run(("git", "init", "-b", "main"), cwd=self.repository)
        self.runner.run(("git", "config", "user.name", "Test"), cwd=self.repository)
        self.runner.run(
            ("git", "config", "user.email", "test@example.invalid"), cwd=self.repository
        )
        self.repository.joinpath("README.md").write_text("example\n")
        self.runner.run(("git", "add", "README.md"), cwd=self.repository)
        self.runner.run(("git", "commit", "-m", "initial"), cwd=self.repository)
        self.workspace = WorkspaceConfig(
            root=self.root,
            repositories=(
                RepositoryConfig(
                    name="api",
                    path=self.repository,
                    selected_by_default=True,
                ),
            ),
        )
        self.worktrees = GitWorktreeManager(
            self.workspace, self.root / "worktrees", self.runner
        )
        self.task = Task(
            task_number=7,
            title="Example",
            description="A task",
            branch_name="feature/task-7",
        )
        self.path = self.worktrees.create(self.task)["api"]
        self.commits = GitCommitManager(
            self.worktrees,
            self.workspace,
            CommitConfig(tags=MappingProxyType({"PATCH": "[PATCH]"})),
            self.runner,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_creates_exact_configured_commit_message(self) -> None:
        self.path.joinpath("feature.txt").write_text("implemented\n")
        result = self.commits.commit(7, "patch", "Add example behavior")
        self.assertEqual(result[0].message, "[PATCH] Add example behavior")
        log = self.runner.run(
            ("git", "log", "-1", "--format=%s"), cwd=self.path
        ).stdout.strip()
        self.assertEqual(log, "[PATCH] Add example behavior")

    def test_clean_worktree_creates_no_commit(self) -> None:
        self.assertEqual(self.commits.commit(7, "PATCH", "Nothing changed"), ())

    def test_unknown_type_is_rejected_before_staging(self) -> None:
        self.path.joinpath("feature.txt").write_text("implemented\n")
        with self.assertRaisesRegex(ValueError, "configured types: PATCH"):
            self.commits.commit(7, "OTHER", "Add example behavior")
        staged = self.runner.run(
            ("git", "diff", "--cached", "--name-only"), cwd=self.path
        ).stdout.strip()
        self.assertEqual(staged, "")

    def test_repository_filter_must_match_task_worktree(self) -> None:
        with self.assertRaisesRegex(ValueError, "no worktree"):
            self.commits.commit(7, "PATCH", "Example", repository="missing")


if __name__ == "__main__":
    unittest.main()
