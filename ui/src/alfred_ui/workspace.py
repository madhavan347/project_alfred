"""Active Alfred workspace selection and per-request service construction.

Services are rebuilt for every request, exactly as each CLI invocation builds them, so edits made
by agents, the CLI, or a text editor are always observed without restarting the UI server.
"""

import threading
from pathlib import Path

from alfred.bootstrap import AlfredServices, build_services
from alfred.config.loader import ConfigError, discover_config, load_config
from alfred.config.models import AlfredConfig
from alfred.utils.time import Clock


class NoWorkspaceError(RuntimeError):
    """Raised when an operation needs a workspace but none is open."""


class WorkspaceContext:
    """Track the open configuration and serialize state-changing operations."""

    def __init__(self, config_path: Path | None = None, *, start: Path | None = None) -> None:
        # Alfred state has no file locks, so the UI applies its own mutations one at a time.
        self.mutation_lock = threading.RLock()
        self._lock = threading.Lock()
        self._config_path: Path | None = None
        self._generation = 0
        self.discovery_error = ""
        try:
            self._config_path = discover_config(start, explicit=config_path)
        except ConfigError as exc:
            if config_path is not None:
                raise
            self.discovery_error = str(exc)

    @property
    def config_path(self) -> Path | None:
        """Return the open configuration path, if any."""
        with self._lock:
            return self._config_path

    @property
    def generation(self) -> int:
        """Return a counter that changes whenever a different workspace is opened."""
        with self._lock:
            return self._generation

    def require_path(self) -> Path:
        """Return the configuration path or raise an actionable error."""
        path = self.config_path
        if path is None:
            raise NoWorkspaceError(
                "No Alfred workspace is open. Open an existing .alfred/config.toml or "
                "initialize a new workspace in Settings."
            )
        return path

    def services(self) -> AlfredServices:
        """Build configured services, initializing any missing state documents."""
        return build_services(config_path=self.require_path())

    def config(self) -> AlfredConfig:
        """Load the configuration without touching state."""
        config = load_config(self.require_path())
        Clock.from_name(config.runtime.timezone)
        return config

    def open(self, path: Path, *, validate: bool = True) -> Path:
        """Switch to another workspace configuration, validating it unless asked not to.

        Opening without validation lets an operator repair a broken configuration in the editor.
        """
        resolved = discover_config(explicit=path)
        if validate:
            config = load_config(resolved)
            Clock.from_name(config.runtime.timezone)
        with self._lock:
            self._config_path = resolved
            self._generation += 1
            self.discovery_error = ""
        return resolved
