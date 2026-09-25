"""Run orchestration across tasks, worktrees, sessions, and completion reports."""

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from alfred.adapters.completion import CompletionFileStore
from alfred.adapters.git.worktrees import WorktreeStatus
from alfred.adapters.state import JsonStateStore
from alfred.application.dispatch import AgentDispatcher, DispatchOutcome
from alfred.application.knowledge import KnowledgeService
from alfred.application.tasks import TaskService
from alfred.domain.constants import (
    CompletionStatus,
    ExecutionMode,
    PlanningState,
    PromptPhase,
    RunStatus,
    TaskStatus,
)
from alfred.domain.models import AgentRun, CompletionReport, Task
from alfred.domain.state_machine import (
    ACTIVE_RUN_STATUSES,
    COMPLETION_RUN_STATUS,
    COMPLETION_TASK_STATUS,
    can_transition,
    normalize_completion_status,
    require_transition,
)
from alfred.ports.session import SessionBackend
from alfred.utils.time import Clock


class WorktreeOperations(Protocol):
    """Worktree behavior required by run orchestration."""

    def create(
        self,
        task: Task,
        repositories: Sequence[str] | None = None,
    ) -> dict[str, Path]: ...

    def statuses(self, task_number: int) -> tuple[WorktreeStatus, ...]: ...

    def cleanup(self, task_number: int, *, force: bool = False) -> tuple[Path, ...]: ...


class RunService:
    """Coordinate bounded task dispatch and auditable run state."""

    def __init__(
        self,
        tasks: TaskService,
        store: JsonStateStore,
        worktrees: WorktreeOperations,
        dispatcher: AgentDispatcher,
        sessions: SessionBackend,
        completions: CompletionFileStore,
        knowledge: KnowledgeService,
        clock: Clock,
    ) -> None:
        self.tasks = tasks
        self.store = store
        self.worktrees = worktrees
        self.dispatcher = dispatcher
        self.sessions = sessions
        self.completions = completions
        self.knowledge = knowledge
        self.clock = clock

    def list(self, task_number: int | None = None) -> tuple[AgentRun, ...]:
        """Return persisted runs, optionally limited to one task."""
        runs = (AgentRun.from_dict(item) for item in self.store.runs())
        selected = [run for run in runs if task_number is None or run.task_number == task_number]
        return tuple(sorted(selected, key=lambda run: (run.started_at, run.run_id)))

    def trigger(
        self,
        task_numbers: Sequence[int],
        *,
        parallel: int = 1,
        actor: str = "manager",
    ) -> tuple[AgentRun, ...]:
        """Dispatch up to ``parallel`` tasks in the supplied order."""
        if parallel < 1:
            raise ValueError("parallel must be at least 1")
        return tuple(
            self._start(self.tasks.require(task_number), actor)
            for task_number in tuple(dict.fromkeys(task_numbers))[:parallel]
        )

    def continue_execution(
        self,
        task_number: int,
        note: str = "Plan approved.",
        *,
        actor: str = "manager",
    ) -> AgentRun:
        """Continue a planned task in its existing session after approval."""
        task = self.tasks.require(task_number)
        if task.execution_mode != ExecutionMode.PLAN_EXECUTION:
            raise ValueError(f"Task {task_number} does not use plan-execution mode")
        if task.planning_state != PlanningState.STARTED:
            raise ValueError(f"Task {task_number} has no plan awaiting approval")
        run = self._latest_active(task_number)
        self.dispatcher.preflight(task, PromptPhase.EXECUTION)
        task.planning_state = PlanningState.APPROVED
        task.notes = note
        paths = self.worktrees.create(task)
        outcome = self.dispatcher.dispatch(task, PromptPhase.EXECUTION, paths)
        timestamp = self.clock.timestamp()
        run.phase = PromptPhase.EXECUTION.value
        run.command_preview = outcome.command_preview
        run.worktree_paths = {name: str(path) for name, path in paths.items()}
        run.session_name = outcome.session_name
        run.session_status = "queued" if outcome.queued else "active"
        run.run_status = RunStatus.QUEUED if outcome.queued else RunStatus.RUNNING
        run.last_event_at = timestamp
        self._save_run(run)
        self._update_queue(task_number, add=outcome.queued)
        task.planning_state = PlanningState.COMPLETED
        task.status = TaskStatus.QUEUED if outcome.queued else TaskStatus.RUNNING
        self.tasks.record(task, "PLAN_APPROVED", note, actor=actor)
        return run

    def complete(
        self,
        task_number: int,
        result: str | CompletionStatus,
        summary: str,
        *,
        actor: str,
        override_actor: bool = False,
    ) -> CompletionReport:
        """Finish the active run and write a coordinator completion handoff."""
        if not summary.strip():
            raise ValueError("Completion summary is required")
        task = self.tasks.require(task_number)
        self._require_actor(task, actor, override_actor)
        status = normalize_completion_status(result)
        run = self._latest_active(task_number)
        target = COMPLETION_TASK_STATUS[status]
        require_transition(task.status, target)
        timestamp = self.clock.timestamp()
        run_status = COMPLETION_RUN_STATUS[status]
        worktrees = self.worktrees.statuses(task_number)
        report = CompletionReport(
            task_number=task_number,
            agent=task.assigned_agent_alias,
            status=status,
            summary=summary.strip(),
            repositories=tuple(item.repository for item in worktrees),
            branches={item.repository: item.branch for item in worktrees},
            knowledge_entries=self.knowledge.count_for_task(task_number),
            completed_at=timestamp,
        )
        task.status = target
        self.tasks.record(
            task,
            f"RUN_{run_status.value.upper()}",
            report.summary,
            actor=actor,
        )
        self.completions.write(report)
        # The run is marked finished last, so anyone watching run state never sees a completed run
        # whose task update or coordinator handoff has not been written yet.
        run.run_status = run_status
        run.ended_at = timestamp
        run.last_event_at = timestamp
        run.summary = report.summary
        run.session_status = "inactive"
        self._save_run(run)
        self._update_queue(task_number, add=False)
        return report

    def stop(
        self,
        task_number: int,
        note: str = "Run stopped.",
        *,
        actor: str = "manager",
        cleanup: bool = False,
        force: bool = False,
    ) -> AgentRun:
        """Stop a live run and optionally remove its worktrees."""
        task = self.tasks.require(task_number)
        run = self._latest_active(task_number)
        if cleanup and not force:
            dirty = [
                status.repository
                for status in self.worktrees.statuses(task_number)
                if status.changes.strip()
            ]
            if dirty:
                raise ValueError(
                    f"Task {task_number} worktrees have uncommitted changes: "
                    f"{', '.join(dirty)}; commit them or pass --force to discard them"
                )
        if (
            run.session_name
            and run.session_status == "active"
            and self.sessions.exists(run.session_name)
        ):
            self.sessions.stop(run.session_name)
        if cleanup:
            self.worktrees.cleanup(task_number, force=force)
        timestamp = self.clock.timestamp()
        run.run_status = RunStatus.STOPPED
        run.ended_at = timestamp
        run.last_event_at = timestamp
        run.summary = note
        run.session_status = "inactive"
        self._save_run(run)
        self._update_queue(task_number, add=False)
        # A terminal task keeps its status; stopping then only closes an orphaned run.
        if can_transition(task.status, TaskStatus.PENDING):
            task.status = TaskStatus.PENDING
            if task.execution_mode == ExecutionMode.PLAN_EXECUTION:
                task.planning_state = PlanningState.PENDING
        self.tasks.record(task, "RUN_STOPPED", note, actor=actor)
        return run

    def record_event(
        self,
        task_number: int,
        event_type: str,
        note: str = "",
        *,
        actor: str,
        override_actor: bool = False,
    ) -> Task:
        """Apply one supported agent lifecycle event."""
        task = self.tasks.require(task_number)
        self._require_actor(task, actor, override_actor)
        normalized = event_type.strip().lower()
        if normalized == "plan_approved":
            self.continue_execution(task_number, note or "Plan approved.", actor=actor)
            return self.tasks.require(task_number)
        if normalized == "blocked":
            return self.tasks.block(task_number, note or "Agent reported a blocker.", actor=actor)
        if normalized == "unblocked":
            task = self.tasks.progress(task_number, note or "Agent resumed execution.", actor=actor)
            self._resume_blocked_run(task_number)
            return task
        if normalized == "review_requested":
            task.status = TaskStatus.IN_REVIEW
        elif normalized in {"progress", "coding", "execution_started", "fixing"}:
            task.status = TaskStatus.IN_PROGRESS
        elif normalized == "plan_completed":
            if task.planning_state != PlanningState.STARTED:
                raise ValueError(f"Task {task_number} has no active planning phase")
        else:
            raise ValueError(f"Unsupported run event: {event_type}")
        return self.tasks.record(
            task,
            f"AGENT_{normalized.upper()}",
            note or normalized.replace("_", " ").title(),
            actor=actor,
        )

    def _resume_blocked_run(self, task_number: int) -> None:
        """Return a run blocked at completion to running so it is monitored again."""
        run = self.active(task_number)
        if run is None or run.run_status != RunStatus.BLOCKED:
            return
        run.run_status = RunStatus.RUNNING
        run.last_event_at = self.clock.timestamp()
        if (
            run.session_name
            and self.sessions.available()
            and self.sessions.exists(run.session_name)
        ):
            run.session_status = "active"
        self._save_run(run)

    def reopen(self, task_number: int, *, actor: str = "manager") -> AgentRun:
        """Start a new execution attempt after a previous run reached a terminal state."""
        task = self.tasks.require(task_number)
        if self.active(task_number) is not None:
            raise ValueError(f"Task {task_number} already has an active run")
        if task.execution_mode == ExecutionMode.PLAN_EXECUTION:
            task.planning_state = PlanningState.COMPLETED
        return self._start(task, actor)

    def active(self, task_number: int) -> AgentRun | None:
        """Return the latest active run for a task when one exists."""
        runs = [run for run in self.list(task_number) if run.run_status in ACTIVE_RUN_STATUSES]
        return runs[-1] if runs else None

    def session_names(self) -> tuple[str, ...]:
        """Return sessions owned by this Alfred instance."""
        return self.sessions.list(self.dispatcher.config.runtime.session_prefix)

    def _start(self, task: Task, actor: str) -> AgentRun:
        """Dispatch one task's initial phase and persist the new run."""
        # Reading runs first also rejects corrupt run state before any worktree or session exists.
        existing = self.active(task.task_number)
        if existing is not None and existing.run_status != RunStatus.QUEUED:
            raise ValueError(
                f"Task {task.task_number} already has an active run; "
                "stop it before triggering again"
            )
        # A queued run never reached its agent, so redispatch the phase it was queued for.
        phase = PromptPhase(existing.phase) if existing is not None else self._initial_phase(task)
        self.dispatcher.preflight(task, phase)
        paths = self.worktrees.create(task) if phase == PromptPhase.EXECUTION else {}
        outcome = self.dispatcher.dispatch(task, phase, paths)
        if existing is not None:
            timestamp = self.clock.timestamp()
            existing.run_status = RunStatus.STOPPED
            existing.ended_at = timestamp
            existing.last_event_at = timestamp
            existing.summary = "Superseded by a new dispatch."
            existing.session_status = "inactive"
            self._save_run(existing)
        run = self._new_run(task, phase, paths, outcome)
        self._save_run(run)
        self._update_queue(task.task_number, add=outcome.queued)
        task.status = TaskStatus.QUEUED if outcome.queued else TaskStatus.RUNNING
        if phase == PromptPhase.PLAN:
            task.planning_state = PlanningState.STARTED
        self.tasks.record(
            task,
            "RUN_QUEUED" if outcome.queued else "RUN_STARTED",
            f"{phase.value.title()} phase dispatched to {task.assigned_agent_alias}.",
            actor=actor,
        )
        return run

    def _initial_phase(self, task: Task) -> PromptPhase:
        if not task.assigned_agent_alias:
            raise ValueError(f"Task {task.task_number} must be assigned before triggering")
        if task.execution_mode == ExecutionMode.DIRECT:
            return PromptPhase.EXECUTION
        if task.planning_state == PlanningState.PENDING:
            return PromptPhase.PLAN
        if task.planning_state in {PlanningState.APPROVED, PlanningState.COMPLETED}:
            return PromptPhase.EXECUTION
        if task.planning_state == PlanningState.STARTED:
            raise ValueError(f"Task {task.task_number} is awaiting plan approval")
        raise ValueError(f"Task {task.task_number} has an invalid planning state")

    def _new_run(
        self,
        task: Task,
        phase: PromptPhase,
        paths: dict[str, Path],
        outcome: DispatchOutcome,
    ) -> AgentRun:
        timestamp = self.clock.timestamp()
        agent = self.dispatcher.config.agents[task.assigned_agent_alias]
        return AgentRun(
            run_id=uuid4().hex,
            task_number=task.task_number,
            agent_alias=task.assigned_agent_alias,
            runtime_target=agent.runtime_target,
            run_status=RunStatus.QUEUED if outcome.queued else RunStatus.RUNNING,
            started_at=timestamp,
            phase=phase.value,
            command_preview=outcome.command_preview,
            worktree_paths={name: str(path) for name, path in paths.items()},
            session_name=outcome.session_name,
            session_status="queued" if outcome.queued else "active",
            last_event_at=timestamp,
        )

    def _latest_active(self, task_number: int) -> AgentRun:
        run = self.active(task_number)
        if run is None:
            raise ValueError(f"Task {task_number} has no active run")
        return run

    def _save_run(self, run: AgentRun) -> None:
        records = [item for item in self.store.runs() if item.get("run_id") != run.run_id]
        records.append(run.to_dict())
        self.store.save_runs(records)

    def _update_queue(self, task_number: int, *, add: bool) -> None:
        queue = [item for item in self.store.queue() if item != task_number]
        if add:
            queue.append(task_number)
        self.store.save_queue(queue)

    @staticmethod
    def _require_actor(task: Task, actor: str, override: bool) -> None:
        expected = f"agent:{task.assigned_agent_alias}"
        if not override and actor != expected:
            raise PermissionError(
                f"Task {task.task_number} run updates require actor {expected!r}; "
                "a manager may pass --override-manager"
            )
