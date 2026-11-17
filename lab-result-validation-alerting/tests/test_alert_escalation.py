
from datetime import datetime, timedelta, timezone
import threading

import pytest

from labvalidation.models import AlertStatus, ResultFlag
from labvalidation.critical_alerts import CriticalAlertRegistry
from labvalidation.alert_escalation import (
    AlertEscalationScheduler,
    CriticalAlertEscalator,
    EscalationPolicy,
    EscalationEventType,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def setup_manager(policy=None):
    registry = CriticalAlertRegistry()
    registry.create_alert("R-STEP10", ResultFlag.CRITICAL_HIGH, NOW)
    manager = CriticalAlertEscalator(
        registry,
        tuple(policy or (
            EscalationPolicy("NURSE", 5),
            EscalationPolicy("MEDICAL_DIRECTOR", 15),
        )),
    )
    return registry, manager


def test_no_escalation_before_first_deadline():
    _, manager = setup_manager()
    assert manager.escalate_due(NOW + timedelta(minutes=4)) == ()


def test_escalates_at_exact_deadline():
    _, manager = setup_manager()
    events = manager.escalate_due(NOW + timedelta(minutes=5))
    assert len(events) == 1
    assert events[0].recipient_role == "NURSE"


def test_escalation_is_not_duplicated():
    _, manager = setup_manager()
    moment = NOW + timedelta(minutes=5)
    assert len(manager.escalate_due(moment)) == 1
    assert manager.escalate_due(moment) == ()


def test_multiple_due_steps_are_sent_in_order():
    _, manager = setup_manager()
    events = manager.escalate_due(NOW + timedelta(minutes=15))
    assert [e.recipient_role for e in events] == [
        "NURSE", "MEDICAL_DIRECTOR"
    ]


def test_notification_attempts_are_recorded():
    registry, manager = setup_manager()
    manager.escalate_due(NOW + timedelta(minutes=5))
    alert = registry.get_alert(manager.registry.all_alerts()[0].alert_id)
    assert len(alert.notifications) == 1


def test_acknowledgement_records_actor_and_time():
    _, manager = setup_manager()
    event = manager.acknowledge(
        manager.registry.all_alerts()[0].alert_id, "reviewer-1", "Patient and critical value confirmed", NOW
    )
    assert event.actor == "reviewer-1"
    assert event.occurred_at == NOW
    assert manager.status(manager.registry.all_alerts()[0].alert_id) == AlertStatus.ACKNOWLEDGED


def test_acknowledgement_records_read_back():
    _, manager = setup_manager()
    manager.acknowledge(manager.registry.all_alerts()[0].alert_id, "reviewer-1", "Value read back", NOW)
    events = manager.audit_events(manager.registry.all_alerts()[0].alert_id)
    assert [e.event_type for e in events] == [
        EscalationEventType.ACKNOWLEDGED,
        EscalationEventType.READ_BACK,
    ]


def test_acknowledged_alert_does_not_escalate():
    _, manager = setup_manager()
    manager.acknowledge(manager.registry.all_alerts()[0].alert_id, "reviewer-1", "Confirmed", NOW)
    assert manager.escalate_due(NOW + timedelta(hours=1)) == ()


def test_cannot_acknowledge_twice():
    _, manager = setup_manager()
    manager.acknowledge(manager.registry.all_alerts()[0].alert_id, "reviewer-1", "Confirmed", NOW)
    with pytest.raises(ValueError):
        manager.acknowledge(manager.registry.all_alerts()[0].alert_id, "reviewer-2", "Confirmed", NOW)


def test_closing_records_reason():
    _, manager = setup_manager()
    event = manager.close(manager.registry.all_alerts()[0].alert_id, "supervisor", "Resolved", NOW)
    assert event.event_type == EscalationEventType.CLOSED
    assert event.detail == "Resolved"
    assert manager.status(manager.registry.all_alerts()[0].alert_id) == AlertStatus.CLOSED


def test_closed_alert_does_not_escalate():
    _, manager = setup_manager()
    manager.close(manager.registry.all_alerts()[0].alert_id, "supervisor", "Resolved", NOW)
    assert manager.escalate_due(NOW + timedelta(hours=1)) == ()


def test_unknown_alert_is_rejected():
    _, manager = setup_manager()
    with pytest.raises(ValueError):
        manager.acknowledge("missing", "reviewer", "Confirmed", NOW)


def test_blank_read_back_is_rejected():
    _, manager = setup_manager()
    with pytest.raises(ValueError):
        manager.acknowledge(manager.registry.all_alerts()[0].alert_id, "reviewer", " ", NOW)


def test_naive_timestamp_is_rejected():
    _, manager = setup_manager()
    with pytest.raises(ValueError):
        manager.escalate_due(datetime(2026, 1, 1, 12, 0))


def test_negative_escalation_delay_is_rejected():
    with pytest.raises(ValueError):
        EscalationPolicy("NURSE", -1)


def test_escalation_delays_must_be_ordered():
    registry = CriticalAlertRegistry()
    with pytest.raises(ValueError):
        CriticalAlertEscalator(
            registry,
            (EscalationPolicy("NURSE", 15),
             EscalationPolicy("DIRECTOR", 5)),
        )


def test_explicit_read_back_is_audited():
    _, manager = setup_manager()
    event = manager.record_read_back(
        manager.registry.all_alerts()[0].alert_id, "reviewer", "Confirmed 7.2", NOW
    )
    assert event.event_type == EscalationEventType.READ_BACK
    assert event.detail == "Confirmed 7.2"


def test_audit_filter_only_returns_requested_alert():
    registry = CriticalAlertRegistry()
    registry.create_alert("R-A", ResultFlag.CRITICAL_HIGH, NOW)
    registry.create_alert("R-B", ResultFlag.CRITICAL_HIGH, NOW)
    manager = CriticalAlertEscalator(
        registry, (EscalationPolicy("NURSE", 0),)
    )
    manager.escalate_due(NOW)
    assert all(e.alert_id == "R-A" for e in manager.audit_events("R-A"))
    assert len(manager.audit_events()) == 2


def test_scheduler_runs_escalation_checks_automatically_and_stops():
    called = threading.Event()

    class FakeEscalator:
        def __init__(self):
            self.calls = []

        def escalate_due(self, now):
            self.calls.append(now)
            called.set()
            return ()

    manager = FakeEscalator()
    scheduler = AlertEscalationScheduler(
        manager, poll_interval_seconds=0.01
    )
    scheduler.start()
    try:
        assert called.wait(1.0)
        assert scheduler.is_running
    finally:
        assert scheduler.stop(timeout=1.0)

    assert manager.calls
    assert all(moment.tzinfo is not None for moment in manager.calls)
    assert not scheduler.is_running


@pytest.mark.parametrize("interval", [0, -1, float("nan"), float("inf"), True, "1"])
def test_scheduler_rejects_invalid_poll_intervals(interval):
    with pytest.raises(ValueError):
        AlertEscalationScheduler(CriticalAlertEscalator(
            CriticalAlertRegistry(), ()
        ), poll_interval_seconds=interval)