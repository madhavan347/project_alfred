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

Each agent has a `runtime_target` label and direct, plan, and execution command arrays. Task plan and
execution commands support `{task_number}`, `{task_title}`, `{task_branch}`, `{phase}`, and
`{workdir}` placeholders. The learner launches the `direct` array verbatim, so do not put task
placeholders in it; it may use only `{prompt}` or `{prompt_file}` (see below).

Commands must be TOML arrays, not shell strings:

```toml
[agents.builder.commands]
direct = ["agent-cli", "--learn"]
plan = ["agent-cli", "--task", "{task_number}", "--plan"]
execution = ["agent-cli", "--workdir", "{workdir}"]
```

#### Prompt delivery

By default Alfred starts the command and then bracket-pastes the prompt into the new session.
Interactive agent TUIs take a moment to start and may first show a folder-trust dialog, so a
prompt pasted into a brand-new session can be lost or left unsubmitted. Prefer passing the prompt
as an argument with `{prompt}` (the prompt text) or `{prompt_file}` (its path). When the command
that creates a session uses either placeholder, Alfred does not paste. This applies to task
sessions and to the learner's `direct` command. A reused session, such as plan continuation or a
reopen, always receives the prompt by paste.

```toml
[agents.claude.commands]
direct = ["claude", "{prompt}"]
plan = ["claude", "{prompt}"]
execution = ["claude", "{prompt}"]

[agents.codex.commands]
direct = ["codex", "{prompt}"]
plan = ["codex", "{prompt}"]
execution = ["codex", "{prompt}"]

[agents.agy.commands]
direct = ["agy", "-i", "{prompt}"]
plan = ["agy", "-i", "{prompt}"]
execution = ["agy", "-i", "{prompt}"]
```

Agent CLIs may stop at a folder-trust or permission-mode dialog in a detached session, before they
read the prompt. Answer each dialog once by attaching with `alfred run attach` (or `learner
attach`); the prompt passed as an argument is submitted after the dialog closes.

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
