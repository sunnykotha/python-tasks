from pathlib import Path
import subprocess

project = Path(r"C:\Users\GK\lab-result-validation-alerting")
python = project / ".venv" / "Scripts" / "python.exe"

service = r'''
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
                status=AlertStatus.ACTIVE,
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

    def all_alerts(self) -> tuple[CriticalAlertRecord, ...]:
        with self._lock:
            return tuple(self._alerts_by_id.values())
'''

tests = r'''
from datetime import datetime, timezone, timedelta

import pytest

from labvalidation.models import ResultFlag, AlertStatus
from labvalidation.critical_alerts import (
    CriticalAlertRegistry, AlertCreationError, NotificationStatus
)


NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def test_critical_high_creates_alert():
    registry = CriticalAlertRegistry()
    alert = registry.create_alert("R-1", ResultFlag.CRITICAL_HIGH, NOW)
    assert alert is not None
    assert alert.result_id == "R-1"
    assert alert.flag == ResultFlag.CRITICAL_HIGH
    assert alert.created_at == NOW
    assert alert.status == AlertStatus.ACTIVE


def test_critical_low_creates_alert():
    registry = CriticalAlertRegistry()
    alert = registry.create_alert("R-2", ResultFlag.CRITICAL_LOW, NOW)
    assert alert.flag == ResultFlag.CRITICAL_LOW


@pytest.mark.parametrize(
    "flag",
    [ResultFlag.NORMAL, ResultFlag.LOW, ResultFlag.HIGH, ResultFlag.UNINTERPRETED],
)
def test_noncritical_flag_does_not_create_alert(flag):
    registry = CriticalAlertRegistry()
    assert registry.create_alert("R-3", flag, NOW) is None
    assert registry.all_alerts() == ()


def test_duplicate_result_returns_same_alert():
    registry = CriticalAlertRegistry()
    first = registry.create_alert("R-4", ResultFlag.CRITICAL_HIGH, NOW)
    second = registry.create_alert(
        "R-4", ResultFlag.CRITICAL_HIGH, NOW + timedelta(minutes=1)
    )
    assert second is first
    assert len(registry.all_alerts()) == 1


def test_alert_can_be_retrieved_by_id():
    registry = CriticalAlertRegistry()
    alert = registry.create_alert("R-5", ResultFlag.CRITICAL_LOW, NOW)
    assert registry.get_alert(alert.alert_id) is alert


def test_notification_attempt_is_recorded():
    registry = CriticalAlertRegistry()
    alert = registry.create_alert("R-6", ResultFlag.CRITICAL_HIGH, NOW)
    event = registry.record_notification(
        alert.alert_id, "CHARGE_NURSE", NotificationStatus.SENT, NOW
    )
    assert event.alert_id == alert.alert_id
    assert event.recipient_role == "CHARGE_NURSE"
    assert event.status == NotificationStatus.SENT
    assert alert.notifications == [event]


def test_failed_notification_is_audited():
    registry = CriticalAlertRegistry()
    alert = registry.create_alert("R-7", ResultFlag.CRITICAL_HIGH, NOW)
    event = registry.record_notification(
        alert.alert_id, "SUPERVISOR", NotificationStatus.FAILED,
        NOW, "Delivery unavailable"
    )
    assert event.status == NotificationStatus.FAILED
    assert event.detail == "Delivery unavailable"


def test_multiple_notification_attempts_are_preserved():
    registry = CriticalAlertRegistry()
    alert = registry.create_alert("R-8", ResultFlag.CRITICAL_HIGH, NOW)
    first = registry.record_notification(
        alert.alert_id, "CHARGE_NURSE", NotificationStatus.FAILED, NOW
    )
    second = registry.record_notification(
        alert.alert_id, "SUPERVISOR", NotificationStatus.SENT,
        NOW + timedelta(minutes=1)
    )
    assert alert.notifications == [first, second]


def test_unknown_alert_notification_is_rejected():
    registry = CriticalAlertRegistry()
    with pytest.raises(AlertCreationError, match="not found"):
        registry.record_notification(
            "unknown", "CHARGE_NURSE", NotificationStatus.SENT, NOW
        )


def test_empty_result_id_is_rejected():
    registry = CriticalAlertRegistry()
    with pytest.raises(AlertCreationError, match="Result ID"):
        registry.create_alert(" ", ResultFlag.CRITICAL_HIGH, NOW)


def test_naive_alert_timestamp_is_rejected():
    registry = CriticalAlertRegistry()
    with pytest.raises(AlertCreationError, match="timezone"):
        registry.create_alert(
            "R-9", ResultFlag.CRITICAL_HIGH, datetime(2026, 10, 29, 12, 0)
        )


def test_notification_requires_valid_status():
    registry = CriticalAlertRegistry()
    alert = registry.create_alert("R-10", ResultFlag.CRITICAL_HIGH, NOW)
    with pytest.raises(AlertCreationError, match="NotificationStatus"):
        registry.record_notification(alert.alert_id, "CHARGE_NURSE", "SENT", NOW)
'''

(project / "src/labvalidation/critical_alerts.py").write_text(
    service.lstrip(), encoding="utf-8"
)
(project / "tests/test_critical_alerts.py").write_text(
    tests.lstrip(), encoding="utf-8"
)

result = subprocess.run(
    [str(python), "-m", "pytest", "-v"],
    cwd=project,
)

if result.returncode == 0:
    print("\nSTEP 9 PASSED: Critical alert and notification tests passed.")
if result.returncode != 0:
    print(f"\nSTEP 9 FAILED: pytest returned {result.returncode}.")