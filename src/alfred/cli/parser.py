"""Argument parser definitions for Alfred's stable command surface."""

import argparse
from pathlib import Path

from alfred import __version__


def build_parser() -> argparse.ArgumentParser:
    """Create the complete parser without loading configuration or touching disk."""
    parser = argparse.ArgumentParser(
        prog="alfred",
        description="Coordinate local tasks, agents, and Git worktrees.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="path to .alfred/config.toml (overrides ALFRED_CONFIG and discovery)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    resources = parser.add_subparsers(dest="resource")

    init_parser = resources.add_parser("init", help="initialize an Alfred workspace")
    init_parser.add_argument("--root", type=Path, default=Path.cwd())
    init_parser.add_argument("--force", action="store_true")

    _task_parser(resources)
    _agent_parser(resources)
    _run_parser(resources)
    _worktree_parser(resources)
    _sync_parser(resources)
    _knowledge_parser(resources)
    _report_parser(resources)
    _coordinator_parser(resources)
    _learner_parser(resources)
    _notification_parser(resources)
    return parser


def _task_parser(resources: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    task = resources.add_parser("task", help="manage the task lifecycle")
    actions = task.add_subparsers(dest="action", required=True)
    create = actions.add_parser("create")
    create.add_argument("--task", type=int, required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--description", required=True)
    create.add_argument("--category", default="General")
    create.add_argument("--priority", default="P2")
    create.add_argument("--deadline", default="")
    create.add_argument("--notes", default="")
    create.add_argument("--assign", default="")
    create.add_argument("--dispatch", choices=("auto", "queued"), default="auto")
    create.add_argument("--branch", default="")
    create.add_argument("--mode", choices=("direct", "plan-execution"), default="direct")
    create.add_argument("--worktree", choices=("enabled", "disabled"), default="enabled")
    create.add_argument("--repos", default="", help="comma-separated repository names")
    create.add_argument("--dependencies", default="", help="comma-separated task numbers")

    update = actions.add_parser("update")
    update.add_argument("--task", type=int, required=True)
    for name in ("title", "description", "category", "priority", "deadline", "notes", "branch"):
        update.add_argument(f"--{name}")
    update.add_argument("--mode", choices=("direct", "plan-execution"))
    update.add_argument("--worktree", choices=("enabled", "disabled"))
    update.add_argument("--repos")
    update.add_argument("--dependencies")

    _task_actor_action(actions, "start")
    progress = _task_actor_action(actions, "progress")
    progress.add_argument("--note", required=True)
    block = _task_actor_action(actions, "block")
    block.add_argument("--reason", required=True)
    unblock = _task_actor_action(actions, "unblock")
    unblock.add_argument("--note", default="")
    review = _task_actor_action(actions, "review")
    review.add_argument("--decision", choices=("approved", "changes_requested"), required=True)
    review.add_argument("--note", required=True)
    merge = _task_actor_action(actions, "merge")
    merge.add_argument("--mr", default="")
    deploy = _task_actor_action(actions, "deploy")
    deploy.add_argument("--env", default="production")
    deploy.add_argument("--result", default="passed")
    archive = _task_actor_action(actions, "archive")
    archive.add_argument("--note", default="")
    consolidate = _task_actor_action(actions, "consolidate")
    consolidate.add_argument("--note", default="")


def _task_actor_action(
    actions: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
) -> argparse.ArgumentParser:
    parser = actions.add_parser(name)
    parser.add_argument("--task", type=int, required=True)
    parser.add_argument("--actor", default="manager")
    return parser


def _agent_parser(resources: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    agent = resources.add_parser("agent", help="manage agent assignment")
    actions = agent.add_subparsers(dest="action", required=True)
    for name in ("assign", "reassign"):
        command = actions.add_parser(name)
        command.add_argument("--task", type=int, required=True)
        command.add_argument("--to", required=True)
        command.add_argument("--actor", default="manager")
        if name == "assign":
            command.add_argument("--dispatch", choices=("auto", "queued"))
        else:
            command.add_argument(
                "--mode",
                choices=("soft-switch", "stop-and-switch"),
                default="soft-switch",
            )
    status = actions.add_parser("status")
    status.add_argument("--task", type=int, required=True)


def _run_parser(resources: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    run = resources.add_parser("run", help="dispatch and monitor agent runs")
    actions = run.add_subparsers(dest="action", required=True)
    trigger = actions.add_parser("trigger")
    trigger.add_argument("--tasks", default="")
    trigger.add_argument("--all", action="store_true")
    trigger.add_argument("--parallel", type=int, default=1)
    trigger.add_argument("--actor", default="manager")
    listing = actions.add_parser("list")
    listing.add_argument("--status", default="")
    stop = actions.add_parser("stop")
    stop.add_argument("--task", type=int, required=True)
    stop.add_argument("--reason", default="manual stop")
    stop.add_argument("--cleanup", choices=("ask", "yes", "no"), default="ask")
    stop.add_argument("--force", action="store_true")
    continuation = actions.add_parser("continue")
    continuation.add_argument("--task", type=int, required=True)
    continuation.add_argument("--note", default="")
    continuation.add_argument("--actor", default="manager")
    attach = actions.add_parser("attach")
    attach.add_argument("--task", type=int, required=True)
    sessions = actions.add_parser("sessions")
    sessions.add_argument("--task", type=int)
    event = actions.add_parser("event")
    event.add_argument("--task", type=int, required=True)
    event.add_argument(
        "--type",
        required=True,
        choices=(
            "plan_completed",
            "plan_approved",
            "progress",
            "coding",
            "execution_started",
            "blocked",
            "unblocked",
            "review_requested",
            "fixing",
        ),
    )
    event.add_argument("--note", default="")
    event.add_argument("--actor", default="agent:unknown")
    event.add_argument("--override-manager", action="store_true")
    complete = actions.add_parser("complete")
    complete.add_argument("--task", type=int, required=True)
    complete.add_argument("--result", choices=("success", "failed", "blocked"))
    complete.add_argument(
        "--status",
        choices=("success", "failed", "blocked"),
        dest="status_alias",
    )
    complete.add_argument("--note", default="")
    complete.add_argument("--summary", default="", dest="summary_alias")
    complete.add_argument("--actor", default="agent:unknown")
    complete.add_argument("--override-manager", action="store_true")
    reopen = actions.add_parser("reopen")
    reopen.add_argument("--task", type=int, required=True)
    reopen.add_argument("--actor", default="manager")


def _worktree_parser(resources: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    worktree = resources.add_parser("worktree", help="manage task worktrees")
    actions = worktree.add_subparsers(dest="action", required=True)
    create = actions.add_parser("create")
    create.add_argument("--task", type=int, required=True)
    create.add_argument("--repos", required=True)
    status = actions.add_parser("status")
    status.add_argument("--task", type=int, required=True)
    commit = actions.add_parser("commit")
    commit.add_argument("--task", type=int, required=True)
    commit.add_argument("--type", required=True)
    commit.add_argument("--message", required=True)
    commit.add_argument("--repo")
    push = actions.add_parser("push")
    push.add_argument("--task", type=int, required=True)
    push.add_argument("--repo")


def _sync_parser(resources: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    sync = resources.add_parser("sync", help="validate or reconcile tracker drift")
    actions = sync.add_subparsers(dest="action", required=True)
    for name in ("validate", "drift-report", "apply"):
        command = actions.add_parser(name)
        command.add_argument("--task", type=int)


def _knowledge_parser(resources: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    knowledge = resources.add_parser("knowledge", help="manage project knowledge")
    actions = knowledge.add_subparsers(dest="action", required=True)
    add = actions.add_parser("add")
    add.add_argument("--task", type=int, required=True)
    add.add_argument("--category", required=True)
    add.add_argument("--title", required=True)
    add.add_argument("--content", required=True)
    add.add_argument("--agent", default="")
    add.add_argument("--files", default="")
    add.add_argument("--modules", default="", help="related repository names")
    listing = actions.add_parser("list")
    listing.add_argument("--category")


def _report_parser(resources: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    report = resources.add_parser("report", help="show local task reports")
    actions = report.add_subparsers(dest="action", required=True)
    for name in ("today", "risk", "dependency", "velocity"):
        actions.add_parser(name)


def _coordinator_parser(
    resources: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    coordinator = resources.add_parser("coordinator", help="manage completion monitoring")
    actions = coordinator.add_subparsers(dest="action")
    for name in ("start", "stop", "status", "once", "loop"):
        actions.add_parser(name)


def _learner_parser(resources: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    learner = resources.add_parser("learner", help="manage the learner agent")
    actions = learner.add_subparsers(dest="action")
    start = actions.add_parser("start")
    start.add_argument("--agent")
    for name in ("stop", "status", "attach"):
        actions.add_parser(name)


def _notification_parser(
    resources: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    notifications = resources.add_parser("notifications", help="manage notifications")
    actions = notifications.add_subparsers(dest="action")
    acknowledge = actions.add_parser("ack")
    acknowledge.add_argument("--task", type=int, required=True)
    actions.add_parser("clear")
