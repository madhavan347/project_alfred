#!/usr/bin/env python3
"""Create a disposable Alfred workspace with real Git repositories for trying out the UI.

The sandbox follows docs/end-to-end-testing.md: a working repository with a local bare remote,
an initialized ``.alfred`` workspace, the Markdown tracker enabled, and a one-entry knowledge
requirement. Agents include the scripted ``fake`` agent (which really runs ``alfred`` commands),
a ``recorder`` that only waits, and, with ``--real-agents``, Claude Code and Codex presets.

    python ui/scripts/make_sandbox.py --root /path/to/new/sandbox --seed
"""

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def git(*arguments: str, cwd: Path) -> None:
    """Run git quietly, raising on failure."""
    subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True, text=True)


def create_repository(root: Path, name: str, *, remote: bool) -> Path:
    """Create a repository with one commit on ``main`` and, optionally, a bare remote."""
    path = root / name
    path.mkdir(parents=True)
    git("init", "-b", "main", cwd=path)
    git("config", "user.name", "Alfred Sandbox", cwd=path)
    git("config", "user.email", "alfred-sandbox@example.invalid", cwd=path)
    (path / "README.md").write_text(f"# {name}\n\nSandbox repository for Alfred.\n")
    git("add", "README.md", cwd=path)
    git("commit", "-m", "Initial fixture", cwd=path)
    if remote:
        bare = root / f"{name}-remote.git"
        subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
        git("remote", "add", "origin", str(bare), cwd=path)
    return path


def config_text(prefix: str, python: str, *, real_agents: bool, second_repo: bool) -> str:
    """Render the sandbox configuration."""
    fake = [python, str(SCRIPTS / "fake_agent.py")]
    fake_plan = [*fake, "--phase", "{phase}", "--task", "{task_number}", "--prompt-file"]
    lines = [
        "version = 1",
        "",
        "[alfred]",
        'timezone = "UTC"',
        'state_directory = ".alfred/state"',
        'temp_directory = ".alfred/tmp"',
        'worktree_directory = ".alfred/worktrees"',
        f'session_prefix = "{prefix}"',
        'tmux_unavailable_policy = "queue"',
        "",
        "[workspace]",
        'root = ".."',
        "",
        "[[repositories]]",
        'name = "app"',
        'path = "app"',
        'default_branch = "main"',
        'remote = "origin"',
        "selected_by_default = true",
        "",
    ]
    if second_repo:
        lines += [
            "[[repositories]]",
            'name = "library"',
            'path = "library"',
            'default_branch = "main"',
            'remote = "origin"',
            "selected_by_default = false",
            "",
        ]
    lines += [
        "[agents.fake]",
        'runtime_target = "scripted-agent"',
        "",
        "[agents.fake.commands]",
        f"direct = {_array([*fake, '--phase', 'direct', '--prompt-file', '{prompt_file}'])}",
        f"plan = {_array([*fake_plan, '{prompt_file}'])}",
        f"execution = {_array([*fake_plan, '{prompt_file}'])}",
        "",
        "[agents.recorder]",
        'runtime_target = "local-test"',
        "",
        "[agents.recorder.commands]",
        'direct = ["tail", "-f", "/dev/null"]',
        'plan = ["tail", "-f", "/dev/null"]',
        'execution = ["tail", "-f", "/dev/null"]',
        "",
    ]
    if real_agents:
        lines += [
            "[agents.claude]",
            'runtime_target = "claude-code"',
            "",
            "[agents.claude.commands]",
            'direct = ["claude", "{prompt}"]',
            'plan = ["claude", "{prompt}"]',
            'execution = ["claude", "{prompt}"]',
            "",
            "[agents.codex]",
            'runtime_target = "codex"',
            "",
            "[agents.codex.commands]",
            'direct = ["codex", "{prompt}"]',
            'plan = ["codex", "{prompt}"]',
            'execution = ["codex", "{prompt}"]',
            "",
        ]
    lines += [
        "[trackers.markdown]",
        "enabled = true",
        'canonical = "tracking/tasks.md"',
        'agents = "tracking/agents.md"',
        'daily_notes = "tracking/daily"',
        "",
        "[commit.tags]",
        'patch = "[PATCH]"',
        'fix = "[FIX]"',
        'feature = "[FEATURE]"',
        "",
        "[knowledge]",
        'directory = ".alfred/knowledge"',
        "required_completion_entries = 1",
        "",
    ]
    return "\n".join(lines)


def _array(values: list[str]) -> str:
    return "[" + ", ".join(json.dumps(value) for value in values) + "]"


def seed(config: Path) -> None:
    """Create a handful of tasks in different states through Alfred's own services."""
    from alfred.bootstrap import build_services
    from alfred.domain.constants import DispatchMode, ExecutionMode, PlanningState
    from alfred.domain.models import Task

    services = build_services(config_path=config)
    tasks = [
        Task(
            task_number=1,
            title="Add a health endpoint",
            description="Expose GET /health returning ok. [fake:wait]",
            priority="P1",
            category="Backend",
            branch_name="feature/health-1",
            assigned_agent_alias="fake",
            target_repositories=["app"],
        ),
        Task(
            task_number=2,
            title="Plan the storage migration",
            description="Plan, then migrate the storage layer.",
            priority="P2",
            category="Data",
            branch_name="feature/storage-2",
            assigned_agent_alias="fake",
            execution_mode=ExecutionMode.PLAN_EXECUTION,
            planning_state=PlanningState.PENDING,
            target_repositories=["app"],
            dependencies=[1],
        ),
        Task(
            task_number=3,
            title="Tidy the README",
            description="Queue this documentation fix for the next batch.",
            priority="P3",
            category="Docs",
            branch_name="docs/readme-3",
            assigned_agent_alias="fake",
            dispatch_mode=DispatchMode.QUEUED,
        ),
        Task(
            task_number=4,
            title="Investigate flaky test",
            description="The nightly run fails one test intermittently.",
            priority="P0",
            category="Quality",
            branch_name="fix/flaky-4",
        ),
    ]
    for task in tasks:
        services.tasks.upsert(task)
    services.tasks.block(4, "Waiting for access to the nightly logs")


def main() -> int:
    """Create the sandbox and print how to open it."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, required=True, help="new, empty directory")
    parser.add_argument("--prefix", default="alfred-sandbox", help="tmux session prefix")
    parser.add_argument("--python", default=sys.executable, help="interpreter for fake agents")
    parser.add_argument("--seed", action="store_true", help="create example tasks")
    parser.add_argument("--real-agents", action="store_true", help="add claude and codex agents")
    parser.add_argument("--second-repo", action="store_true", help="add a library repository")
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        parser.error(f"{root} is not empty")
    root.mkdir(parents=True, exist_ok=True)
    create_repository(root, "app", remote=True)
    if args.second_repo:
        create_repository(root, "library", remote=True)
    (root / "tracking" / "daily").mkdir(parents=True)

    from alfred.config.initializer import initialize_workspace

    config = initialize_workspace(root)
    config.write_text(
        config_text(
            args.prefix, args.python, real_agents=args.real_agents, second_repo=args.second_repo
        ),
        encoding="utf-8",
    )
    if args.seed:
        seed(config)
    print(f"Sandbox ready: {root}")
    print(f"Config: {config}")
    print(f"Start the UI: alfred-ui --config {shlex.quote(str(config))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
