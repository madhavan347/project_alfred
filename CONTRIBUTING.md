# Contributing

Contributions are welcome through pull requests. By contributing, you agree that your
contribution is licensed under the project's [MIT License](LICENSE). This guide defines the
expected workflow.

## Development setup

```console
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Use a focused branch and keep private `.alfred` state, agent settings, credentials, prompts, and
generated worktrees out of commits.

## Incremental workflow

Each change should follow this loop:

1. Define one observable outcome and its acceptance checks.
2. Add or update the smallest relevant test.
3. Implement only that outcome.
4. Run focused tests, then the complete quality suite.
5. Review the staged diff for scope, secrets, generated files, and accidental personal paths.
6. Commit the coherent slice before beginning the next one.

Avoid mixing formatting, refactoring, features, and behavior fixes in one commit. Preserve existing
interfaces unless the change explicitly includes a migration path.

## Commit messages

Use one configured bracket tag followed by an imperative summary:

```text
[PATCH] Clarify migration failure output
[FIX] Reject mismatched worktree branches
[FEATURE] Add repository selection command
```

- `[PATCH]` is for tests, documentation, maintenance, and behavior-neutral refactoring.
- `[FIX]` is for a user-visible defect or safety correction.
- `[FEATURE]` is for new user-visible behavior.

Keep the first line concise. Add a body only when the reason, compatibility impact, or migration
detail is not clear from the diff.

## Required checks

```console
.venv/bin/ruff check alfred src tests
.venv/bin/ruff format --check alfred src tests
.venv/bin/mypy src
.venv/bin/pytest --cov=alfred --cov-report=term-missing
.venv/bin/python -m build
```

New workflow behavior needs tests at the lowest useful layer. Prefer pure domain tests, use fakes
for process/session boundaries, and reserve real Git integration tests for repository semantics.

## Pull requests

Pull requests should explain the outcome, list validation performed, identify migration or security
impact, and call out any intentional follow-up. Do not include runtime archives, customer or employer
data, generated distributions, unrelated worktree changes, or a license change without owner approval.
