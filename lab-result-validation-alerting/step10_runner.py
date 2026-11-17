from pathlib import Path

root = Path(__file__).resolve().parent
module = root / "src" / "labvalidation" / "alert_escalation.py"
tests = root / "tests" / "test_alert_escalation.py"
module.parent.mkdir(parents=True, exist_ok=True)
tests.parent.mkdir(parents=True, exist_ok=True)

source = r'''
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from labvalidation.models import AlertStatus
from labvalidation.critical_alerts import (
    CriticalAlertRegistry,
    NotificationStatus,
)


class EscalationEventType(str, Enum):
    ESCALATED = "escalated"
    ACKNOWLEDGED = "acknowledged"
    CLOSED = "closed"
    READ_BACK = "read_back"


@dataclass(frozen=True)
class EscalationPolicy:
    recipient_role: str
    after_minutes: int

    def __post_init__(self):
        if not self.recipient_role.strip():
            raise ValueError("Recipient role is required")
        if self.after_minutes < 0:
            raise ValueError("Escalation delay cannot be negative")


@dataclass(frozen=True)
class EscalationAuditEvent:
    event_type: EscalationEventType
    alert_id: str
    actor: str
    occurred_at: datetime
    recipient_role: str = ""
    detail: str = ""


@dataclass
class _AlertLifecycle:
    status: AlertStatus
    next_step: int = 0
    acknowledged_by: str = ""
    acknowledged_at: datetime | None = None


class CriticalAlertEscalator:
    def __init__(
        self,
        registry: CriticalAlertRegistry,
        policy: tuple[EscalationPolicy, ...],
    ):
        self.registry = registry
        self.policy = tuple(policy)
        previous_delay = -1
        for step in self.policy:
            if step.after_minutes < previous_delay:
                raise ValueError("Escalation delays must be in ascending order")
            previous_delay = step.after_minutes
        self._states: dict[str, _AlertLifecycle] = {}
        self._events: list[EscalationAuditEvent] = []

    @staticmethod
    def _validate_time(value: datetime) -> None:
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware")
        if value.utcoffset() is None:
            raise ValueError("Timestamp must be timezone-aware")

    @staticmethod
    def _validate_text(value: str, field: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} is required")

    def _get_alert(self, alert_id: str):
        self._validate_text(alert_id, "Alert ID")
        alert = self.registry.get_alert(alert_id)
        if alert is None:
            raise ValueError("Alert not found")
        if alert.alert_id not in self._states:
            self._states[alert.alert_id] = _AlertLifecycle(alert.status)
        return alert, self._states[alert.alert_id]

    def status(self, alert_id: str) -> AlertStatus:
        _, state = self._get_alert(alert_id)
        return state.status

    def escalate_due(self, now: datetime) -> tuple[EscalationAuditEvent, ...]:
        self._validate_time(now)
        created = []

        for alert in self.registry.all_alerts():
            _, state = self._get_alert(alert.alert_id)
            if state.status != AlertStatus.OPEN:
                continue

            while state.next_step < len(self.policy):
                step = self.policy[state.next_step]
                due_at = alert.created_at + timedelta(
                    minutes=step.after_minutes
                )
                if now < due_at:
                    break

                event = EscalationAuditEvent(
                    event_type=EscalationEventType.ESCALATED,
                    alert_id=alert.alert_id,
                    actor="system",
                    occurred_at=now,
                    recipient_role=step.recipient_role,
                    detail=f"Escalation step {state.next_step + 1}",
                )
                self.registry.record_notification(
                    alert.alert_id,
                    step.recipient_role,
                    NotificationStatus.SENT,
                    attempted_at=now,
                    detail=event.detail,
                )
                self._events.append(event)
                created.append(event)
                state.next_step += 1

        return tuple(created)

    def acknowledge(
        self,
        alert_id: str,
        acknowledged_by: str,
        read_back: str,
        acknowledged_at: datetime | None = None,
    ) -> EscalationAuditEvent:
        self._validate_text(acknowledged_by, "Acknowledging person")
        self._validate_text(read_back, "Read-back confirmation")
        moment = acknowledged_at or datetime.now(timezone.utc)
        self._validate_time(moment)
        alert, state = self._get_alert(alert_id)

        if state.status != AlertStatus.OPEN:
            raise ValueError("Only open alerts can be acknowledged")

        state.status = AlertStatus.ACKNOWLEDGED
        state.acknowledged_by = acknowledged_by.strip()
        state.acknowledged_at = moment

        event = EscalationAuditEvent(
            event_type=EscalationEventType.ACKNOWLEDGED,
            alert_id=alert.alert_id,
            actor=acknowledged_by.strip(),
            occurred_at=moment,
            detail="Alert acknowledged",
        )
        read_event = EscalationAuditEvent(
            event_type=EscalationEventType.READ_BACK,
            alert_id=alert.alert_id,
            actor=acknowledged_by.strip(),
            occurred_at=moment,
            detail=read_back.strip(),
        )
        self._events.extend((event, read_event))
        return event

    def record_read_back(
        self,
        alert_id: str,
        actor: str,
        read_back: str,
        recorded_at: datetime | None = None,
    ) -> EscalationAuditEvent:
        self._validate_text(actor, "Read-back actor")
        self._validate_text(read_back, "Read-back confirmation")
        moment = recorded_at or datetime.now(timezone.utc)
        self._validate_time(moment)
        alert, _ = self._get_alert(alert_id)

        event = EscalationAuditEvent(
            event_type=EscalationEventType.READ_BACK,
            alert_id=alert.alert_id,
            actor=actor.strip(),
            occurred_at=moment,
            detail=read_back.strip(),
        )
        self._events.append(event)
        return event

    def close(
        self,
        alert_id: str,
        closed_by: str,
        reason: str,
        closed_at: datetime | None = None,
    ) -> EscalationAuditEvent:
        self._validate_text(closed_by, "Closing person")
        self._validate_text(reason, "Closure reason")
        moment = closed_at or datetime.now(timezone.utc)
        self._validate_time(moment)
        alert, state = self._get_alert(alert_id)

        if state.status == AlertStatus.CLOSED:
            raise ValueError("Alert is already closed")

        state.status = AlertStatus.CLOSED
        event = EscalationAuditEvent(
            event_type=EscalationEventType.CLOSED,
            alert_id=alert.alert_id,
            actor=closed_by.strip(),
            occurred_at=moment,
            detail=reason.strip(),
        )
        self._events.append(event)
        return event

    def audit_events(
        self, alert_id: str | None = None
    ) -> tuple[EscalationAuditEvent, ...]:
        if alert_id is None:
            return tuple(self._events)
        self._validate_text(alert_id, "Alert ID")
        return tuple(
            event for event in self._events
            if event.alert_id == alert_id
        )
'''

test_source = r'''
from datetime import datetime, timedelta, timezone

import pytest

from labvalidation.models import AlertStatus, ResultFlag
from labvalidation.critical_alerts import CriticalAlertRegistry
from labvalidation.alert_escalation import (
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
    alert = registry.get_alert("R-STEP10")
    assert len(alert.notifications) == 1


def test_acknowledgement_records_actor_and_time():
    _, manager = setup_manager()
    event = manager.acknowledge(
        "R-STEP10", "reviewer-1", "Patient and critical value confirmed", NOW
    )
    assert event.actor == "reviewer-1"
    assert event.occurred_at == NOW
    assert manager.status("R-STEP10") == AlertStatus.ACKNOWLEDGED


def test_acknowledgement_records_read_back():
    _, manager = setup_manager()
    manager.acknowledge("R-STEP10", "reviewer-1", "Value read back", NOW)
    events = manager.audit_events("R-STEP10")
    assert [e.event_type for e in events] == [
        EscalationEventType.ACKNOWLEDGED,
        EscalationEventType.READ_BACK,
    ]


def test_acknowledged_alert_does_not_escalate():
    _, manager = setup_manager()
    manager.acknowledge("R-STEP10", "reviewer-1", "Confirmed", NOW)
    assert manager.escalate_due(NOW + timedelta(hours=1)) == ()


def test_cannot_acknowledge_twice():
    _, manager = setup_manager()
    manager.acknowledge("R-STEP10", "reviewer-1", "Confirmed", NOW)
    with pytest.raises(ValueError):
        manager.acknowledge("R-STEP10", "reviewer-2", "Confirmed", NOW)


def test_closing_records_reason():
    _, manager = setup_manager()
    event = manager.close("R-STEP10", "supervisor", "Resolved", NOW)
    assert event.event_type == EscalationEventType.CLOSED
    assert event.detail == "Resolved"
    assert manager.status("R-STEP10") == AlertStatus.CLOSED


def test_closed_alert_does_not_escalate():
    _, manager = setup_manager()
    manager.close("R-STEP10", "supervisor", "Resolved", NOW)
    assert manager.escalate_due(NOW + timedelta(hours=1)) == ()


def test_unknown_alert_is_rejected():
    _, manager = setup_manager()
    with pytest.raises(ValueError):
        manager.acknowledge("missing", "reviewer", "Confirmed", NOW)


def test_blank_read_back_is_rejected():
    _, manager = setup_manager()
    with pytest.raises(ValueError):
        manager.acknowledge("R-STEP10", "reviewer", " ", NOW)


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
        "R-STEP10", "reviewer", "Confirmed 7.2", NOW
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
'''

module.write_text(source, encoding="utf-8")
tests.write_text(test_source, encoding="utf-8")
print("Created src/labvalidation/alert_escalation.py")
print("Created tests/test_alert_escalation.py")