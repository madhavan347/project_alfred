"""Stable task and run vocabulary shared by Alfred workflows."""

from enum import StrEnum


class TaskStatus(StrEnum):
    PENDING = "Pending"
    QUEUED = "Queued"
    RUNNING = "Running"
    IN_PROGRESS = "In Progress"
    BLOCKED = "Blocked"
    ON_HOLD = "On Hold"
    IN_REVIEW = "MR in Review"
    COMPLETED = "Completed"
    CONSOLIDATED = "Consolidated"


class DispatchMode(StrEnum):
    AUTO = "auto"
    QUEUED = "queued"


class ExecutionMode(StrEnum):
    DIRECT = "direct"
    PLAN_EXECUTION = "plan-execution"


class WorktreeMode(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class PlanningState(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    STARTED = "started"
    APPROVED = "approved"
    COMPLETED = "completed"


class LifecyclePhase(StrEnum):
    ACTIVE = "active"
    TESTING_DEPLOYMENT = "testing_deployment"
    ARCHIVED = "archived"
    CONSOLIDATED = "consolidated"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    STOPPED = "stopped"


class CompletionStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"


class PromptPhase(StrEnum):
    PLAN = "plan"
    EXECUTION = "execution"


class KnowledgeCategory(StrEnum):
    PATTERNS = "patterns"
    DECISIONS = "decisions"
    ENTITIES = "entities"
    ISSUES = "issues"
    CONVENTIONS = "conventions"


PRIORITIES = frozenset({"P0", "P1", "P2", "P3", "P4", "P5"})
