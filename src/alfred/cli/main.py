"""Top-level Alfred command-line entry point."""

import argparse
from collections.abc import Sequence

from alfred import __version__


def build_parser() -> argparse.ArgumentParser:
    """Create the root parser without performing filesystem work."""
    parser = argparse.ArgumentParser(
        prog="alfred",
        description="Coordinate local tasks, agents, and Git worktrees.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse command-line arguments and return a process status."""
    build_parser().parse_args(argv)
    return 0
