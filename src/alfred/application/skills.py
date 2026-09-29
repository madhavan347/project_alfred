"""Editable per-phase skills that are appended to agent prompts."""

from pathlib import Path

from alfred.domain.constants import PromptPhase
from alfred.utils.files import atomic_write_text

MAX_SKILL_BYTES = 64 * 1024


class SkillService:
    """Read and replace the plan and execution skill files in a skills directory."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path(self, phase: PromptPhase | str) -> Path:
        """Return the skill file for a validated phase name."""
        return self.directory / f"{PromptPhase(phase).value}.md"

    def get(self, phase: PromptPhase | str) -> str:
        """Return a phase's skill text, or an empty string when none is defined."""
        path = self.path(phase)
        return path.read_text(encoding="utf-8").strip() if path.is_file() else ""

    def set(self, phase: PromptPhase | str, content: str) -> Path:
        """Create or replace a phase's skill after checking it is non-empty and bounded."""
        text = content.strip()
        if not text:
            raise ValueError("Skill content must not be empty")
        if len(text.encode("utf-8")) > MAX_SKILL_BYTES:
            raise ValueError(f"Skill content must be at most {MAX_SKILL_BYTES} bytes")
        path = self.path(phase)
        atomic_write_text(path, f"{text}\n")
        return path

    def remove(self, phase: PromptPhase | str) -> bool:
        """Delete a phase's skill so prompts fall back to the built-in instructions."""
        path = self.path(phase)
        existed = path.is_file()
        path.unlink(missing_ok=True)
        return existed
