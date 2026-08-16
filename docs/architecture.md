# Architecture

Alfred uses explicit dependency direction so workflow policy stays testable and external tools
remain replaceable.

```text
CLI -> bootstrap -> application services -> domain models and pure policy
                         |
                         +-> ports -> Git, tmux, JSON, Markdown, filesystem adapters
```

## Packages

- `alfred.domain` owns typed task/run details, constants, validation, and transition policy. It does
  not perform I/O.
- `alfred.config` discovers and strictly parses project TOML, initializes workspaces, and performs
  non-destructive legacy migration.
- `alfred.application` coordinates task, run, dispatch, notification, knowledge, tracker, and
  reporting workflows.
- `alfred.ports` defines the small process, session, and tracker protocols used by workflows.
- `alfred.adapters` implements atomic JSON/filesystem storage, Git worktrees and commits, tmux,
  Markdown synchronization, and completion-file handoff.
- `alfred.cli` defines parsing separately from command execution.
- `alfred.bootstrap` is the only composition root. Constructing services initializes missing local
  state but does not start processes, create worktrees, or access the network.

## State flow

Task changes are validated, persisted to versioned JSON, appended to the event log, and then sent
to the optional tracker. Tracker failure rolls task and event state back to their prior snapshots.
Atomic writes use a temporary file in the target directory followed by `replace`, preserving
same-filesystem semantics.

Run orchestration has two paths:

1. Direct execution creates or reuses worktrees and dispatches the execution prompt.
2. Plan-execution dispatches without worktrees, records approval, creates worktrees, then reuses the
   session for execution.

Agents submit structured completion reports. The coordinator validates and archives those reports,
creates human-review notifications, and detects unexpectedly dead sessions without duplicating
alerts.

## Safety boundaries

- Child processes receive argument tuples; Alfred does not construct shell pipelines.
- Repository paths, names, branches, agents, and tmux sessions are validated before use.
- Network mutation occurs only through the explicit worktree push command.
- Legacy migration requires an empty destination and retains both source and backup.
- Dirty worktrees cannot be removed unless force is explicitly selected.
