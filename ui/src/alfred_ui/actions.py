"""State-changing operations that mirror Alfred's CLI handlers one-to-one.

Each function performs exactly what the corresponding ``alfred`` command does, using the same
application services, and returns a message plus structured data instead of printing. A few
operations the CLI leaves to manual tmux or Git steps (such as removing a finished task's
worktrees) are clearly marked and keep Alfred's safety rules: dirty worktrees need an explicit
force, and sessions owned by an active run must be stopped through the run.
"""

import sys
from pathlib import Path
from typing import Any

from alfred.bootstrap import AlfredServices
from alfred.config.initializer import initialize_workspace
from alfred.config.migration import migrate_legacy_runtime
from alfred.domain.constants import (
    DispatchMode,
    ExecutionMode,
    LifecyclePhase,
    PlanningState,
    RunStatus,
    TaskStatus,
    WorktreeMode,
)
from alfred.domain.models import Task

from alfred_ui import schemas
from alfred_ui.snapshot import describe_session
from alfred_ui.tmux_inspector import SessionInfo, TmuxInspector
from alfred_ui.transcripts import TranscriptStore

Result = dict[str, Any]


def _result(message: str, **data: Any) -> Result:
    return {"ok": True, "message": message, **data}


def _clean(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value.strip()]


# Tasks -------------------------------------------------------------------------------------


def create_task(services: AlfredServices, body: schemas.TaskCreateBody) -> Result:
    """``alfred task create``; refuses to silently replace an existing task."""
    if services.tasks.get(body.task) is not None:
        raise ValueError(f"Task {body.task} already exists; edit it instead of creating it again")
    mode = ExecutionMode(body.mode)
    task = Task(
        task_number=body.task,
        title=body.title,
        description=body.description,
        category=body.category,
        priority=body.priority,
        deadline=body.deadline,
        notes=body.notes,
        assigned_agent_alias=body.assign,
        dispatch_mode=DispatchMode(body.dispatch),
        execution_mode=mode,
        worktree_mode=WorktreeMode(body.worktree),
        branch_name=body.branch.strip(),
        planning_state=(
            PlanningState.PENDING
            if mode == ExecutionMode.PLAN_EXECUTION
            else PlanningState.NOT_REQUIRED
        ),
        target_repositories=_clean(body.repos),
        dependencies=list(body.dependencies),
    )
    services.tasks.upsert(task, actor=body.actor)
    return _result(f"Created task {task.task_number}", task_number=task.task_number)


def update_task(services: AlfredServices, number: int, body: schemas.TaskUpdateBody) -> Result:
    """``alfred task update``: change only the supplied fields."""
    task = services.tasks.require(number)
    for field in ("title", "description", "category", "priority", "deadline", "notes"):
        value = getattr(body, field)
        if value is not None:
            setattr(task, field, value)
    if body.branch is not None:
        task.branch_name = body.branch.strip()
    if body.mode is not None:
        task.execution_mode = ExecutionMode(body.mode)
        task.planning_state = (
            PlanningState.PENDING
            if task.execution_mode == ExecutionMode.PLAN_EXECUTION
            else PlanningState.NOT_REQUIRED
        )
    if body.worktree is not None:
        task.worktree_mode = WorktreeMode(body.worktree)
    if body.repos is not None:
        task.target_repositories = _clean(body.repos)
    if body.dependencies is not None:
        task.dependencies = list(body.dependencies)
    services.tasks.upsert(task, actor=body.actor)
    return _result(f"Updated task {task.task_number}", task_number=task.task_number)


def start_task(services: AlfredServices, number: int, body: schemas.ActorBody) -> Result:
    """``alfred task start``."""
    task = services.tasks.progress(number, "Task started.", actor=body.actor)
    return _status(task)


def progress_task(services: AlfredServices, number: int, body: schemas.RequiredNoteBody) -> Result:
    """``alfred task progress``."""
    if not body.note.strip():
        raise ValueError("A progress note is required")
    return _status(services.tasks.progress(number, body.note, actor=body.actor))


def block_task(services: AlfredServices, number: int, body: schemas.BlockBody) -> Result:
    """``alfred task block``."""
    return _status(services.tasks.block(number, body.reason, actor=body.actor))


def unblock_task(services: AlfredServices, number: int, body: schemas.NoteBody) -> Result:
    """``alfred task unblock``."""
    return _status(services.tasks.unblock(number, body.note, actor=body.actor))


def hold_task(services: AlfredServices, number: int, body: schemas.NoteBody) -> Result:
    """Put a task on hold (Alfred's ``On Hold`` status; resume with unblock)."""
    note = body.note.strip() or "Put on hold."
    return _status(services.tasks.update_status(number, TaskStatus.ON_HOLD, note, actor=body.actor))


def review_task(services: AlfredServices, number: int, body: schemas.ReviewBody) -> Result:
    """``alfred task review``."""
    return _status(services.tasks.review(number, body.decision, body.note, actor=body.actor))


def merge_task(services: AlfredServices, number: int, body: schemas.MergeBody) -> Result:
    """``alfred task merge``."""
    return _status(services.tasks.merge(number, body.mr, actor=body.actor))


def deploy_task(services: AlfredServices, number: int, body: schemas.DeployBody) -> Result:
    """``alfred task deploy``."""
    return _status(services.tasks.deploy(number, body.env, body.result, actor=body.actor))


def archive_task(services: AlfredServices, number: int, body: schemas.NoteBody) -> Result:
    """``alfred task archive``."""
    task = services.tasks.update_phase(
        number,
        LifecyclePhase.ARCHIVED,
        body.note or "Archived after completion.",
        actor=body.actor,
    )
    return _status(task)


def consolidate_task(services: AlfredServices, number: int, body: schemas.NoteBody) -> Result:
    """``alfred task consolidate``."""
    task = services.tasks.update_phase(
        number,
        LifecyclePhase.CONSOLIDATED,
        body.note or "Consolidated into a parent task.",
        actor=body.actor,
    )
    return _status(task)


def _status(task: Task) -> Result:
    return _result(f"Task {task.task_number}: {task.status}", task_number=task.task_number)


# Agents ------------------------------------------------------------------------------------


def assign_agent(services: AlfredServices, number: int, body: schemas.AssignBody) -> Result:
    """``alfred agent assign``."""
    dispatch = DispatchMode(body.dispatch) if body.dispatch else None
    task = services.tasks.assign(number, body.agent, actor=body.actor, dispatch_mode=dispatch)
    return _result(
        f"Task {task.task_number} assigned to {task.assigned_agent_alias}",
        task_number=task.task_number,
    )


def reassign_agent(services: AlfredServices, number: int, body: schemas.ReassignBody) -> Result:
    """``alfred agent reassign``, stopping the active run first for stop-and-switch."""
    stopped = False
    if body.mode == "stop-and-switch" and services.runs.active(number) is not None:
        services.runs.stop(number, "Agent reassigned.", actor=body.actor)
        stopped = True
    task = services.tasks.assign(number, body.agent, actor=body.actor)
    message = f"Task {task.task_number} assigned to {task.assigned_agent_alias}"
    if stopped:
        message = f"Stopped the active run. {message}"
    return _result(message, task_number=task.task_number, stopped=stopped)


# Runs --------------------------------------------------------------------------------------


def trigger_runs(services: AlfredServices, body: schemas.TriggerBody) -> Result:
    """``alfred run trigger``, including ``--all`` and ``--parallel``."""
    if body.all:
        numbers = [
            task.task_number for task in services.tasks.list() if task.status == TaskStatus.QUEUED
        ]
    else:
        numbers = list(body.tasks)
    if not numbers:
        raise ValueError("Choose tasks to trigger, or queue at least one task to trigger all")
    runs = services.runs.trigger(numbers, parallel=body.parallel, actor=body.actor)
    skipped = list(dict.fromkeys(numbers))[body.parallel :]
    lines = [f"Task {run.task_number}: {run.run_status}" for run in runs]
    if skipped:
        lines.append(f"Not dispatched (parallel {body.parallel}): {', '.join(map(str, skipped))}")
    return _result(
        "; ".join(lines),
        runs=[{"task_number": run.task_number, "run_id": run.run_id} for run in runs],
        skipped=skipped,
    )


def stop_run(
    services: AlfredServices,
    inspector: TmuxInspector,
    number: int,
    body: schemas.StopBody,
) -> Result:
    """``alfred run stop``; the UI first saves the session's transcript."""
    active = services.runs.active(number)
    transcript = None
    if active is not None and active.session_name:
        transcript = _safe_capture(services, inspector, active.session_name, number, "stopped")
    run = services.runs.stop(
        number,
        body.reason or "manual stop",
        actor=body.actor,
        cleanup=body.cleanup,
        force=body.force,
    )
    return _result(f"Stopped run {run.run_id} for task {number}", transcript=transcript)


def continue_run(
    services: AlfredServices,
    inspector: TmuxInspector,
    number: int,
    body: schemas.ContinueBody,
) -> Result:
    """``alfred run continue``: approve the plan and start execution in the same session.

    The planning screen is saved first, because the execution prompt is pasted into the same
    session and would otherwise push the plan out of view.
    """
    active = services.runs.active(number)
    transcript = None
    if active is not None and active.session_name and active.phase == "plan":
        transcript = _safe_capture(services, inspector, active.session_name, number, "plan")
    run = services.runs.continue_execution(number, body.note or "Plan approved.", actor=body.actor)
    return _result(
        f"Execution phase started for task {run.task_number}",
        run_id=run.run_id,
        transcript=transcript,
    )


def record_event(services: AlfredServices, number: int, body: schemas.EventBody) -> Result:
    """``alfred run event``."""
    task = services.runs.record_event(
        number, body.type, body.note, actor=body.actor, override_actor=body.override
    )
    return _result(f"Event {body.type} recorded for task {task.task_number}")


def complete_run(services: AlfredServices, number: int, body: schemas.CompleteBody) -> Result:
    """``alfred run complete``."""
    report = services.runs.complete(
        number, body.result, body.note, actor=body.actor, override_actor=body.override
    )
    return _result(f"Task {report.task_number} completion reported as {report.status}")


def reopen_run(services: AlfredServices, number: int, body: schemas.ActorBody) -> Result:
    """``alfred run reopen``."""
    run = services.runs.reopen(number, actor=body.actor)
    return _result(
        f"Task {run.task_number} session reopened",
        run_id=run.run_id,
        session_name=run.session_name,
    )


# Worktrees ---------------------------------------------------------------------------------


def create_worktrees(
    services: AlfredServices, number: int, body: schemas.WorktreeCreateBody
) -> Result:
    """``alfred worktree create``."""
    task = services.tasks.require(number)
    created = services.worktrees.create(task, _clean(body.repos))
    lines = [f"{repository}: {path}" for repository, path in created.items()]
    return _result(
        "; ".join(lines) or "No worktrees created",
        worktrees={name: str(path) for name, path in created.items()},
    )


def commit_worktrees(services: AlfredServices, number: int, body: schemas.CommitBody) -> Result:
    """``alfred worktree commit``."""
    results = services.commits.commit(
        number, body.type, body.message, repository=body.repo.strip() or None
    )
    if not results:
        return _result("Nothing to commit", commits=[])
    return _result(
        "; ".join(f"{item.repository}: {item.revision} {item.message}" for item in results),
        commits=[
            {"repository": item.repository, "revision": item.revision, "message": item.message}
            for item in results
        ],
    )


def push_worktrees(services: AlfredServices, number: int, body: schemas.PushBody) -> Result:
    """``alfred worktree push``: the only operation that mutates a remote."""
    results = services.commits.push(number, repository=body.repo.strip() or None)
    return _result(
        "; ".join(f"{item.repository}: pushed {item.branch} to {item.remote}" for item in results)
        or "No worktrees to push",
        pushed=[
            {"repository": item.repository, "branch": item.branch, "remote": item.remote}
            for item in results
        ],
    )


def remove_worktrees(
    services: AlfredServices, number: int, body: schemas.RemoveWorktreesBody
) -> Result:
    """Remove a task's worktrees after its run ended (the manual Git cleanup step).

    Refused while a run is active (use stop with cleanup instead); dirty worktrees require an
    explicit force, matching ``alfred run stop --cleanup yes --force``.
    """
    task = services.tasks.require(number)
    active = services.runs.active(number)
    if active is not None:
        raise ValueError(
            f"Task {number} has an active run ({active.run_status}); stop it with cleanup instead"
        )
    statuses = services.worktrees.statuses(number)
    if not statuses:
        raise ValueError(f"Task {number} has no worktrees")
    dirty = [status.repository for status in statuses if status.changes.strip()]
    if dirty and not body.force:
        raise ValueError(
            f"Task {number} worktrees have uncommitted changes: {', '.join(dirty)}; "
            "commit them or confirm force to discard them"
        )
    removed = services.worktrees.cleanup(number, force=body.force)
    names = ", ".join(path.name for path in removed)
    services.tasks.record(
        task,
        "WORKTREES_REMOVED",
        f"Removed worktrees: {names}" + (" (forced)" if body.force else ""),
        actor=body.actor,
    )
    return _result(f"Removed worktrees for task {number}: {names}")


# Tracker, knowledge, coordinator, learner, notifications -------------------------------------


def sync_apply(services: AlfredServices, body: schemas.SyncApplyBody) -> Result:
    """``alfred sync apply`` for one task or every task."""
    numbers = (
        [body.task]
        if body.task is not None
        else [task.task_number for task in services.tasks.list()]
    )
    for number in numbers:
        services.sync.apply(number, actor=body.actor)
    return _result(
        f"Synchronized {len(numbers)} task(s)" if numbers else "No tasks to synchronize",
        tasks=numbers,
    )


def add_knowledge(services: AlfredServices, body: schemas.KnowledgeBody) -> Result:
    """``alfred knowledge add``."""
    path = services.knowledge.add(
        body.task,
        body.category,
        body.title,
        body.content,
        agent=body.agent,
        related_files=tuple(_clean(body.files)),
        related_repositories=tuple(_clean(body.modules)),
    )
    return _result(f"Knowledge entry created: {path}", path=str(path))


def coordinator_name(services: AlfredServices) -> str:
    """Return the coordinator session name for this workspace."""
    return f"{services.config.runtime.session_prefix}-coordinator"


def coordinator_start(services: AlfredServices) -> Result:
    """``alfred coordinator start``: run ``coordinator loop`` in a background tmux session."""
    name = coordinator_name(services)
    if not services.sessions.available():
        raise RuntimeError("tmux is required to start the coordinator in the background")
    if services.sessions.exists(name):
        return _result(f"Coordinator already running: {name}")
    command = (
        sys.executable,
        "-m",
        "alfred",
        "--config",
        str(services.config.config_path),
        "coordinator",
        "loop",
    )
    services.sessions.create(name, services.config.workspace.root, command)
    return _result(f"Coordinator started: {name}")


def coordinator_stop(services: AlfredServices) -> Result:
    """``alfred coordinator stop``."""
    name = coordinator_name(services)
    if services.sessions.available() and services.sessions.exists(name):
        services.sessions.stop(name)
        return _result(f"Coordinator stopped: {name}")
    return _result("Coordinator is not running")


def coordinator_once(services: AlfredServices) -> Result:
    """``alfred coordinator once``."""
    cycle = services.coordinator.process_once()
    return _result(
        f"Processed={cycle.processed} invalid={cycle.invalid} dead_sessions={cycle.dead_sessions}",
        processed=cycle.processed,
        invalid=cycle.invalid,
        dead_sessions=cycle.dead_sessions,
    )


def learner_start(services: AlfredServices, body: schemas.LearnerStartBody) -> Result:
    """``alfred learner start``."""
    alias = body.agent or next(iter(sorted(services.config.agents)), "")
    if not alias:
        raise ValueError("Configure an agent or choose one")
    started = services.learner.start(alias)
    return _result("Learner started" if started else "Learner already running", agent=alias)


def learner_stop(services: AlfredServices) -> Result:
    """``alfred learner stop``."""
    stopped = services.learner.stop()
    return _result("Learner stopped" if stopped else "Learner is not running")


def acknowledge_notifications(
    services: AlfredServices, body: schemas.NotificationAckBody
) -> Result:
    """``alfred notifications ack``."""
    count = services.notifications.acknowledge(body.task)
    return _result(f"Acknowledged {count} notification(s) for task {body.task}", count=count)


def clear_notifications(services: AlfredServices) -> Result:
    """``alfred notifications clear``."""
    count = services.notifications.clear_acknowledged()
    return _result(f"Cleared {count} acknowledged notification(s)", count=count)


def migrate(services: AlfredServices, body: schemas.MigrateBody) -> Result:
    """``alfred migrate``."""
    directory = (
        Path(body.migration_directory).expanduser()
        if body.migration_directory.strip()
        else services.config.runtime.state_directory.parent / "migrations"
    )
    result = migrate_legacy_runtime(Path(body.source).expanduser(), services.store, directory)
    state = "already migrated" if result.already_migrated else "migrated"
    fragment = ""
    if result.agent_fragment is not None and result.agent_fragment.is_file():
        fragment = result.agent_fragment.read_text(encoding="utf-8")
    return _result(
        f"Legacy runtime {state}: tasks={result.tasks} runs={result.runs} "
        f"queued={result.queued_tasks}",
        already_migrated=result.already_migrated,
        backup_directory=str(result.backup_directory),
        marker_path=str(result.marker_path),
        agent_fragment=str(result.agent_fragment) if result.agent_fragment else "",
        agent_fragment_text=fragment,
        tasks=result.tasks,
        runs=result.runs,
        queued_tasks=result.queued_tasks,
    )


def initialize(body: schemas.InitBody) -> Path:
    """``alfred init``."""
    return initialize_workspace(Path(body.root).expanduser(), force=body.force)


# Sessions ----------------------------------------------------------------------------------


def owned_session(services: AlfredServices, name: str) -> dict[str, Any]:
    """Return a description of an Alfred-owned session or raise if it is not one."""
    prefix = services.config.runtime.session_prefix
    if not name.startswith(f"{prefix}-"):
        raise PermissionError(f"Session {name} does not belong to this workspace ({prefix}-*)")
    run = next((run for run in reversed(services.runs.list()) if run.session_name == name), None)
    placeholder = SessionInfo(name=name, created=0, activity=0, attached=0, windows=0, panes=())
    return describe_session(placeholder, prefix, run)


def send_text(
    services: AlfredServices,
    inspector: TmuxInspector,
    name: str,
    body: schemas.SendTextBody,
) -> Result:
    """Paste a message into an agent session, recording it on the task by default."""
    session = owned_session(services, name)
    scratch = services.config.runtime.temp_directory / "ui" / "messages"
    inspector.send_text(
        name, body.text, submit=body.submit, scratch_directory=scratch, bracketed=body.bracketed
    )
    number = session["task_number"]
    if body.record and body.text.strip() and number is not None:
        task = services.tasks.get(number)
        if task is not None:
            services.tasks.record(task, "OPERATOR_MESSAGE", body.text.strip(), actor=body.actor)
    return _result(f"Sent message to {name}")


def send_keys(
    services: AlfredServices, inspector: TmuxInspector, name: str, body: schemas.SendKeysBody
) -> Result:
    """Send named keys to a session (for example to answer an agent's trust dialog)."""
    owned_session(services, name)
    inspector.send_keys(name, body.keys)
    return _result(f"Sent {' '.join(body.keys)} to {name}")


def kill_session(
    services: AlfredServices,
    inspector: TmuxInspector,
    name: str,
    body: schemas.KillSessionBody,
) -> Result:
    """Stop a session no active run owns, such as one left behind after completion.

    The coordinator and learner sessions are stopped through their own commands so the learner's
    marker is removed as ``alfred learner stop`` would.
    """
    session = owned_session(services, name)
    if session["kind"] == "coordinator" and name == coordinator_name(services):
        return coordinator_stop(services)
    if session["kind"] == "learner" and name == services.learner.session_name:
        return learner_stop(services)
    number = session["task_number"]
    if number is not None:
        active = services.runs.active(number)
        if (
            active is not None
            and active.session_name == name
            and active.run_status != RunStatus.QUEUED
        ):
            raise ValueError(
                f"Session {name} belongs to task {number}'s active run; stop the run instead"
            )
    if not inspector.exists(name):
        raise ValueError(f"Session {name} is not running")
    transcript = _safe_capture(services, inspector, name, number, "closed")
    inspector.kill(name)
    if number is not None:
        task = services.tasks.get(number)
        if task is not None:
            services.tasks.record(
                task, "SESSION_CLOSED", f"Closed tmux session {name}.", actor=body.actor
            )
    return _result(f"Closed session {name}", transcript=transcript)


def capture_session(
    services: AlfredServices,
    inspector: TmuxInspector,
    name: str,
    body: schemas.CaptureBody,
) -> Result:
    """Save a session's full scrollback as a transcript."""
    session = owned_session(services, name)
    store = TranscriptStore.for_config(services.config)
    transcript = store.capture(
        inspector, name, task_number=session["task_number"], reason=body.reason or "manual"
    )
    return _result(f"Saved transcript {transcript['name']}", transcript=transcript)


def _safe_capture(
    services: AlfredServices,
    inspector: TmuxInspector,
    name: str,
    number: int | None,
    reason: str,
) -> dict[str, Any] | None:
    """Best-effort transcript capture that never blocks the action it precedes."""
    try:
        if not inspector.exists(name):
            return None
        return TranscriptStore.for_config(services.config).capture(
            inspector, name, task_number=number, reason=reason
        )
    except (OSError, RuntimeError, ValueError):
        return None
