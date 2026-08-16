"""Top-level Alfred command-line entry point."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from alfred import __version__
from alfred.config.initializer import initialize_workspace


def build_parser() -> argparse.ArgumentParser:
    """Create the root parser without performing filesystem work."""
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
    subparsers = parser.add_subparsers(dest="resource")

    init_parser = subparsers.add_parser("init", help="initialize an Alfred workspace")
    init_parser.add_argument("--root", type=Path, default=Path.cwd())
    init_parser.add_argument("--force", action="store_true")
    return parser


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
