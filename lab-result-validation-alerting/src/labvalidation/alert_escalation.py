
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import math
import threading
from collections.abc import Callable

from labvalidation.models import AlertStatus
from labvalidation.critical_alerts import CriticalAlertRegistry
from labvalidation.email_notifications import deliver_notification


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
        notification_sender=None,
    ):
        self.registry = registry
        self.policy = tuple(policy)
        self.notification_sender = notification_sender
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
            if alert.status == AlertStatus.SUPERSEDED:
                state.status = AlertStatus.SUPERSEDED
                continue
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
                deliver_notification(
                    self.registry,
                    alert,
                    step.recipient_role,
                    now,
                    self.notification_sender,
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


class AlertEscalationScheduler:
    """Periodically checks escalation deadlines on a stoppable daemon thread."""

    def __init__(
        self,
        escalator: CriticalAlertEscalator,
        poll_interval_seconds: float = 1.0,
        clock: Callable[[], datetime] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ):
        if (
            isinstance(poll_interval_seconds, bool)
            or not isinstance(poll_interval_seconds, (int, float))
            or not math.isfinite(poll_interval_seconds)
            or poll_interval_seconds <= 0
        ):
            raise ValueError("Poll interval must be a finite positive number")

        self.escalator = escalator
        self.poll_interval_seconds = float(poll_interval_seconds)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._on_error = on_error
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._last_error: Exception | None = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    @property
    def last_error(self) -> Exception | None:
        return self._last_error

    def start(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="lab-alert-escalation",
                daemon=True,
            )
            self._thread.start()
        return self

    def stop(self, timeout: float | None = None) -> bool:
        if timeout is not None and (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout < 0
        ):
            raise ValueError("Timeout must be a finite non-negative number")

        self._stop_event.set()
        with self._lock:
            thread = self._thread

        if thread is None:
            return True
        if thread is not threading.current_thread():
            thread.join(timeout)
        return not thread.is_alive()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.escalator.escalate_due(self._clock())
                self._last_error = None
            except Exception as exc:
                self._last_error = exc
                if self._on_error is not None:
                    try:
                        self._on_error(exc)
                    except Exception:
                        pass

            if self._stop_event.wait(self.poll_interval_seconds):
                break