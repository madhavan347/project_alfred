"""Create a generic project-local Alfred workspace."""

from pathlib import Path

from alfred.config.constants import CONFIG_DIRECTORY, CONFIG_FILENAME


DEFAULT_CONFIG = """\
version = 1

[alfred]
timezone = "UTC"
state_directory = ".alfred/state"
temp_directory = ".alfred/tmp"
worktree_directory = ".alfred/worktrees"
session_prefix = "alfred-task"
tmux_unavailable_policy = "queue"

[workspace]
root = ".."

[trackers.markdown]
enabled = false

[commit.tags]
patch = "[PATCH]"
fix = "[FIX]"
feature = "[FEATURE]"

[knowledge]
directory = ".alfred/knowledge"
required_completion_entries = 0
"""


def initialize_workspace(root: Path, *, force: bool = False) -> Path:
    """Create local configuration and runtime directories under ``root``."""
    workspace = root.expanduser().resolve()
    config_directory = workspace / CONFIG_DIRECTORY
    config_path = config_directory / CONFIG_FILENAME
    if config_path.exists() and not force:
        raise FileExistsError(
            f"Alfred configuration already exists: {config_path}; use --force to replace it"
        )

    config_directory.mkdir(parents=True, exist_ok=True)
    (config_directory / "state").mkdir(exist_ok=True)
    (config_directory / "tmp").mkdir(exist_ok=True)
    (config_directory / "worktrees").mkdir(exist_ok=True)
    config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    return config_path
