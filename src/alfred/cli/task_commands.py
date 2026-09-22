"""Task and agent command handlers."""

import argparse

from alfred.bootstrap import AlfredServices
from alfred.domain.constants import (
    DispatchMode,
    ExecutionMode,
    LifecyclePhase,
    PlanningState,
    WorktreeMode,
)
from alfred.domain.models import Task


def handle_task(args: argparse.Namespace, services: AlfredServices) -> int:
    """Execute one task lifecycle command."""
    if args.action == "create":
        task = Task(
            task_number=args.task,
            title=args.title,
            description=args.description,
            category=args.category,
            priority=args.priority,
            deadline=args.deadline,
            notes=args.notes,
            assigned_agent_alias=args.assign,
            dispatch_mode=DispatchMode(args.dispatch),
            execution_mode=ExecutionMode(args.mode),
            worktree_mode=WorktreeMode(args.worktree),
            branch_name=args.branch.strip(),
            planning_state=(
                PlanningState.PENDING
                if args.mode == ExecutionMode.PLAN_EXECUTION
                else PlanningState.NOT_REQUIRED
            ),
            target_repositories=_csv(args.repos),
            dependencies=_integer_csv(args.dependencies),
        )
        services.tasks.upsert(task)
        print(f"Created task {task.task_number}")
        return 0

    if args.action == "update":
        task = services.tasks.require(args.task)
        for field in ("title", "description", "category", "priority", "deadline", "notes"):
            value = getattr(args, field)
            if value is not None:
                setattr(task, field, value)
        if args.branch is not None:
            task.branch_name = args.branch.strip()
        if args.mode is not None:
            task.execution_mode = ExecutionMode(args.mode)
            task.planning_state = (
                PlanningState.PENDING
                if task.execution_mode == ExecutionMode.PLAN_EXECUTION
                else PlanningState.NOT_REQUIRED
            )
        if args.worktree is not None:
            task.worktree_mode = WorktreeMode(args.worktree)
        if args.repos is not None:
            task.target_repositories = _csv(args.repos)
        if args.dependencies is not None:
            task.dependencies = _integer_csv(args.dependencies)
        services.tasks.upsert(task)
        print(f"Updated task {task.task_number}")
        return 0

    if args.action == "start":
        task = services.tasks.progress(args.task, "Task started.", actor=args.actor)
    elif args.action == "progress":
        task = services.tasks.progress(args.task, args.note, actor=args.actor)
    elif args.action == "block":
        task = services.tasks.block(args.task, args.reason, actor=args.actor)
    elif args.action == "unblock":
        task = services.tasks.unblock(args.task, args.note, actor=args.actor)
    elif args.action == "review":
        task = services.tasks.review(
            args.task,
            args.decision,
            args.note,
            actor=args.actor,
        )
    elif args.action == "merge":
        task = services.tasks.merge(args.task, args.mr, actor=args.actor)
    elif args.action == "deploy":
        task = services.tasks.deploy(args.task, args.env, args.result, actor=args.actor)
    elif args.action == "archive":
        task = services.tasks.update_phase(
            args.task,
            LifecyclePhase.ARCHIVED,
            args.note or "Archived after completion.",
            actor=args.actor,
        )
    elif args.action == "consolidate":
        task = services.tasks.update_phase(
            args.task,
            LifecyclePhase.CONSOLIDATED,
            args.note or "Consolidated into a parent task.",
            actor=args.actor,
        )
    else:
        raise ValueError(f"Unsupported task action: {args.action}")
    print(f"Task {task.task_number}: {task.status}")
    return 0


def handle_agent(args: argparse.Namespace, services: AlfredServices) -> int:
    """Execute one agent assignment command."""
    if args.action == "status":
        task = services.tasks.require(args.task)
        print(f"Task {task.task_number} agent: {task.assigned_agent_alias or '-'}")
        return 0
    if (
        args.action == "reassign"
        and args.mode == "stop-and-switch"
        and services.runs.active(args.task) is not None
    ):
        services.runs.stop(args.task, "Agent reassigned.", actor=args.actor)
    dispatch = DispatchMode(args.dispatch) if getattr(args, "dispatch", None) else None
    task = services.tasks.assign(
        args.task,
        args.to,
        actor=args.actor,
        dispatch_mode=dispatch,
    )
    print(f"Task {task.task_number} assigned to {task.assigned_agent_alias}")
    return 0


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _integer_csv(value: str) -> list[int]:
    try:
        return [int(item) for item in _csv(value)]
    except ValueError as exc:
        raise ValueError("Dependencies must be comma-separated task numbers") from exc
