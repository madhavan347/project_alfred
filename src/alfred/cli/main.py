"""Top-level Alfred command-line entry point."""

from collections.abc import Sequence

from alfred.bootstrap import build_services
from alfred.cli.parser import build_parser
from alfred.cli.run_commands import handle_run, handle_worktree
from alfred.cli.task_commands import handle_agent, handle_task
from alfred.config.initializer import initialize_workspace


def main(argv: Sequence[str] | None = None) -> int:
    """Parse command-line arguments and return a process status."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.resource == "init":
        try:
            config_path = initialize_workspace(args.root, force=args.force)
        except FileExistsError as exc:
            parser.error(str(exc))
        print(f"Initialized Alfred workspace: {config_path}")
        return 0
    if args.resource in {"task", "agent", "run", "worktree"}:
        try:
            services = build_services(config_path=args.config)
            if args.resource == "task":
                return handle_task(args, services)
            if args.resource == "agent":
                return handle_agent(args, services)
            if args.resource == "run":
                return handle_run(args, services)
            return handle_worktree(args, services)
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            print(f"ERROR: {exc}")
            return 1
    if args.resource is None:
        parser.print_help()
    else:
        print(f"ERROR: Handler is not available yet: {args.resource}")
        return 1
    return 0
