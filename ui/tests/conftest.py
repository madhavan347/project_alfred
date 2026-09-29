"""Shared fixtures: disposable workspaces with real Git and an isolated tmux server."""

import importlib.util
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType
from typing import TypeVar

import pytest
from fastapi.testclient import TestClient

from alfred_ui.app import create_app
from alfred_ui.cli import expose_alfred_to_sessions
from alfred_ui.live import LiveHub
from alfred_ui.security import TokenPolicy
from alfred_ui.tmux_inspector import TmuxInspector
from alfred_ui.workspace import WorkspaceContext

UI_ROOT = Path(__file__).resolve().parents[1]
TOKEN = "test-token"
T = TypeVar("T")


def _load_sandbox() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "make_sandbox", UI_ROOT / "scripts" / "make_sandbox.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SANDBOX = _load_sandbox()


@pytest.fixture(scope="session", autouse=True)
def isolated_tmux() -> Iterator[Path]:
    """Point every tmux command in the test session at a private socket directory."""
    # Unix socket paths are short on macOS, so this cannot live under pytest's tmp_path.
    directory = Path(tempfile.mkdtemp(prefix="auit-", dir=tempfile.gettempdir()))
    previous = {key: os.environ.get(key) for key in ("TMUX_TMPDIR", "TMUX", "PATH")}
    os.environ["TMUX_TMPDIR"] = str(directory)
    os.environ.pop("TMUX", None)
    # As alfred-ui does at startup: agent sessions must be able to run this installation's alfred.
    expose_alfred_to_sessions()
    yield directory
    subprocess.run(["tmux", "kill-server"], capture_output=True, check=False)
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    shutil.rmtree(directory, ignore_errors=True)


@pytest.fixture
def prefix() -> str:
    """A unique session prefix so tests never see each other's sessions."""
    return f"t{uuid.uuid4().hex[:8]}"


@pytest.fixture
def workspace(tmp_path: Path, prefix: str) -> Path:
    """Create a sandbox workspace like scripts/make_sandbox.py and return its config path."""
    root = tmp_path / "workspace"
    root.mkdir()
    SANDBOX.create_repository(root, "app", remote=True)
    SANDBOX.create_repository(root, "library", remote=True)
    (root / "tracking" / "daily").mkdir(parents=True)
    from alfred.config.initializer import initialize_workspace

    config = initialize_workspace(root)
    text = SANDBOX.config_text(
        prefix, str(UI_ROOT / ".venv" / "bin" / "python"), real_agents=False, second_repo=True
    )
    config.write_text(text, encoding="utf-8")
    return config


@pytest.fixture
def context(workspace: Path) -> WorkspaceContext:
    return WorkspaceContext(workspace)


@pytest.fixture
def client(context: WorkspaceContext) -> Iterator[TestClient]:
    """A signed-in API client for the workspace, with the live hub running."""
    inspector = TmuxInspector()
    hub = LiveHub(
        context, inspector, poll_interval=0.05, session_interval=0.05, worktree_interval=0.2
    )
    app = create_app(
        context,
        policy=TokenPolicy(token=TOKEN),
        allowed_hosts=("testserver",),
        static_directory=None,
        inspector=inspector,
        hub=hub,
    )
    with TestClient(app, headers={"X-Alfred-Token": TOKEN}) as test_client:
        yield test_client


def wait_for(predicate: Callable[[], T], timeout: float = 20.0, interval: float = 0.1) -> T:
    """Poll until ``predicate`` returns a truthy value, then return it."""
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:
            return value
        if time.monotonic() > deadline:
            raise AssertionError("Timed out waiting for the condition")
        time.sleep(interval)
