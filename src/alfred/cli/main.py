"""Top-level Alfred command-line entry point."""

from collections.abc import Sequence

from alfred.cli.parser import build_parser
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
    if args.resource is None:
        parser.print_help()
    return 0
