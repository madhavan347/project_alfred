# End-to-end release testing

Use this runbook for every release candidate. It combines automated quality gates, an isolated
installed-package test, real Git worktrees and pushes, real tmux dispatch, state/recovery checks,
and a final publication review. Run it on macOS because that is Alfred's declared platform and CI
environment.

Record the date, candidate revision, Python version, macOS version, tester, and evidence location.
Do not mark the candidate ready while any required check is skipped, failing, or unexplained.

## Release test record

| Field | Value |
|---|---|
| Candidate revision | |
| Candidate version | |
| Test date/time/timezone | |
| Tester | |
| macOS version and architecture | |
| Python versions | 3.11, 3.12, 3.13, 3.14 |
| Evidence/log location | |

## 1. Preconditions and hard blockers

- [ ] The candidate is tested from a dedicated clean checkout, not an active development worktree.
- [ ] The tracked diff and commit range contain only intended release content.
- [ ] Python 3.11–3.14, Git, and tmux are available for their respective checks.
- [ ] No real production repository or remote is used in the sandbox walkthrough.
- [ ] Ownership of every tracked file is confirmed.
- [ ] A license has been selected, its exact `LICENSE` file added, and package metadata updated.
- [ ] Security-reporting and release-hosting destinations are configured.

The license items are currently blocking. A green technical test does not authorize publication.

## 2. Automated quality and package gates

Create a clean development environment and run every repository check:

```console
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'

.venv/bin/ruff check alfred src tests
.venv/bin/ruff format --check alfred src tests
.venv/bin/mypy src
.venv/bin/pytest --cov=alfred --cov-report=term-missing
.venv/bin/python -m build
```

Acceptance criteria:

- [ ] Lint and formatting checks return 0.
- [ ] Strict mypy returns 0.
- [ ] All tests pass on Python 3.11, 3.12, 3.13, and 3.14.
- [ ] Branch-aware coverage is at least 85%.
- [ ] Both a source archive and wheel are created in `dist/`.
- [ ] CI independently passes the same matrix on `macos-latest`.

Install the exact wheel in a second clean environment. Do not rebuild between validation and
publication.

```console
python3 -m venv .release-smoke
.release-smoke/bin/python -m pip install dist/*.whl
.release-smoke/bin/alfred --version
.release-smoke/bin/alfred --help
.release-smoke/bin/python -m alfred --version
```

- [ ] The reported version matches `pyproject.toml`, `alfred.__version__`, the changelog heading,
      and the intended tag.
- [ ] Both console and module entry points work without the source tree on `PYTHONPATH`.

Set the installed binary path for the remaining examples:

```console
export ALFRED_E2E_BIN="$PWD/.release-smoke/bin/alfred"
```

## 3. Create an isolated Git and tmux sandbox

Create a disposable directory and two local Git repositories: one working repository and one bare
remote. Keep the printed path with the test evidence.

```console
export ALFRED_E2E_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/alfred-e2e.XXXXXX")"
mkdir -p "$ALFRED_E2E_ROOT/app"
git -C "$ALFRED_E2E_ROOT/app" init -b main
git -C "$ALFRED_E2E_ROOT/app" config user.name "Alfred E2E"
git -C "$ALFRED_E2E_ROOT/app" config user.email "alfred-e2e@example.invalid"
touch "$ALFRED_E2E_ROOT/app/README.md"
git -C "$ALFRED_E2E_ROOT/app" add README.md
git -C "$ALFRED_E2E_ROOT/app" commit -m "Initial fixture"
git init --bare "$ALFRED_E2E_ROOT/remote.git"
git -C "$ALFRED_E2E_ROOT/app" remote add origin "$ALFRED_E2E_ROOT/remote.git"

"$ALFRED_E2E_BIN" init --root "$ALFRED_E2E_ROOT"
```

Replace the generated config with this sandbox-only configuration. A copyable version is available
at [`docs/examples/e2e-config.toml`](examples/e2e-config.toml).

```toml
version = 1

[alfred]
timezone = "UTC"
state_directory = ".alfred/state"
temp_directory = ".alfred/tmp"
worktree_directory = ".alfred/worktrees"
session_prefix = "alfred-e2e"
tmux_unavailable_policy = "queue"

[workspace]
root = ".."

[[repositories]]
name = "app"
path = "app"
default_branch = "main"
remote = "origin"
selected_by_default = true

[agents.recorder]
runtime_target = "local-test"

[agents.recorder.commands]
direct = ["tail", "-f", "/dev/null"]
plan = ["tail", "-f", "/dev/null"]
execution = ["tail", "-f", "/dev/null"]

[trackers.markdown]
enabled = true
canonical = "tracking/tasks.md"
agents = "tracking/agents.md"
daily_notes = "tracking/daily"

[commit.tags]
patch = "[PATCH]"
fix = "[FIX]"
feature = "[FEATURE]"

[knowledge]
directory = ".alfred/knowledge"
required_completion_entries = 1
```

Create the configured tracker directory:

```console
mkdir -p "$ALFRED_E2E_ROOT/tracking/daily"
export ALFRED_CONFIG="$ALFRED_E2E_ROOT/.alfred/config.toml"
```

Acceptance criteria:

- [ ] `alfred --version` works from outside the source checkout.
- [ ] `alfred report velocity` initializes state and prints `Completed 0/0`.
- [ ] Invalid config keys, an invalid timezone, and a missing explicit config each produce a concise
      non-zero error without a traceback.
- [ ] Running `init` again without `--force` refuses to overwrite the config.

## 4. Direct task from creation through archive

Create and dispatch a direct task:

```console
"$ALFRED_E2E_BIN" task create \
  --task 101 \
  --title "Direct flow" \
  --description "Exercise direct execution" \
  --priority P1 \
  --branch e2e/direct-101 \
  --repos app \
  --assign recorder

"$ALFRED_E2E_BIN" run trigger --tasks 101
"$ALFRED_E2E_BIN" run list --status running
"$ALFRED_E2E_BIN" run sessions --task 101
"$ALFRED_E2E_BIN" run attach --task 101
"$ALFRED_E2E_BIN" worktree status --task 101
```

Verify:

- [ ] Task, run, queue, and event JSON remain valid schema-version-1 documents.
- [ ] Branch `e2e/direct-101` and `.alfred/worktrees/task-101/app` exist.
- [ ] The tmux session name starts with `alfred-e2e-101-recorder`.
- [ ] The prompt names the task, execution phase, branch, and exact worktree path.
- [ ] `run attach` prints a correct command without attaching the test shell.
- [ ] Task and agent tracker rows exist and the daily note contains the event.

Exercise actor checks and progress:

```console
"$ALFRED_E2E_BIN" run event \
  --task 101 --type progress --note "Direct work started" --actor agent:recorder

"$ALFRED_E2E_BIN" run event \
  --task 101 --type review_requested --note "Ready" --actor agent:recorder
```

- [ ] An event from `agent:wrong` fails and does not mutate task or event state.
- [ ] A valid event moves the task to the documented status.

Commit and explicitly push the sandbox branch:

```console
touch "$ALFRED_E2E_ROOT/.alfred/worktrees/task-101/app/e2e-change.txt"
"$ALFRED_E2E_BIN" worktree commit \
  --task 101 --type feature --message "Exercise direct flow"
"$ALFRED_E2E_BIN" worktree push --task 101 --repo app
git --git-dir "$ALFRED_E2E_ROOT/remote.git" show-ref e2e/direct-101
```

- [ ] The exact commit subject is `[FEATURE] Exercise direct flow`.
- [ ] No remote mutation happens before `worktree push`.
- [ ] The bare remote contains only the explicitly pushed task branch.

Add the knowledge entry required by the completion gate, complete, and process the handoff:

```console
"$ALFRED_E2E_BIN" knowledge add \
  --task 101 \
  --category patterns \
  --title "Direct flow fixture" \
  --content "The direct release test uses a local recorder agent." \
  --agent recorder \
  --modules app

"$ALFRED_E2E_BIN" run complete \
  --task 101 \
  --result success \
  --note "Direct flow passed" \
  --actor agent:recorder

"$ALFRED_E2E_BIN" coordinator once
"$ALFRED_E2E_BIN" notifications
```

- [ ] The pending completion is moved to `processed`, not `invalid`.
- [ ] The notification includes success, summary, agent, repository, and no knowledge validation
      issue.
- [ ] A second coordinator cycle does not duplicate the notification.

Finish the human-controlled lifecycle:

```console
"$ALFRED_E2E_BIN" task review \
  --task 101 --decision approved --note "E2E review passed"
"$ALFRED_E2E_BIN" task merge --task 101 --mr local/e2e-101
"$ALFRED_E2E_BIN" task deploy --task 101 --env sandbox --result passed
"$ALFRED_E2E_BIN" task archive --task 101 --note "E2E lifecycle complete"
"$ALFRED_E2E_BIN" notifications ack --task 101
"$ALFRED_E2E_BIN" notifications clear
```

- [ ] Final status is `Completed` and lifecycle phase is `archived`.
- [ ] Attempting an invalid terminal transition fails without state corruption.

## 5. Plan-approval, block, failure, and reopen

```console
"$ALFRED_E2E_BIN" task create \
  --task 102 \
  --title "Plan flow" \
  --description "Exercise approval and recovery" \
  --branch e2e/plan-102 \
  --mode plan-execution \
  --repos app \
  --assign recorder

"$ALFRED_E2E_BIN" run trigger --tasks 102
"$ALFRED_E2E_BIN" run event \
  --task 102 --type plan_completed --note "Plan ready" --actor agent:recorder
"$ALFRED_E2E_BIN" run continue --task 102 --note "Plan accepted"
```

- [ ] No task-102 worktree exists during planning.
- [ ] Planning state changes `pending -> started -> completed`.
- [ ] Continue creates the worktree and reuses the same session name.
- [ ] A second continue is rejected.

Exercise an active blocker and recovery:

```console
"$ALFRED_E2E_BIN" run event \
  --task 102 --type blocked --note "Fixture unavailable" --actor agent:recorder
"$ALFRED_E2E_BIN" run event \
  --task 102 --type unblocked --note "Fixture restored" --actor agent:recorder
"$ALFRED_E2E_BIN" run complete \
  --task 102 --result failed --note "First attempt failed" --actor agent:recorder
"$ALFRED_E2E_BIN" coordinator once
"$ALFRED_E2E_BIN" run reopen --task 102
```

- [ ] Block/unblock changes task status without losing the active attempt.
- [ ] Failed completion makes that run terminal and leaves the task `In Progress`.
- [ ] Reopen creates a new run ID in execution phase and reuses valid worktrees.

Stop the reopened attempt and verify safe cleanup behavior:

```console
"$ALFRED_E2E_BIN" run stop \
  --task 102 --reason "Testing stop without cleanup" --cleanup no
"$ALFRED_E2E_BIN" run reopen --task 102
"$ALFRED_E2E_BIN" run stop \
  --task 102 --reason "Testing explicit cleanup" --cleanup yes --force
```

- [ ] Stop closes the live session and resets the task to `Pending`.
- [ ] Without cleanup, worktrees remain.
- [ ] Dirty cleanup without `--force` fails; forced cleanup succeeds only when explicitly supplied.

## 6. Queue fallback and dead-session notification

First confirm the installed tmux path. On common Homebrew installations, running Alfred with a
restricted `PATH=/usr/bin:/bin` hides tmux while retaining system Git.

Create task 103, hide tmux for its trigger, and inspect the queue:

```console
"$ALFRED_E2E_BIN" task create \
  --task 103 \
  --title "Queue flow" \
  --description "Exercise missing tmux" \
  --branch e2e/queue-103 \
  --repos app \
  --assign recorder

PATH=/usr/bin:/bin "$ALFRED_E2E_BIN" run trigger --tasks 103
"$ALFRED_E2E_BIN" run list --status queued
PATH=/usr/bin:/bin "$ALFRED_E2E_BIN" run stop \
  --task 103 --reason "Replace queued attempt" --cleanup no
"$ALFRED_E2E_BIN" run trigger --tasks 103
```

- [ ] Missing tmux with queue policy persists a queued run and prompt without a session.
- [ ] Stop succeeds without tmux and removes the task from `queue.json`.
- [ ] Retrying with tmux creates one current running attempt.

Kill only task 103's sandbox tmux session, then run the coordinator twice:

```console
tmux kill-session -t alfred-e2e-103-recorder
"$ALFRED_E2E_BIN" coordinator once
"$ALFRED_E2E_BIN" coordinator once
"$ALFRED_E2E_BIN" notifications
```

- [ ] Exactly one `session_died` notification is pending.
- [ ] Acknowledge and clear affect only the requested task and acknowledged records.

## 7. Tracker, reporting, knowledge, and learner

```console
"$ALFRED_E2E_BIN" sync validate
"$ALFRED_E2E_BIN" sync drift-report --task 101
"$ALFRED_E2E_BIN" sync apply --task 101

"$ALFRED_E2E_BIN" report today
"$ALFRED_E2E_BIN" report risk
"$ALFRED_E2E_BIN" report dependency
"$ALFRED_E2E_BIN" report velocity

"$ALFRED_E2E_BIN" knowledge list
"$ALFRED_E2E_BIN" learner start --agent recorder
"$ALFRED_E2E_BIN" learner status
"$ALFRED_E2E_BIN" learner attach
"$ALFRED_E2E_BIN" learner stop
```

- [ ] Sync validation returns 0 when all rows and paths exist.
- [ ] Removing a task or agent row makes validation return 1; apply restores it.
- [ ] Reports match manually inspected task JSON and use deterministic ordering.
- [ ] Knowledge paths and content match the requested category and task.
- [ ] Learner start is idempotent, attach prints the correct command, and stop removes its marker.

## 8. Migration in a separate empty destination

Migration refuses a non-empty destination, so use another initialized workspace. Prepare legacy
`tasks.json`, `runs.json`, `queue.json`, and `agent_map.json` fixtures containing no sensitive data.

```console
export ALFRED_MIGRATION_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/alfred-migration.XXXXXX")"
"$ALFRED_E2E_BIN" init --root "$ALFRED_MIGRATION_ROOT"
"$ALFRED_E2E_BIN" \
  --config "$ALFRED_MIGRATION_ROOT/.alfred/config.toml" \
  migrate --source /path/to/synthetic/legacy-runtime
```

- [ ] Valid tasks, runs, and queue items are normalized into versioned destination documents.
- [ ] Every recognized source file has an unchanged backup copy.
- [ ] The source directory remains unchanged.
- [ ] Agent commands are emitted only as a reviewable TOML fragment.
- [ ] A second invocation reports `already migrated` and changes no migrated state.
- [ ] Invalid JSON and a non-empty destination fail before overwriting destination data.

## 9. Negative and safety matrix

Verify each failure returns non-zero, prints an actionable error, and leaves prior state intact.

| Case | Expected result |
|---|---|
| task number is zero, title/description empty, or priority invalid | full validation message |
| enabled worktree has no branch or no repository selection | dispatch rejected |
| dependency contains self or duplicates | task rejected |
| unknown agent, repository, commit type, or command placeholder | rejected before external mutation |
| wrong completion/event actor | actor requirement shown; no mutation |
| plan continue on direct, pending, or already-continued task | rejected |
| trigger with `--parallel 0` | rejected |
| existing worktree branch does not match task branch | rejected |
| local task branch has diverged from default branch | rejected |
| clean worktree commit | `Nothing to commit`; no empty commit |
| dirty worktree cleanup without force | Git failure; worktree retained |
| tracker write fails partway | task/event and written tracker files rolled back |
| malformed completion | quarantined under `invalid`; polling continues |
| corrupt or wrong-version state JSON | rejected and not replaced |
| migration source invalid or destination non-empty | no migrated destination writes |
| `tmux_unavailable_policy = "error"` without tmux | dispatch rejected rather than queued |

## 10. Security, privacy, and publication checks

Inspect tracked files and the release commit range for credentials, tokens, private hostnames,
absolute personal paths, employer/customer data, prompts, completions, runtime archives, generated
worktrees, editor files, and built distributions.

```console
git status --short
git diff --check
git ls-files
git log --oneline --decorate --max-count=20
```

- [ ] `.alfred/config.toml`, state, prompts, completions, worktrees, and private knowledge are absent
      from the release unless explicitly sanitized and intended.
- [ ] Package metadata has the intended author, description, Python requirement, classifiers,
      license expression/file, version, and README rendering.
- [ ] Dependency and copied-content licenses are compatible with the selected project license.
- [ ] The changelog contains a dated release section with no unresolved release-critical items.
- [ ] Security reporting, contribution policy, code of conduct, and repository links are correct.
- [ ] The release tag will point to the exact tested commit.

## 11. Known release limitation to decide

Alfred exposes worktree cleanup through `run stop --cleanup`; it does not currently expose a
standalone cleanup command after a run is terminal. Completion also marks the persisted session
inactive without stopping the underlying tmux session, which permits later reuse but requires manual
cleanup after the final archive. Before the first release, either add and test explicit terminal
session/worktree cleanup or document the accepted manual tmux and Git cleanup procedure as a
supported limitation. Do not silently delete a completed task's worktree.

## 12. Dispose of the sandbox

Retain any required evidence first. List matching sessions and inspect both temporary roots before
removing them:

```console
tmux list-sessions -F '#{session_name}' | grep '^alfred-e2e-' || true
find "$ALFRED_E2E_ROOT" -maxdepth 3 -print
find "$ALFRED_MIGRATION_ROOT" -maxdepth 3 -print
```

Stop only the sessions created by this run. Then remove only the exact temporary directories printed
and reviewed above. Do not use a broad path, glob, home directory, or workspace root as a cleanup
target.

## 13. Exit criteria

The candidate is technically ready only when:

- [ ] all automated, package, lifecycle, recovery, negative, and privacy checks above pass;
- [ ] every failure found during the walkthrough has a recorded fix or explicit release decision;
- [ ] the exact built artifacts are retained with hashes and are the artifacts to be published;
- [ ] a clean-machine install of those artifacts passes version, help, initialization, and direct
      task smoke tests;
- [ ] ownership and licensing blockers are closed;
- [ ] the owner signs off on the evidence and exact release commit.

After publication, install from the public index in a new environment and repeat the entry-point,
version, help, initialization, and one sandbox direct-flow smoke test.
