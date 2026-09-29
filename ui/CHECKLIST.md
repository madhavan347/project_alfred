# UI merge checklist

The UI lives on the `feature_ui_changes` branch until it has been tested and audited. Complete every
item before merging it into `master`.

## Continuous integration

- [ ] Add a UI job to `.github/workflows/ci.yml` that creates `ui/.venv`, installs
      `-e .. -e '.[dev]'`, installs tmux, and runs `ruff check src tests scripts`,
      `ruff format --check src tests scripts`, `mypy`, and `pytest --cov=alfred_ui`.
- [ ] Add a frontend job for `ui/web`: `npm ci`, `npm run typecheck`, `npm test`, and
      `npm run build`.
- [ ] Decide whether the Playwright end-to-end suite runs in CI or stays a local release check.
- [ ] Add npm updates for `/ui/web` to `.github/dependabot.yml`.
- [ ] Make `tests/test_adapters.py::test_bind_moves_past_busy_ports` independent of the default
      port: it fails whenever something else already listens on 8765.

## Security

- [ ] Complete a security audit of the UI server and frontend before merging, and fix its findings.
      Report anything found through private vulnerability reporting, not in public issues.

## License and packaging

- [ ] Add a copy of the MIT `LICENSE` under `ui/` and declare `license = "MIT"` and
      `license-files = ["LICENSE"]` in `ui/pyproject.toml` (with `setuptools>=77`).
- [ ] Add `"license": "MIT"` to `ui/web/package.json`.

## Documentation

- [ ] Link the UI from the root `README.md`, and describe it in `CONTRIBUTING.md` (required checks)
      and `CHANGELOG.md`.
