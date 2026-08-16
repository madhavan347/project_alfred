"""Git worktree lifecycle integration tests."""

import tempfile
import unittest
from pathlib import Path

from alfred.adapters.git import GitWorktreeManager
from alfred.adapters.process import ProcessError, SubprocessRunner
from alfred.config.models import RepositoryConfig, WorkspaceConfig
from alfred.domain.models import Task


class GitWorktreeManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repository = self.root / "api"
        self.repository.mkdir()
        self.runner = SubprocessRunner()
        self.runner.run(("git", "init", "-b", "main"), cwd=self.repository)
        self.repository.joinpath("README.md").write_text("example\n")
        self.runner.run(("git", "add", "README.md"), cwd=self.repository)
        self.runner.run(
            (
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-m",
                "initial",
            ),
            cwd=self.repository,
        )
        workspace = WorkspaceConfig(
            root=self.root,
            repositories=(
                RepositoryConfig(
                    name="api",
                    path=self.repository,
                    default_branch="main",
                    selected_by_default=True,
                ),
            ),
        )
        self.manager = GitWorktreeManager(workspace, self.root / "worktrees", self.runner)
        self.task = Task(
            task_number=7,
            title="Example",
            description="A task",
            branch_name="feature/task-7",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_create_and_reuse_worktree(self) -> None:
        first = self.manager.create(self.task)
        second = self.manager.create(self.task)
        self.assertEqual(first, second)
        self.assertEqual(self.manager.statuses(7)[0].branch, "feature/task-7")

    def test_cleanup_unregisters_clean_worktree(self) -> None:
        path = self.manager.create(self.task)["api"]
        self.assertEqual(self.manager.cleanup(7), (path,))
        self.assertFalse(path.exists())

    def test_dirty_cleanup_requires_explicit_force(self) -> None:
        path = self.manager.create(self.task)["api"]
        path.joinpath("untracked.txt").write_text("dirty\n")
        with self.assertRaises(ProcessError):
            self.manager.cleanup(7)
        self.assertTrue(path.exists())
        self.assertEqual(self.manager.cleanup(7, force=True), (path,))

    def test_missing_repository_is_rejected(self) -> None:
        self.manager.workspace.repositories[0].path.joinpath(".git").rename(
            self.repository / "git-metadata"
        )
        with self.assertRaisesRegex(ValueError, "missing or invalid"):
            self.manager.create(self.task)

    def test_repository_names_cannot_escape_worktree_root(self) -> None:
        with self.assertRaisesRegex(ValueError, "Repository name"):
            RepositoryConfig(name="../outside", path=self.repository)


if __name__ == "__main__":
    unittest.main()
