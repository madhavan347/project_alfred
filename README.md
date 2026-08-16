# Alfred

Alfred is a local, configuration-driven workflow orchestrator for coordinating tasks,
command-line agents, Git worktrees, and human review on macOS.

It keeps project configuration in `.alfred/config.toml`, stores local state as versioned JSON,
uses argument arrays instead of shell command templates, and performs no implicit Git push.

> [!IMPORTANT]
> This repository does not grant a license yet. Do not publish, redistribute, or reuse the code
> until the owner selects and adds a license.

## Requirements

- macOS
- Python 3.11 or newer
- Git
- tmux for interactive agent and background coordinator sessions

tmux can be optional when `tmux_unavailable_policy = "queue"`; dispatches are then persisted for
later execution.

## Install for local development

```console
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/alfred --version
```

The repository-local `./alfred` launcher remains available for compatibility.

## Quick start

Initialize configuration and private runtime directories in a project:

```console
alfred init --root /path/to/project
```

Then edit `/path/to/project/.alfred/config.toml` to declare repositories and agents:

```toml
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

[[repositories]]
name = "app"
path = "."
default_branch = "main"
remote = "origin"
selected_by_default = true

[agents.builder]
runtime_target = "local"

[agents.builder.commands]
direct = ["agent-cli"]
plan = ["agent-cli", "--plan"]
execution = ["agent-cli", "--execute"]

[trackers.markdown]
enabled = false

[commit.tags]
patch = "[PATCH]"
fix = "[FIX]"
feature = "[FEATURE]"

[knowledge]
directory = ".alfred/knowledge"
required_completion_entries = 0
```

Create, assign, and dispatch a task:

```console
alfred --config /path/to/project/.alfred/config.toml task create \
  --task 7 \
  --title "Add health endpoint" \
  --description "Implement and test the endpoint" \
  --branch feature/health \
  --assign builder

alfred --config /path/to/project/.alfred/config.toml run trigger --tasks 7
alfred --config /path/to/project/.alfred/config.toml run attach --task 7
```

## Workflow

```text
task details -> assignment -> plan (optional) -> worktrees -> agent session
     -> progress/events -> completion report -> human review -> deploy/archive
```

Direct tasks create configured worktrees before execution. `plan-execution` tasks dispatch a
planning prompt first, wait for `alfred run continue --task N`, then create worktrees and reuse the
same session for implementation. Completion is actor-checked unless an explicit manager override
is supplied.

Important command groups:

| Command | Purpose |
|---|---|
| `alfred task ...` | Create, update, review, deploy, archive, or consolidate tasks |
| `alfred agent ...` | Assign or reassign configured agents |
| `alfred run ...` | Trigger, continue, stop, inspect, or complete agent runs |
| `alfred worktree ...` | Create, inspect, commit, and explicitly push task worktrees |
| `alfred sync ...` | Validate or reconcile the optional Markdown tracker |
| `alfred knowledge ...` | Add or list categorized project learnings |
| `alfred coordinator ...` | Process completions and monitor session health |
| `alfred learner ...` | Run a configured knowledge-learning agent |
| `alfred notifications ...` | Review and acknowledge human-action notifications |
| `alfred migrate ...` | Back up and migrate legacy JSON runtime state |

Run `alfred <group> --help` for the complete arguments.

## State, safety, and migration

Alfred writes project-local runtime files beneath `.alfred/`. Configuration, state, prompts,
completion reports, worktrees, and knowledge may contain sensitive project details and should not
be committed unless deliberately reviewed.

Git operations are repository-scoped. Worktree cleanup requires an explicit request, forced dirty
cleanup requires `--force`, and pushing is available only through `alfred worktree push`.

Legacy JSON can be migrated once into an empty destination:

```console
alfred migrate --source /path/to/legacy/data/runtime
```

The migration copies every recognized source file to a timestamped backup, writes a marker for
idempotency, and never deletes the legacy source. Migrated agent commands are emitted as a TOML
fragment for manual review.

## Development

```console
.venv/bin/ruff check alfred src tests
.venv/bin/ruff format --check alfred src tests
.venv/bin/mypy src
.venv/bin/pytest --cov=alfred --cov-report=term-missing
.venv/bin/python -m build
```

The test suite enforces 85% branch-aware coverage. See [Architecture](docs/architecture.md),
[Configuration](docs/configuration.md), and [Contributing](CONTRIBUTING.md) for more detail.

## License and publication status

No license has been granted. Before any public release, the owner must confirm ownership, select a
license, add the corresponding `LICENSE` file and package metadata, and perform the final release
review. Until then, the repository is source-available for its owner only—not open source.
