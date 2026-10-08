"""Rebuild this checkout's frontend and report whether the running server is out of date.

Updating never touches the network: it rebuilds what is already on disk with the installed
``node_modules``. Bringing the code itself up to date (``git pull``, switching branches) stays a
manual step. Python packages are editable installs, so a restart is enough to load new Python code.
"""

import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import alfred

import alfred_ui

UI_ROOT = Path(alfred_ui.__file__).resolve().parents[2]
BUILD_COMMAND = ("npm", "run", "build")
BUILD_TIMEOUT = 600
OUTPUT_LIMIT = 20_000
FRONTEND_SOURCES = ("src", "index.html", "package.json", "package-lock.json", "vite.config.ts")


@dataclass
class Updater:
    """Rebuild the frontend of one checkout and describe the running server."""

    ui_root: Path = UI_ROOT
    static_directory: Path | None = None
    command: Sequence[str] = BUILD_COMMAND
    restart: Callable[[], None] | None = None
    started_at: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def web(self) -> Path:
        """The frontend source directory of this checkout."""
        return self.ui_root / "web"

    @property
    def default_static(self) -> Path:
        """Where ``npm run build`` writes the frontend."""
        return self.ui_root / "src" / "alfred_ui" / "static"

    def rebuild_problem(self) -> str:
        """Return why the frontend cannot be rebuilt here, or an empty string."""
        if not (self.web / "package.json").is_file():
            return f"No frontend sources at {self.web}; this installation is not a checkout"
        if not (self.web / "node_modules").is_dir():
            return f"Run npm ci in {self.web} first; the update never downloads packages"
        if shutil.which(self.command[0]) is None:
            return f"{self.command[0]} is not on this server's PATH"
        static = self.static_directory
        if static is not None and static.resolve() != self.default_static.resolve():
            return f"The server serves {static} (--static-dir), not this checkout's build"
        return ""

    def describe(self) -> dict[str, Any]:
        """Return the running versions, the checkout, and whether a rebuild or restart is due."""
        static = self.static_directory or self.default_static
        index = static / "index.html"
        built = index.stat().st_mtime if index.is_file() else None
        sources = newest_mtime(self.web / name for name in FRONTEND_SOURCES)
        python = newest_mtime(
            [Path(alfred_ui.__file__).parent, Path(alfred.__file__).parent], suffix=".py"
        )
        return {
            "versions": {"alfred": alfred.__version__, "ui": alfred_ui.__version__},
            "checkout": str(self.ui_root.parent),
            "packages": {
                "alfred": str(Path(alfred.__file__).parent),
                "alfred_ui": str(Path(alfred_ui.__file__).parent),
            },
            "git": git_state(self.ui_root),
            "started_at": _iso(self.started_at),
            "frontend": {
                "static_directory": str(static),
                "built_at": _iso(built) if built else "",
                "sources_changed_at": _iso(sources) if sources else "",
                "stale": built is None or (sources is not None and sources > built),
            },
            "backend": {
                "changed_at": _iso(python) if python else "",
                "stale": python is not None and python > self.started_at,
            },
            "rebuild": {"available": not self.rebuild_problem(), "reason": self.rebuild_problem()},
            "restart": {
                "available": self.restart is not None,
                "reason": ""
                if self.restart is not None
                else "Only a server started with the alfred-ui command can restart itself",
            },
        }

    def rebuild(self) -> dict[str, Any]:
        """Run the frontend build as an argument tuple and return its combined output."""
        if problem := self.rebuild_problem():
            raise ValueError(problem)
        if not self._lock.acquire(blocking=False):
            raise ValueError("A rebuild is already running")
        started = time.monotonic()
        try:
            completed = subprocess.run(
                tuple(self.command),
                cwd=self.web,
                capture_output=True,
                text=True,
                timeout=BUILD_TIMEOUT,
                check=False,
                env={**os.environ, "CI": "1", "NO_COLOR": "1"},
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"The frontend build took longer than {BUILD_TIMEOUT}s") from exc
        finally:
            self._lock.release()
        output = (completed.stdout + completed.stderr)[-OUTPUT_LIMIT:]
        ok = completed.returncode == 0
        return {
            "ok": ok,
            "message": "Frontend rebuilt"
            if ok
            else f"The frontend build failed (exit {completed.returncode}); nothing was restarted",
            "output": output,
            "seconds": round(time.monotonic() - started, 1),
        }

    def request_restart(self) -> dict[str, Any]:
        """Ask the server to restart shortly, after this response has been sent."""
        if self.restart is None:
            raise ValueError("Only a server started with the alfred-ui command can restart itself")
        timer = threading.Timer(0.5, self.restart)
        timer.daemon = True
        timer.start()
        return {"ok": True, "message": "Restarting the server", "started_at": _iso(self.started_at)}


def newest_mtime(paths: Iterable[Path], *, suffix: str = "") -> float | None:
    """Return the newest modification time among files under the given paths."""
    newest: float | None = None
    for path in paths:
        if path.is_file():
            candidates: Iterable[Path] = [path]
        elif path.is_dir():
            candidates = (item for item in path.rglob(f"*{suffix}") if item.is_file())
        else:
            continue
        for item in candidates:
            if "node_modules" in item.parts or "__pycache__" in item.parts:
                continue
            mtime = item.stat().st_mtime
            newest = mtime if newest is None else max(newest, mtime)
    return newest


def git_state(directory: Path) -> dict[str, Any]:
    """Return the checkout's branch, commit, and uncommitted file count, when it is a Git repo."""

    def git(*arguments: str) -> str:
        completed = subprocess.run(
            ("git", "-C", str(directory), *arguments),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return completed.stdout.strip() if completed.returncode == 0 else ""

    try:
        commit = git("rev-parse", "--short", "HEAD")
        if not commit:
            return {"available": False}
        changes = git("status", "--porcelain")
        return {
            "available": True,
            "branch": git("branch", "--show-current"),
            "commit": commit,
            "subject": git("log", "-1", "--format=%s"),
            "changes": len(changes.splitlines()) if changes else 0,
        }
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False}


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, UTC).isoformat()
