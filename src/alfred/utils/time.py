"""Configurable timezone-aware clock helpers."""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class Clock:
    """Produce consistent timestamps in one configured IANA timezone."""

    timezone: ZoneInfo

    @classmethod
    def from_name(cls, name: str) -> "Clock":
        """Create a clock or propagate the platform's unknown-zone error."""
        return cls(ZoneInfo(name))

    def now(self) -> datetime:
        """Return the current aware datetime."""
        return datetime.now(self.timezone)

    def timestamp(self) -> str:
        """Return an ISO-8601 timestamp suitable for state and logs."""
        return self.now().isoformat(timespec="seconds")
