# Release checklist

Alfred must not be published while the repository has no license.

## Ownership and legal gate

- Confirm every tracked file is owned by the publisher or covered by a compatible grant.
- Select a license with informed legal review.
- Add the exact `LICENSE` text and matching `pyproject.toml` metadata/classifier.
- Recheck dependency and copied-content license compatibility.

## Technical gate

- Update the version in `pyproject.toml` and `alfred.__version__` together.
- Move relevant changelog entries from Unreleased into a dated version.
- Run Ruff check/format, strict mypy, pytest with coverage, and an isolated package build.
- Install the built wheel in a new virtual environment and smoke-test `alfred --version` and help.
- Scan tracked files and reachable history for credentials, personal paths, private names, archives,
  generated runtime state, and stale identities.
- Confirm the default branch contains only the intended rewritten public history.

## Publication gate

- Review README, security reporting, contribution policy, and code of conduct.
- Enable branch protection and required macOS CI checks.
- Create a signed version tag only after the release commit is approved.
- Publish from the built artifacts without rebuilding them in a different environment.
- Verify the published metadata, install instructions, and entry point from a clean environment.
