"""Request bodies for the UI API, with defaults that match the Alfred CLI."""

from typing import Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "plan_completed",
    "plan_approved",
    "progress",
    "coding",
    "execution_started",
    "blocked",
    "unblocked",
    "review_requested",
    "fixing",
]
CompletionResult = Literal["success", "failed", "blocked"]


class ActorBody(BaseModel):
    """Any action attributed to an actor (``manager`` unless changed)."""

    actor: str = "manager"


class TaskCreateBody(ActorBody):
    """Fields of ``alfred task create``."""

    task: int
    title: str
    description: str
    category: str = "General"
    priority: str = "P2"
    deadline: str = ""
    notes: str = ""
    assign: str = ""
    dispatch: Literal["auto", "queued"] = "auto"
    branch: str = ""
    mode: Literal["direct", "plan-execution"] = "direct"
    worktree: Literal["enabled", "disabled"] = "enabled"
    repos: list[str] = Field(default_factory=list)
    dependencies: list[int] = Field(default_factory=list)


class TaskUpdateBody(ActorBody):
    """Fields of ``alfred task update``; omitted fields stay unchanged."""

    title: str | None = None
    description: str | None = None
    category: str | None = None
    priority: str | None = None
    deadline: str | None = None
    notes: str | None = None
    branch: str | None = None
    mode: Literal["direct", "plan-execution"] | None = None
    worktree: Literal["enabled", "disabled"] | None = None
    repos: list[str] | None = None
    dependencies: list[int] | None = None


class NoteBody(ActorBody):
    """A task action with an optional note."""

    note: str = ""


class RequiredNoteBody(ActorBody):
    """A task action whose note is required."""

    note: str


class BlockBody(ActorBody):
    """``alfred task block``."""

    reason: str


class ReviewBody(ActorBody):
    """``alfred task review``."""

    decision: Literal["approved", "changes_requested"]
    note: str


class MergeBody(ActorBody):
    """``alfred task merge``."""

    mr: str = ""


class DeployBody(ActorBody):
    """``alfred task deploy``."""

    env: str = "production"
    result: str = "passed"


class AssignBody(ActorBody):
    """``alfred agent assign``."""

    agent: str
    dispatch: Literal["auto", "queued"] | None = None


class ReassignBody(ActorBody):
    """``alfred agent reassign``."""

    agent: str
    mode: Literal["soft-switch", "stop-and-switch"] = "soft-switch"


class TriggerBody(ActorBody):
    """``alfred run trigger``."""

    tasks: list[int] = Field(default_factory=list)
    all: bool = False
    parallel: int = 1


class StopBody(ActorBody):
    """``alfred run stop``."""

    reason: str = "manual stop"
    cleanup: bool = False
    force: bool = False


class ContinueBody(ActorBody):
    """``alfred run continue``."""

    note: str = ""


class EventBody(BaseModel):
    """``alfred run event``."""

    type: EventType
    note: str = ""
    actor: str = "manager"
    override: bool = True


class CompleteBody(BaseModel):
    """``alfred run complete``."""

    result: CompletionResult
    note: str
    actor: str = "manager"
    override: bool = True


class WorktreeCreateBody(BaseModel):
    """``alfred worktree create``; an empty list uses the task's repositories."""

    repos: list[str] = Field(default_factory=list)


class CommitBody(BaseModel):
    """``alfred worktree commit``."""

    type: str
    message: str
    repo: str = ""


class PushBody(BaseModel):
    """``alfred worktree push``."""

    repo: str = ""


class RemoveWorktreesBody(ActorBody):
    """Remove a finished task's worktrees; dirty trees need ``force``."""

    force: bool = False


class SyncApplyBody(ActorBody):
    """``alfred sync apply``; no task means every task."""

    task: int | None = None


class KnowledgeBody(BaseModel):
    """``alfred knowledge add``."""

    task: int
    category: Literal["patterns", "decisions", "entities", "issues", "conventions"]
    title: str
    content: str
    agent: str = ""
    files: list[str] = Field(default_factory=list)
    modules: list[str] = Field(default_factory=list)


class LearnerStartBody(BaseModel):
    """``alfred learner start``."""

    agent: str = ""


class NotificationAckBody(BaseModel):
    """``alfred notifications ack``."""

    task: int


class SendTextBody(BaseModel):
    """Paste a message into a session and optionally press Enter."""

    text: str = ""
    submit: bool = True
    bracketed: bool = True
    record: bool = True
    actor: str = "manager"


class SendKeysBody(BaseModel):
    """Send named keys (for example Enter, Escape, C-c, y) to a session."""

    keys: list[str]


class KillSessionBody(ActorBody):
    """Stop a tmux session that no active run owns."""


class CaptureBody(BaseModel):
    """Save the complete scrollback of a session."""

    reason: str = "manual"


class InitBody(BaseModel):
    """``alfred init``."""

    root: str
    force: bool = False


class OpenWorkspaceBody(BaseModel):
    """Open another workspace by its configuration path or project root."""

    path: str
    validate_config: bool = True


class ConfigTextBody(BaseModel):
    """Configuration TOML text to validate or save."""

    text: str


class RepositorySnippetBody(BaseModel):
    """Values for a new ``[[repositories]]`` block."""

    name: str
    path: str
    default_branch: str = "main"
    remote: str = "origin"
    selected_by_default: bool = False


class AgentSnippetBody(BaseModel):
    """Values for a new ``[agents.<alias>]`` block."""

    alias: str
    runtime_target: str = ""
    direct: list[str] = Field(default_factory=list)
    plan: list[str] = Field(default_factory=list)
    execution: list[str] = Field(default_factory=list)


class MigrateBody(BaseModel):
    """``alfred migrate``."""

    source: str
    migration_directory: str = ""


class LoginBody(BaseModel):
    """Access token supplied by the operator."""

    token: str
