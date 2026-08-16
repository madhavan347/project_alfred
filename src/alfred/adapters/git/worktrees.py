"""Safe, configuration-driven Git worktree lifecycle operations."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from alfred.config.models import WorkspaceConfig
from alfred.domain.constants import WorktreeMode
from alfred.domain.models import Task
from alfred.ports.process import ProcessRunner


@dataclass(frozen=True, slots=True)
class WorktreeStatus:
    """Current branch and porcelain status for one task worktree."""

    repository: str
    path: Path
    branch: str
    changes: str


class GitWorktreeManager:
    """Create and remove task worktrees without hidden network operations."""

    def __init__(
        self,
        workspace: WorkspaceConfig,
        worktree_root: Path,
        runner: ProcessRunner,
    ) -> None:
        self.workspace = workspace
        self.worktree_root = worktree_root
        self.runner = runner

    def create(
        self,
        task: Task,
        repositories: Sequence[str] | None = None,
    ) -> dict[str, Path]:
        """Create or reuse configured worktrees for a task."""
        if task.worktree_mode == WorktreeMode.DISABLED:
            return {}
        if not task.branch_name.strip():
            raise ValueError("branch_name is required when worktrees are enabled")
        names = self._repository_names(task, repositories)
        created: dict[str, Path] = {}
        for name in names:
            repository = self.workspace.repository(name)
            self._require_repository(repository.path, name)
            target = self.worktree_root / f"task-{task.task_number}" / name
            if target.exists():
                branch = self._capture(("git", "branch", "--show-current"), target)
                if branch != task.branch_name:
                    raise ValueError(
                        f"Existing worktree {target} uses {branch!r}, expected {task.branch_name!r}"
                    )
                created[name] = target
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            if self._branch_exists(repository.path, task.branch_name):
                self._ensure_not_diverged(
                    repository.path, repository.default_branch, task.branch_name
                )
                arguments = ("git", "worktree", "add", str(target), task.branch_name)
            else:
                self.runner.run(
                    ("git", "rev-parse", "--verify", repository.default_branch),
                    cwd=repository.path,
                )
                arguments = (
                    "git",
                    "worktree",
                    "add",
                    "-b",
                    task.branch_name,
                    str(target),
                    repository.default_branch,
                )
            self.runner.run(arguments, cwd=repository.path)
            created[name] = target
        return created

    def statuses(self, task_number: int) -> tuple[WorktreeStatus, ...]:
        """Return status for all existing worktrees of one task."""
        task_root = self.worktree_root / f"task-{task_number}"
        if not task_root.is_dir():
            return ()
        statuses: list[WorktreeStatus] = []
        for path in sorted(item for item in task_root.iterdir() if item.is_dir()):
            statuses.append(
                WorktreeStatus(
                    repository=path.name,
                    path=path,
                    branch=self._capture(("git", "branch", "--show-current"), path),
                    changes=self._capture(("git", "status", "--porcelain"), path),
                )
            )
        return tuple(statuses)

    def cleanup(self, task_number: int, *, force: bool = False) -> tuple[Path, ...]:
        """Unregister task worktrees, requiring explicit force for dirty trees."""
        removed: list[Path] = []
        for status in self.statuses(task_number):
            repository = self.workspace.repository(status.repository)
            arguments = ["git", "worktree", "remove"]
            if force:
                arguments.append("--force")
            arguments.append(str(status.path))
            self.runner.run(tuple(arguments), cwd=repository.path)
            removed.append(status.path)
        task_root = self.worktree_root / f"task-{task_number}"
        if task_root.is_dir() and not any(task_root.iterdir()):
            task_root.rmdir()
        return tuple(removed)

    def primary_workdir(self, task_number: int) -> Path:
        """Return the first task worktree or the configured workspace root."""
        statuses = self.statuses(task_number)
        return statuses[0].path if statuses else self.workspace.root

    def _repository_names(
        self,
        task: Task,
        repositories: Sequence[str] | None,
    ) -> tuple[str, ...]:
        values = repositories or task.target_repositories
        if not values:
            values = [
                repository.name
                for repository in self.workspace.repositories
                if repository.selected_by_default
            ]
        names = tuple(dict.fromkeys(values))
        if not names:
            raise ValueError("No repositories selected for the task")
        return names

    def _branch_exists(self, repository: Path, branch: str) -> bool:
        result = self.runner.run(
            ("git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"),
            cwd=repository,
            check=False,
        )
        return result.returncode == 0

    def _ensure_not_diverged(self, repository: Path, base: str, branch: str) -> None:
        counts = self._capture(
            ("git", "rev-list", "--left-right", "--count", f"{base}...{branch}"),
            repository,
        ).split()
        if len(counts) != 2:
            raise ValueError(f"Unexpected git rev-list output for {repository.name}")
        behind, ahead = (int(value) for value in counts)
        if behind > 0 and ahead > 0:
            raise ValueError(f"Branch {branch!r} has diverged from {base!r} in {repository.name}")

    def _capture(self, arguments: tuple[str, ...], cwd: Path) -> str:
        return self.runner.run(arguments, cwd=cwd).stdout.strip()

    @staticmethod
    def _require_repository(path: Path, name: str) -> None:
        if not path.is_dir() or not (path / ".git").exists():
            raise ValueError(f"Configured repository is missing or invalid: {name}: {path}")
