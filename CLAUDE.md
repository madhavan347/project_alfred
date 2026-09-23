# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Setup (no `.venv` is checked in; create one before running any check):

```console
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Required quality suite — all five must pass before a commit is considered done:

```console
.venv/bin/ruff check alfred src tests
.venv/bin/ruff format --check alfred src tests
.venv/bin/mypy src            # strict mode, packages = ["alfred"]
.venv/bin/pytest --cov=alfred --cov-report=term-missing   # branch coverage, fail_under = 85
.venv/bin/python -m build
```

Note that `alfred` (the repo-local launcher script) is linted alongside `src` and `tests`.

Tests are `unittest.TestCase` classes run under pytest, so target them by node id:

```console
.venv/bin/pytest tests/application/test_runs.py
.venv/bin/pytest tests/application/test_runs.py::RunServiceTests::test_direct_trigger_creates_worktree_and_running_run
.venv/bin/pytest -k worktree
```

Running the CLI during development: `.venv/bin/alfred ...`, or `./alfred ...` (compatibility
launcher that prepends `src/` to `sys.path`), or `python -m alfred`.

## Architecture

Alfred is a macOS-only, configuration-driven orchestrator for tasks, CLI agents, Git worktrees, and
human review. Dependency direction is strict and one-way:

```text
cli -> bootstrap -> application -> domain
                        |
                        +-> ports (Protocols) -> adapters (git, tmux, json, markdown, subprocess)
```

- `domain/` — `StrEnum` vocabulary (`constants.py`), typed `Task`/`AgentRun`/`CompletionReport`
  dataclasses, `validation.py`, and `state_machine.py` (the allowed `TaskStatus` and
  `LifecyclePhase` transition tables plus the completion-status → task/run-status maps). **No I/O
  here.** New lifecycle rules belong in the transition tables, not in service code.
- `config/` — strict TOML parsing (unknown keys and unsupported `version` are rejected), discovery
  precedence `--config` → `$ALFRED_CONFIG` → nearest `.alfred/config.toml` walking upward,
  workspace initialization, and one-shot legacy JSON migration.
- `application/` — workflow services: `tasks`, `runs`, `dispatch`, `coordinator`, `notifications`,
  `knowledge`, `learner`, `sync`, `reports`.
- `ports/` — small `Protocol`s (`ProcessRunner`, `SessionBackend`, `Tracker`) that application code
  depends on. Tests substitute hand-written recording fakes for these, not mocks.
- `adapters/` — `state/json_store.py` (versioned atomic JSON), `git/` (worktrees, commits), `tmux.py`,
  `markdown/tracker.py`, `completion.py`, `process.py`.
- `cli/` — `parser.py` builds the entire argparse surface with **no disk or config access**;
  `main.py` dispatches `args.resource` to a handler module and converts
  `OSError/RuntimeError/ValueError/KeyError` into `ERROR: ...` plus exit code 1. Handlers receive an
  `AlfredServices` bundle.
- `bootstrap.py` — the only composition root. `build_services()` loads config and creates missing
  state files, but must not start processes, create worktrees, or touch the network.

### State and persistence

`JsonStateStore` owns exactly five documents (`tasks`, `runs`, `queue`, `notifications`, `events`),
each wrapped in a `schema_version` envelope (`STATE_VERSION = 1`) that is validated on every read.
Writes go through `atomic_write_json` (temp file in the same directory + `replace`).

A task mutation validates, persists the task, appends an event, then syncs the optional Markdown
tracker. **If tracker sync fails, task and event state are rolled back to their prior snapshots** —
preserve that ordering when adding mutations.

### Run orchestration

Two paths, both in `application/runs.py`:

1. `direct` — create/reuse worktrees, then dispatch the execution prompt.
2. `plan-execution` — dispatch a plan prompt with no worktrees, wait for
   `alfred run continue --task N`, then create worktrees and reuse the same tmux session for
   execution.

`AgentDispatcher` renders the agent's command **array** with `{task_number}`, `{task_title}`,
`{task_branch}`, `{phase}`, `{workdir}` placeholders, writes a prompt file under the private temp
directory, and starts or reuses a session named
`{session_prefix}-{task_number}-{agent_alias}`. When tmux is unavailable, `tmux_unavailable_policy`
decides between queueing the dispatch (`queue`) and raising (`error`).

Completion is actor-checked: the caller's `--actor` must match the assigned agent unless a manager
override is passed. The coordinator then validates and archives the report, raises a human-review
notification, and detects dead sessions without duplicating alerts.

### Safety invariants — do not weaken these

- Child processes are invoked as argument tuples; never build shell strings or pipelines.
- No implicit Git push. Network mutation happens only via `alfred worktree push`.
- Dirty worktrees are only removed with an explicit `--force`.
- Legacy migration requires an empty destination, writes a timestamped backup and an idempotency
  marker, and never deletes the source.
- Repository names, paths, branches, agent aliases, and session names are validated before use.

## Conventions

- Python 3.11+, `line-length = 100`, ruff rules `E,F,I,UP,B,SIM`, strict mypy on `src`.
- Every module, class, and public function carries a short docstring — match that density.
- Tests live under `tests/<layer>/` mirroring `src/alfred/<layer>/`. Prefer pure domain tests; use
  fakes at the process/session boundary; reserve real `git init` integration tests (see
  `tests/adapters/git/`) for genuine repository semantics.
- Commit messages use one configured bracket tag and an imperative summary: `[PATCH]` for tests,
  docs, maintenance, and behavior-neutral refactors; `[FIX]` for user-visible defects or safety
  corrections; `[FEATURE]` for new user-visible behavior. One coherent slice per commit — don't mix
  formatting, refactoring, and behavior.

## Gotchas

- The version lives in three places that must move together: `pyproject.toml`,
  `alfred.__version__`, and the assertions in `tests/test_package.py`.
- CI (`.github/workflows/ci.yml`) runs on macOS across Python 3.11–3.14 and pushes to `main`; the
  local default branch is `master`, so pushes there only get CI via pull request.
- The repository has **no license**. Do not add one, and do not prepare a publication step without
  owner approval — see `docs/releasing.md`.
- `.alfred/config.toml`, state, prompts, worktrees, and knowledge are gitignored and can contain
  sensitive project detail; keep them out of commits.
- Unit tests are necessary but not sufficient for a release candidate — `docs/end-to-end-testing.md`
  is the executable runbook with real tmux and disposable Git repositories.
