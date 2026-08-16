# Configuration

Alfred discovers `.alfred/config.toml` using this precedence:

1. `--config PATH`
2. `ALFRED_CONFIG`
3. the nearest `.alfred/config.toml` found while walking from the current directory to its parents

Unknown keys and unsupported configuration versions are rejected. Relative runtime paths resolve
from the workspace root; repository paths also resolve from that root.

## Sections

### `alfred`

Defines the IANA timezone, state/temp/worktree directories, tmux session prefix, and unavailable-tmux
policy (`queue` or `error`).

### `workspace` and `repositories`

`workspace.root` establishes path resolution. Each `[[repositories]]` entry declares a unique name,
local path, default branch, remote, and whether it is selected when a task does not name repositories.

### `agents`

Each agent has a `runtime_target` label and direct, plan, and execution command arrays. Supported
placeholders are `{task_number}`, `{task_title}`, `{task_branch}`, `{phase}`, and `{workdir}`.

Commands must be TOML arrays, not shell strings:

```toml
[agents.builder.commands]
direct = ["agent-cli"]
plan = ["agent-cli", "--task", "{task_number}", "--plan"]
execution = ["agent-cli", "--workdir", "{workdir}"]
```

### `trackers.markdown`

The built-in tracker is disabled by default. When enabled, `canonical`, `agents`, and `daily_notes`
paths are all required. A task mutation builds all three updates before writing and rolls back files
already written if a later write fails.

### `commit.tags`

Maps configured types to rendered tags. Keys are normalized to uppercase when used. The defaults are
`PATCH`, `FIX`, and `FEATURE` with bracketed messages.

### `knowledge`

Defines the Markdown knowledge directory and the minimum number of entries expected on completion.
The coordinator reports a validation issue rather than silently accepting an under-documented task.

## Local-only files

The default `.gitignore` excludes `.alfred/config.toml`, state, prompts, worktrees, test caches, build
artifacts, and local agent/editor settings. Review any opt-in Markdown tracker or knowledge paths
before committing them because they can contain task or repository details.
