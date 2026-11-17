from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from uuid import uuid4

from labvalidation.models import ResultFlag, AlertStatus


class AlertCreationError(ValueError):
    """Raised when a critical alert cannot be created safely."""


class NotificationStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


@dataclass(frozen=True)
class NotificationEvent:
    event_id: str
    alert_id: str
    recipient_role: str
    attempted_at: datetime
    status: NotificationStatus
    detail: str = ""


@dataclass
class CriticalAlertRecord:
    alert_id: str
    result_id: str
    flag: ResultFlag
    created_at: datetime
    status: AlertStatus
    notifications: list[NotificationEvent] = field(default_factory=list)


class CriticalAlertRegistry:
    def __init__(self):
        self._alerts_by_result = {}
        self._alerts_by_id = {}
        self._lock = RLock()

    def create_alert(self, result_id: str, flag: ResultFlag,
                     created_at: datetime | None = None) -> CriticalAlertRecord | None:
        if not isinstance(result_id, str) or not result_id.strip():
            raise AlertCreationError("Result ID must be non-empty.")

        if flag not in (ResultFlag.CRITICAL_LOW, ResultFlag.CRITICAL_HIGH):
            return None

        created = created_at or datetime.now(timezone.utc)
        if not isinstance(created, datetime):
            raise AlertCreationError("Creation time must be a datetime.")
        if created.tzinfo is None or created.utcoffset() is None:
            raise AlertCreationError("Creation time must include a timezone.")

        with self._lock:
            existing = self._alerts_by_result.get(result_id)
            if existing is not None:
                return existing

            alert = CriticalAlertRecord(
                alert_id=str(uuid4()),
                result_id=result_id,
                flag=flag,
                created_at=created,
                status=AlertStatus.OPEN,
            )
            self._alerts_by_result[result_id] = alert
            self._alerts_by_id[alert.alert_id] = alert
            return alert

    def get_alert(self, alert_id: str) -> CriticalAlertRecord | None:
        with self._lock:
            return self._alerts_by_id.get(alert_id)

    def record_notification(self, alert_id: str, recipient_role: str,
                            status: NotificationStatus,
                            attempted_at: datetime | None = None,
                            detail: str = "") -> NotificationEvent:
        if not isinstance(recipient_role, str) or not recipient_role.strip():
            raise AlertCreationError("Recipient role must be non-empty.")

        if not isinstance(status, NotificationStatus):
            raise AlertCreationError("Status must be a NotificationStatus.")

        timestamp = attempted_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise AlertCreationError("Notification time must include a timezone.")

        with self._lock:
            alert = self._alerts_by_id.get(alert_id)
            if alert is None:
                raise AlertCreationError("Critical alert was not found.")

            event = NotificationEvent(
                event_id=str(uuid4()),
                alert_id=alert_id,
                recipient_role=recipient_role.strip(),
                attempted_at=timestamp,
                status=status,
                detail=detail,
            )
            alert.notifications.append(event)
            return event

    def supersede_result(self, result_id: str) -> CriticalAlertRecord | None:
        if not isinstance(result_id, str) or not result_id.strip():
            raise AlertCreationError("Result ID must be non-empty.")
        with self._lock:
            alert = self._alerts_by_result.pop(result_id, None)
            if alert is not None:
                alert.status = AlertStatus.SUPERSEDED
            return alert

    def all_alerts(self) -> tuple[CriticalAlertRecord, ...]:
        with self._lock:
            return tuple(self._alerts_by_id.values())
