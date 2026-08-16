"""Configurable learner-agent session workflow."""

from dataclasses import dataclass
from pathlib import Path

from alfred.config.models import AlfredConfig
from alfred.ports.session import SessionBackend
from alfred.utils.files import atomic_write_text


@dataclass(frozen=True, slots=True)
class LearnerStatus:
    """Current learner session state."""

    running: bool
    session_name: str
    agent_alias: str


class LearnerService:
    """Start and stop a configured agent that extracts reusable learnings."""

    SESSION_NAME = "alfred-learner"

    def __init__(self, config: AlfredConfig, sessions: SessionBackend) -> None:
        self.config = config
        self.sessions = sessions
        self.marker = config.runtime.state_directory / "learner.active"

    def start(self, agent_alias: str) -> bool:
        """Start the learner once and deliver its generic review prompt."""
        agent = self.config.agents.get(agent_alias)
        if agent is None:
            available = ", ".join(sorted(self.config.agents)) or "none"
            raise ValueError(f"Unknown agent {agent_alias!r}; configured agents: {available}")
        if not self.sessions.available():
            raise RuntimeError("The configured session backend is unavailable")
        if self.sessions.exists(self.SESSION_NAME):
            return False

        prompt_file = self.config.runtime.temp_directory / "prompts" / "learner.md"
        atomic_write_text(prompt_file, self._prompt())
        self.sessions.create(
            self.SESSION_NAME,
            self.config.workspace.root,
            agent.commands.direct,
        )
        self.sessions.send_prompt(self.SESSION_NAME, prompt_file)
        atomic_write_text(self.marker, f"{agent_alias}\n")
        return True

    def stop(self) -> bool:
        """Stop the learner if active and remove its marker."""
        if not self.sessions.available() or not self.sessions.exists(self.SESSION_NAME):
            self.marker.unlink(missing_ok=True)
            return False
        self.sessions.stop(self.SESSION_NAME)
        self.marker.unlink(missing_ok=True)
        return True

    def status(self) -> LearnerStatus:
        """Return backend state and the marker's configured agent alias."""
        alias = self.marker.read_text(encoding="utf-8").strip() if self.marker.is_file() else ""
        running = self.sessions.available() and self.sessions.exists(self.SESSION_NAME)
        return LearnerStatus(running, self.SESSION_NAME, alias)

    def _prompt(self) -> str:
        processed = self.config.runtime.temp_directory / "completions" / "processed"
        return "\n".join(
            [
                "# Alfred Knowledge Learner",
                "",
                "Review processed task completion reports and extract only new, reusable knowledge.",
                "Avoid duplicates, keep entries concise, and preserve source task references.",
                "",
                f"Processed completions: {processed}",
                f"Knowledge directory: {self.config.knowledge.directory}",
                "",
            ]
        )
