"""Configurable commit and explicit push operations for task worktrees."""

from dataclasses import dataclass

from alfred.adapters.git.worktrees import GitWorktreeManager, WorktreeStatus
from alfred.config.models import CommitConfig, WorkspaceConfig
from alfred.ports.process import ProcessRunner


@dataclass(frozen=True, slots=True)
class CommitResult:
    """One commit created in a task worktree."""

    repository: str
    revision: str
    message: str


@dataclass(frozen=True, slots=True)
class PushResult:
    """One branch explicitly pushed to a configured remote."""

    repository: str
    remote: str
    branch: str


class GitCommitManager:
    """Create configured bracket-tag commits and explicit branch pushes."""

    def __init__(
        self,
        worktrees: GitWorktreeManager,
        workspace: WorkspaceConfig,
        commits: CommitConfig,
        runner: ProcessRunner,
    ) -> None:
        self.worktrees = worktrees
        self.workspace = workspace
        self.commits = commits
        self.runner = runner

    def commit(
        self,
        task_number: int,
        commit_type: str,
        message: str,
        *,
        repository: str | None = None,
    ) -> tuple[CommitResult, ...]:
        """Stage and commit dirty selected task worktrees."""
        normalized_type = commit_type.upper().strip()
        tag = self.commits.tags.get(normalized_type)
        if tag is None:
            valid = ", ".join(sorted(self.commits.tags))
            raise ValueError(f"Unknown commit type {commit_type!r}; configured types: {valid}")
        summary = message.strip()
        if not summary:
            raise ValueError("Commit message cannot be empty")
        full_message = f"{tag} {summary}"

        results: list[CommitResult] = []
        for status in self._selected_statuses(task_number, repository):
            if not status.changes:
                continue
            self.runner.run(("git", "add", "-A"), cwd=status.path)
            self.runner.run(("git", "commit", "-m", full_message), cwd=status.path)
            revision = self.runner.run(
                ("git", "rev-parse", "--short", "HEAD"), cwd=status.path
            ).stdout.strip()
            results.append(
                CommitResult(
                    repository=status.repository,
                    revision=revision,
                    message=full_message,
                )
            )
        return tuple(results)

    def push(
        self,
        task_number: int,
        *,
        repository: str | None = None,
    ) -> tuple[PushResult, ...]:
        """Push selected task branches to their explicitly configured remotes."""
        results: list[PushResult] = []
        for status in self._selected_statuses(task_number, repository):
            config = self.workspace.repository(status.repository)
            self.runner.run(
                ("git", "push", config.remote, status.branch),
                cwd=status.path,
            )
            results.append(
                PushResult(
                    repository=status.repository,
                    remote=config.remote,
                    branch=status.branch,
                )
            )
        return tuple(results)

    def _selected_statuses(
        self,
        task_number: int,
        repository: str | None,
    ) -> tuple[WorktreeStatus, ...]:
        statuses = self.worktrees.statuses(task_number)
        if repository is None:
            return statuses
        selected = tuple(status for status in statuses if status.repository == repository)
        if not selected:
            raise ValueError(f"Task {task_number} has no worktree for repository {repository!r}")
        return selected
