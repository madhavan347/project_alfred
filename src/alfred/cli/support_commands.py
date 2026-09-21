"""Sync, knowledge, report, and notification command handlers."""

import argparse

from alfred.application.reports import dependencies, risks, today, velocity
from alfred.bootstrap import AlfredServices
from alfred.config.migration import migrate_legacy_runtime


def handle_sync(args: argparse.Namespace, services: AlfredServices) -> int:
    """Validate tracker state or explicitly reconcile selected tasks."""
    if args.action in {"validate", "drift-report"}:
        issues = services.sync.validate(args.task)
        if issues:
            print("Sync/Drift Issues:")
            for issue in issues:
                print(f"- {issue}")
            return 1
        print("Sync validation passed")
        return 0
    if args.action == "apply":
        task_numbers = (
            (args.task,)
            if args.task is not None
            else tuple(task.task_number for task in services.tasks.list())
        )
        for task_number in task_numbers:
            services.sync.apply(task_number)
            print(f"Synchronized task {task_number}")
        return 0
    raise ValueError(f"Unsupported sync action: {args.action}")


def handle_knowledge(args: argparse.Namespace, services: AlfredServices) -> int:
    """Add or list project knowledge entries."""
    if args.action == "add":
        path = services.knowledge.add(
            args.task,
            args.category,
            args.title,
            args.content,
            agent=args.agent,
            related_files=tuple(_csv(args.files)),
            related_repositories=tuple(_csv(args.modules)),
        )
        print(f"Knowledge entry created: {path}")
        return 0
    entries = services.knowledge.list(args.category)
    if not entries:
        print("No knowledge entries")
    for entry in entries:
        print(entry)
    return 0


def handle_report(args: argparse.Namespace, services: AlfredServices) -> int:
    """Render one task report."""
    tasks = services.tasks.list()
    if args.action == "today":
        selected = today(tasks)
    elif args.action == "risk":
        selected = risks(tasks)
    elif args.action == "dependency":
        selected = dependencies(tasks)
    elif args.action == "velocity":
        result = velocity(tasks)
        print(f"Completed {result.completed}/{result.total}")
        return 0
    else:
        raise ValueError(f"Unsupported report action: {args.action}")
    for task in selected:
        if args.action == "dependency":
            print(f"Task {task.task_number} depends on {task.dependencies}")
        else:
            print(
                f"Task {task.task_number}: {task.status} | {task.priority} | "
                f"{task.assigned_agent_alias or '-'} | {task.title}"
            )
    return 0


def handle_notifications(args: argparse.Namespace, services: AlfredServices) -> int:
    """List, acknowledge, or clear persistent notifications."""
    if args.action == "ack":
        count = services.notifications.acknowledge(args.task)
        print(f"Acknowledged {count} notification(s) for task {args.task}")
        return 0
    if args.action == "clear":
        count = services.notifications.clear_acknowledged()
        print(f"Cleared {count} acknowledged notification(s)")
        return 0
    pending = services.notifications.pending()
    if not pending:
        print("No pending notifications")
    for notification in pending:
        details = notification.details
        summary = details.get("summary") or details.get("message", "")
        print(
            f"[{notification.notification_type}] Task {notification.task_number} — "
            f"{summary} ({notification.created_at})"
        )
        context = [
            f"{label}={value}"
            for label, value in (
                ("status", details.get("status", "")),
                ("agent", details.get("agent", "")),
                ("repositories", ",".join(details.get("repositories", ()))),
                ("session", details.get("session_name", "")),
            )
            if value
        ]
        if context:
            print(f"  {' '.join(context)}")
        for issue in details.get("validation_issues", ()):
            print(f"  VALIDATION: {issue}")
    return 0


def handle_migration(args: argparse.Namespace, services: AlfredServices) -> int:
    """Migrate legacy JSON state after creating an immutable local backup."""
    directory = args.migration_directory or (
        services.config.runtime.state_directory.parent / "migrations"
    )
    result = migrate_legacy_runtime(
        args.source,
        services.store,
        directory,
    )
    state = "already migrated" if result.already_migrated else "migrated"
    print(
        f"Legacy runtime {state}: tasks={result.tasks} runs={result.runs} "
        f"queued={result.queued_tasks}"
    )
    print(f"Backup: {result.backup_directory}")
    print(f"Marker: {result.marker_path}")
    if result.agent_fragment is not None:
        print(f"Review agent configuration: {result.agent_fragment}")
    return 0


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
