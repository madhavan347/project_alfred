# Release checklist

Alfred is released under the MIT License.

## License gate

- Confirm `LICENSE` still contains the MIT text and that `pyproject.toml` declares
  `license = "MIT"` and `license-files = ["LICENSE"]`.
- Recheck that dependencies and any copied content are compatible with the MIT License.

## Technical gate

- Update the version in `pyproject.toml` and `alfred.__version__` together.
- Move relevant changelog entries from Unreleased into a dated version.
- Run Ruff check/format, strict mypy, pytest with coverage, and an isolated package build.
- Install the built wheel in a new virtual environment and smoke-test `alfred --version` and help.
- Complete the isolated [end-to-end release runbook](end-to-end-testing.md), including direct,
  plan-approval, queue recovery, stop/reopen, worktree, coordinator, tracker, learner, reporting,
  migration, and negative-path checks.
- Record the candidate revision, platform, Python versions, tester, results, and evidence location.
- Resolve or explicitly accept the documented lack of standalone tmux-session and worktree cleanup
  after a terminal run; do not leave the behavior ambiguous for users.
- Scan tracked files and reachable history for credentials, personal paths, private names, archives,
  generated runtime state, and stale identities.
- Confirm the default branch contains only the intended rewritten public history.

## Publication gate

- Review README, security reporting, contribution policy, and code of conduct.
- Enable branch protection and required macOS CI checks.
- Create a signed version tag only after the release commit is approved.
- Publish from the built artifacts without rebuilding them in a different environment.
- Verify the published metadata, install instructions, and entry point from a clean environment.
