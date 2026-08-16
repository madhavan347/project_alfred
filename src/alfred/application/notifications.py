"""Persistent human-review notification workflow."""

from typing import Any
from uuid import uuid4

from alfred.adapters.state import JsonStateStore
from alfred.domain.models import Notification
from alfred.utils.time import Clock


class NotificationService:
    """Create, list, acknowledge, and clear persistent notifications."""

    def __init__(self, store: JsonStateStore, clock: Clock) -> None:
        self.store = store
        self.clock = clock

    def create(
        self,
        notification_type: str,
        task_number: int,
        details: dict[str, Any],
    ) -> Notification:
        """Persist one new notification."""
        notification = Notification(
            notification_id=uuid4().hex,
            notification_type=notification_type,
            task_number=task_number,
            created_at=self.clock.timestamp(),
            details=details,
        )
        notifications = self.store.notifications()
        notifications.append(notification.to_dict())
        self.store.save_notifications(notifications)
        return notification

    def pending(self) -> tuple[Notification, ...]:
        """Return unacknowledged notifications."""
        return tuple(notification for notification in self._all() if not notification.acknowledged)

    def acknowledge(self, task_number: int) -> int:
        """Acknowledge every notification for a task and return the count."""
        notifications = self._all()
        count = 0
        timestamp = self.clock.timestamp()
        for notification in notifications:
            if notification.task_number == task_number and not notification.acknowledged:
                notification.acknowledged = True
                notification.acknowledged_at = timestamp
                count += 1
        self.store.save_notifications([item.to_dict() for item in notifications])
        return count

    def clear_acknowledged(self) -> int:
        """Delete acknowledged notifications and return the removed count."""
        notifications = self._all()
        remaining = [item for item in notifications if not item.acknowledged]
        self.store.save_notifications([item.to_dict() for item in remaining])
        return len(notifications) - len(remaining)

    def _all(self) -> list[Notification]:
        return [Notification.from_dict(item) for item in self.store.notifications()]
