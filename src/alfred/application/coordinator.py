"""Lightweight completion and session-health coordinator."""

from dataclasses import dataclass
from threading import Event

from alfred.adapters.completion import CompletionFileStore
from alfred.adapters.state import JsonStateStore
from alfred.application.notifications import NotificationService
from alfred.config.models import AlfredConfig
from alfred.domain.constants import CompletionStatus, RunStatus
from alfred.domain.models import AgentRun, CompletionReport
from alfred.ports.session import SessionBackend

COMPLETION_NOTIFICATION_TYPES = {
    CompletionStatus.SUCCESS: "task_completed",
    CompletionStatus.FAILED: "task_failed",
    CompletionStatus.BLOCKED: "task_blocked",
}


@dataclass(frozen=True, slots=True)
class CoordinatorCycle:
    """Counts produced by one deterministic coordinator poll."""

    processed: int = 0
    invalid: int = 0
    dead_sessions: int = 0


class Coordinator:
    """Process completion files and monitor active task sessions."""

    def __init__(
        self,
        config: AlfredConfig,
        store: JsonStateStore,
        completions: CompletionFileStore,
        notifications: NotificationService,
        sessions: SessionBackend,
    ) -> None:
        self.config = config
        self.store = store
        self.completions = completions
        self.notifications = notifications
        self.sessions = sessions

    def process_once(self) -> CoordinatorCycle:
        """Process all current inputs once without sleeping."""
        processed = 0
        invalid = 0
        for path in self.completions.pending():
            try:
                report = self.completions.read(path)
            except (ValueError, TypeError, KeyError):
                self.completions.mark_invalid(path)
                invalid += 1
                continue
            issues = self._completion_issues(report)
            self.notifications.create(
                COMPLETION_NOTIFICATION_TYPES[report.status],
                report.task_number,
                {
                    "status": report.status.value,
                    "summary": report.summary,
                    "repositories": list(report.repositories),
                    "commits": list(report.commits),
                    "agent": report.agent,
                    "validation_issues": issues,
                },
            )
            self.completions.mark_processed(path)
            processed += 1
        dead_sessions = self._check_session_health()
        return CoordinatorCycle(processed, invalid, dead_sessions)

    def run(self, stop: Event, *, poll_interval: float = 5.0) -> None:
        """Poll until the supplied event requests shutdown."""
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        while not stop.is_set():
            self.process_once()
            stop.wait(poll_interval)

    def _completion_issues(self, report: CompletionReport) -> list[str]:
        issues: list[str] = []
        if not report.summary.strip():
            issues.append("summary is required")
        required = self.config.knowledge.required_completion_entries
        # Blocked and failed reports record why work stopped; only delivered work needs knowledge.
        if report.status == CompletionStatus.SUCCESS and report.knowledge_entries < required:
            issues.append(
                f"knowledge_entries must be at least {required}; got {report.knowledge_entries}"
            )
        return issues

    def _check_session_health(self) -> int:
        if not self.sessions.available():
            return 0
        active = set(self.sessions.list(self.config.runtime.session_prefix))
        existing = {
            (item.notification_type, item.task_number, item.details.get("session_name"))
            for item in self.notifications.pending()
        }
        created = 0
        records = self.store.runs()
        marked = False
        for raw in records:
            run = AgentRun.from_dict(raw)
            if (
                run.run_status != RunStatus.RUNNING
                or not run.session_name
                or run.session_status == "dead"
                or run.session_name in active
            ):
                continue
            # Record the death on the run so acknowledging the alert does not re-arm it.
            raw["session_status"] = "dead"
            marked = True
            if ("session_died", run.task_number, run.session_name) in existing:
                continue
            self.notifications.create(
                "session_died",
                run.task_number,
                {
                    "session_name": run.session_name,
                    "message": "The agent session ended while the run remained active.",
                },
            )
            created += 1
        if marked:
            self.store.save_runs(records)
        return created
