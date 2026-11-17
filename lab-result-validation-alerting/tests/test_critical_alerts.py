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
    assert alert.status == AlertStatus.OPEN


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
