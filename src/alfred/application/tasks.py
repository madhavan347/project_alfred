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
from alfred.domain.models import Task, TaskEvent
from alfred.domain.state_machine import require_phase_transition, require_transition
from alfred.domain.validation import require_valid_task
from alfred.ports.tracker import Tracker
from alfred.utils.time import Clock


class TaskService:
    """Persist validated task changes with event and tracker rollback."""

    def __init__(
        self,
        store: JsonStateStore,
        tracker: Tracker,
        clock: Clock,
        *,
        agent_aliases: Iterable[str] = (),
    ) -> None:
        self.store = store
        self.tracker = tracker
        self.clock = clock
        self.agent_aliases = frozenset(agent_aliases)

    def list(self) -> tuple[Task, ...]:
        """Return tasks ordered by task number."""
        return tuple(sorted((Task.from_dict(item) for item in self.store.tasks()), key=lambda item: item.task_number))

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
        if task.execution_mode == ExecutionMode.PLAN_EXECUTION:
            if task.planning_state == PlanningState.NOT_REQUIRED:
                task.planning_state = PlanningState.PENDING
        else:
            task.planning_state = PlanningState.NOT_REQUIRED
        if task.dispatch_mode == DispatchMode.QUEUED:
            task.status = TaskStatus.QUEUED
        timestamp = self.clock.timestamp()
        task.created_at = existing.created_at if existing else timestamp
        task.updated_at = timestamp
        require_valid_task(task)
        return self._commit(task, actor, "TASK_UPSERTED", "Task details created or updated.")

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
        if task.dispatch_mode == DispatchMode.QUEUED:
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
