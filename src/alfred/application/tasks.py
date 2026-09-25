"""Task and agent-assignment application workflows."""

from collections.abc import Iterable

from alfred.adapters.state import JsonStateStore
from alfred.domain.constants import (
    DispatchMode,
    ExecutionMode,
    LifecyclePhase,
    PlanningState,
    TaskStatus,
)
from alfred.domain.models import AgentRun, Task, TaskEvent
from alfred.domain.state_machine import (
    ACTIVE_RUN_STATUSES,
    TransitionError,
    require_phase_transition,
    require_transition,
)
from alfred.domain.validation import ref_name_problem, require_valid_task
from alfred.ports.tracker import Tracker
from alfred.utils.time import Clock

# Events that record new work or a status change and therefore require a fresh review approval.
APPROVAL_RESETTING_PREFIXES = ("RUN_", "AGENT_", "STATUS_")
APPROVAL_RESETTING_EVENTS = frozenset({"PROGRESS", "PLAN_APPROVED", "REVIEW_CHANGES_REQUESTED"})


class TaskService:
    """Persist validated task changes with event and tracker rollback."""

    def __init__(
        self,
        store: JsonStateStore,
        tracker: Tracker,
        clock: Clock,
        *,
        agent_aliases: Iterable[str] = (),
        repository_names: Iterable[str] = (),
    ) -> None:
        self.store = store
        self.tracker = tracker
        self.clock = clock
        self.agent_aliases = frozenset(agent_aliases)
        self.repository_names = frozenset(repository_names)

    def list(self) -> tuple[Task, ...]:
        """Return tasks ordered by task number."""
        return tuple(
            sorted(
                (Task.from_dict(item) for item in self.store.tasks()),
                key=lambda item: item.task_number,
            )
        )

    def get(self, task_number: int) -> Task | None:
        """Return a task by number."""
        return next((task for task in self.list() if task.task_number == task_number), None)

    def require(self, task_number: int) -> Task:
        """Return a task or raise an actionable error."""
        task = self.get(task_number)
        if task is None:
            raise ValueError(f"Task {task_number} not found")
        return task

    def upsert(self, task: Task, *, actor: str = "manager") -> Task:
        """Create or replace complete task details with compatible defaults."""
        existing = self.get(task.task_number)
        self._require_configured(task, existing)
        self._require_safe_branch(task, existing)
        if task.execution_mode == ExecutionMode.PLAN_EXECUTION:
            if task.planning_state == PlanningState.NOT_REQUIRED:
                task.planning_state = PlanningState.PENDING
        else:
            task.planning_state = PlanningState.NOT_REQUIRED
        if task.dispatch_mode == DispatchMode.QUEUED and task.status == TaskStatus.PENDING:
            # Only work that has not started becomes eligible for `run trigger --all`.
            task.status = TaskStatus.QUEUED
        timestamp = self.clock.timestamp()
        task.created_at = existing.created_at if existing else timestamp
        task.updated_at = timestamp
        require_valid_task(task)
        return self._commit(task, actor, "TASK_UPSERTED", "Task details created or updated.")

    @staticmethod
    def _require_safe_branch(task: Task, existing: Task | None) -> None:
        """Reject a newly supplied branch name that is not a valid Git branch name."""
        branch = task.branch_name
        if not branch or (existing is not None and branch == existing.branch_name):
            return
        if problem := ref_name_problem(branch):
            raise ValueError(f"branch_name {problem}: {branch!r}")

    def _require_configured(self, task: Task, existing: Task | None) -> None:
        """Reject newly supplied agent aliases or repositories that are not configured."""
        alias = task.assigned_agent_alias
        if (
            alias
            and self.agent_aliases
            and alias not in self.agent_aliases
            and (existing is None or alias != existing.assigned_agent_alias)
        ):
            available = ", ".join(sorted(self.agent_aliases))
            raise ValueError(f"Unknown agent {alias!r}; configured agents: {available}")
        previous = set(existing.target_repositories) if existing else set()
        unknown = [
            name
            for name in task.target_repositories
            if self.repository_names and name not in self.repository_names and name not in previous
        ]
        if unknown:
            available = ", ".join(sorted(self.repository_names))
            raise ValueError(
                f"Unknown repository {', '.join(map(repr, unknown))}; "
                f"configured repositories: {available}"
            )

    def assign(
        self,
        task_number: int,
        agent_alias: str,
        *,
        actor: str = "manager",
        dispatch_mode: DispatchMode | None = None,
    ) -> Task:
        """Assign a configured agent and optionally change dispatch behavior."""
        if self.agent_aliases and agent_alias not in self.agent_aliases:
            available = ", ".join(sorted(self.agent_aliases))
            raise ValueError(f"Unknown agent {agent_alias!r}; configured agents: {available}")
        task = self.require(task_number)
        old = task.assigned_agent_alias or "unassigned"
        task.assigned_agent_alias = agent_alias
        if dispatch_mode is not None:
            task.dispatch_mode = dispatch_mode
        if task.dispatch_mode == DispatchMode.QUEUED and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.QUEUED
        task.updated_at = self.clock.timestamp()
        return self._commit(
            task,
            actor,
            "AGENT_ASSIGNED",
            f"Agent changed from {old} to {agent_alias}.",
        )

    def update_status(
        self,
        task_number: int,
        target: TaskStatus,
        note: str,
        *,
        actor: str = "manager",
    ) -> Task:
        """Apply one valid status transition."""
        task = self.require(task_number)
        require_transition(task.status, target)
        task.status = target
        if note:
            task.notes = note
        task.updated_at = self.clock.timestamp()
        event_type = f"STATUS_{target.value.upper().replace(' ', '_')}"
        return self._commit(task, actor, event_type, note or f"Status changed to {target}.")

    def progress(self, task_number: int, note: str, *, actor: str = "manager") -> Task:
        """Record progress and move an active task to In Progress."""
        task = self.require(task_number)
        if task.status != TaskStatus.IN_PROGRESS:
            require_transition(task.status, TaskStatus.IN_PROGRESS)
            task.status = TaskStatus.IN_PROGRESS
        task.notes = note
        task.updated_at = self.clock.timestamp()
        return self._commit(task, actor, "PROGRESS", note)

    def block(self, task_number: int, reason: str, *, actor: str = "manager") -> Task:
        """Block a task with a required reason."""
        if not reason.strip():
            raise ValueError("Block reason is required")
        return self.update_status(task_number, TaskStatus.BLOCKED, reason, actor=actor)

    def unblock(self, task_number: int, note: str = "", *, actor: str = "manager") -> Task:
        """Return a blocked task to Pending."""
        return self.update_status(
            task_number,
            TaskStatus.PENDING,
            note or "Blocker resolved.",
            actor=actor,
        )

    def review(
        self,
        task_number: int,
        decision: str,
        note: str,
        *,
        actor: str = "manager",
    ) -> Task:
        """Record an approved or changes-requested review decision."""
        if decision not in {"approved", "changes_requested"}:
            raise ValueError("Review decision must be approved or changes_requested")
        task = self.require(task_number)
        target = TaskStatus.IN_REVIEW if decision == "approved" else TaskStatus.IN_PROGRESS
        if task.status != target:
            require_transition(task.status, target)
        task.status = target
        task.notes = note
        task.updated_at = self.clock.timestamp()
        return self._commit(task, actor, f"REVIEW_{decision.upper()}", note)

    def merge(self, task_number: int, merge_request: str = "", *, actor: str = "manager") -> Task:
        """Record the merge of an approved task and move it to testing and deployment."""
        task = self.require(task_number)
        self._require_no_active_run(task_number, "merge")
        if task.status != TaskStatus.IN_REVIEW or not self._approved_since_last_work(task_number):
            raise TransitionError(
                f"Task {task_number} must be approved with 'task review --decision approved' "
                f"after its latest work before merge; status is {task.status}"
            )
        require_phase_transition(task.lifecycle_phase, LifecyclePhase.TESTING_DEPLOYMENT)
        self.record(
            task,
            "MERGED",
            f"Merge request: {merge_request}" if merge_request else "Changes merged.",
            actor=actor,
        )
        return self.update_phase(
            task_number,
            LifecyclePhase.TESTING_DEPLOYMENT,
            "Moved to testing and deployment.",
            actor=actor,
        )

    def deploy(
        self,
        task_number: int,
        environment: str,
        result: str,
        *,
        actor: str = "manager",
    ) -> Task:
        """Record a deployment of a merged task and mark it completed."""
        task = self.require(task_number)
        self._require_no_active_run(task_number, "deploy")
        if task.lifecycle_phase != LifecyclePhase.TESTING_DEPLOYMENT:
            raise TransitionError(
                f"Task {task_number} must be merged (testing_deployment) before deploy; "
                f"phase is {task.lifecycle_phase}"
            )
        return self.update_status(
            task_number,
            TaskStatus.COMPLETED,
            f"Deploy {environment}: {result}",
            actor=actor,
        )

    def update_phase(
        self,
        task_number: int,
        phase: LifecyclePhase,
        note: str = "",
        *,
        actor: str = "manager",
    ) -> Task:
        """Move a task through deployment, archive, or consolidation phases."""
        task = self.require(task_number)
        self._require_no_active_run(task_number, phase.value)
        require_phase_transition(task.lifecycle_phase, phase)
        task.lifecycle_phase = phase
        if phase == LifecyclePhase.ARCHIVED:
            task.status = TaskStatus.COMPLETED
        elif phase == LifecyclePhase.CONSOLIDATED:
            task.status = TaskStatus.CONSOLIDATED
        if note:
            task.notes = note
        task.updated_at = self.clock.timestamp()
        return self._commit(
            task,
            actor,
            f"PHASE_{phase.value.upper()}",
            note or f"Lifecycle moved to {phase.value}.",
        )

    def _approved_since_last_work(self, task_number: int) -> bool:
        """Return whether a human approval follows the task's most recent work or status change.

        An agent's successful completion also sets "MR in Review", so the status alone does not
        show that a reviewer approved the result.
        """
        for event in reversed(self.events(task_number)):
            if event.event_type == "REVIEW_APPROVED":
                return True
            if event.event_type in APPROVAL_RESETTING_EVENTS or event.event_type.startswith(
                APPROVAL_RESETTING_PREFIXES
            ):
                return False
        return False

    def _require_no_active_run(self, task_number: int, action: str) -> None:
        """Keep a live agent run from being orphaned by a delivery or terminal transition."""
        active = [
            run
            for run in (AgentRun.from_dict(item) for item in self.store.runs())
            if run.task_number == task_number and run.run_status in ACTIVE_RUN_STATUSES
        ]
        if active:
            raise TransitionError(
                f"Task {task_number} has an active run ({active[-1].run_status}); "
                f"complete or stop it before {action}"
            )

    def events(self, task_number: int) -> tuple[TaskEvent, ...]:
        """Return persisted events for one task."""
        return tuple(
            TaskEvent(
                timestamp=item["timestamp"],
                actor=item["actor"],
                event_type=item["event_type"],
                details=item["details"],
            )
            for item in self.store.events()
            if item.get("task_number") == task_number
        )

    def record(
        self,
        task: Task,
        event_type: str,
        details: str,
        *,
        actor: str = "manager",
    ) -> Task:
        """Persist a task already changed by a coordinating application service."""
        task.updated_at = self.clock.timestamp()
        require_valid_task(task)
        return self._commit(task, actor, event_type, details)

    def _commit(
        self,
        task: Task,
        actor: str,
        event_type: str,
        details: str,
    ) -> Task:
        tasks_before = self.store.tasks()
        events_before = self.store.events()
        tasks = [item for item in tasks_before if item.get("task_number") != task.task_number]
        tasks.append(task.to_dict())
        event = TaskEvent(self.clock.timestamp(), actor, event_type, details)
        event_record = {"task_number": task.task_number, **event.to_dict()}
        try:
            self.store.save_tasks(tasks)
            self.store.save_events([*events_before, event_record])
            self.tracker.sync(task, event)
        except Exception:
            self.store.save_tasks(tasks_before)
            self.store.save_events(events_before)
            raise
        return task
