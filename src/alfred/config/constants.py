"""Stable configuration defaults that do not contain user-specific paths."""

from pathlib import Path


CONFIG_VERSION = 1
CONFIG_DIRECTORY = Path(".alfred")
CONFIG_FILENAME = "config.toml"
DEFAULT_STATE_DIRECTORY = CONFIG_DIRECTORY / "state"
DEFAULT_TEMP_DIRECTORY = CONFIG_DIRECTORY / "tmp"
DEFAULT_WORKTREE_DIRECTORY = CONFIG_DIRECTORY / "worktrees"
DEFAULT_TIMEZONE = "UTC"
DEFAULT_SESSION_PREFIX = "alfred-task"
DEFAULT_TMUX_POLICY = "queue"

DEFAULT_COMMIT_TAGS = {
    "PATCH": "[PATCH]",
    "FIX": "[FIX]",
    "FEATURE": "[FEATURE]",
}

VALID_TMUX_POLICIES = frozenset({"queue", "error"})
