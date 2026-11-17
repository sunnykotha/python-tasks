from datetime import datetime, timezone
from email.message import EmailMessage

import pytest

from labvalidation.critical_alerts import (
    CriticalAlertRegistry,
    NotificationStatus,
)
from labvalidation.email_notifications import (
    SmtpEmailSender,
    deliver_notification,
)
from labvalidation.models import ResultFlag


NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


class FakeSMTP:
    instances = []
    refused = {}

    def __init__(self, host, port, **kwargs):
        self.host = host
        self.port = port
        self.messages = []
        self.logged_in = False
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def ehlo(self):
        return None

    def starttls(self, context=None):
        return None

    def login(self, username, password):
        self.logged_in = True

    def send_message(self, message):
        self.messages.append(message)
        return FakeSMTP.refused


@pytest.fixture
def smtp_config():
    FakeSMTP.instances = []
    FakeSMTP.refused = {}
    return {
        "LAB_SMTP_HOST": "smtp.example.test",
        "LAB_SMTP_PORT": "587",
        "LAB_SMTP_USERNAME": "test-user",
        "LAB_SMTP_PASSWORD": "test-password",
        "LAB_SMTP_FROM": "alerts@example.test",
        "LAB_ALERT_RECIPIENT_ORDERING_PHYSICIAN": "doctor@example.test",
        "LAB_ALERT_RECIPIENT_CHARGE_NURSE": "nurse@example.test",
        "LAB_ALERT_RECIPIENT_SUPERVISOR": "supervisor@example.test",
    }


def make_alert():
    registry = CriticalAlertRegistry()
    alert = registry.create_alert("EMAIL-TEST-1", ResultFlag.CRITICAL_HIGH, NOW)
    return registry, alert


def test_smtp_sender_sends_email_over_starttls(monkeypatch, smtp_config):
    import labvalidation.email_notifications as module

    monkeypatch.setattr(module.smtplib, "SMTP", FakeSMTP)
    registry, alert = make_alert()
    sender = SmtpEmailSender(smtp_config)

    event = deliver_notification(
        registry, alert, "ORDERING_PHYSICIAN", NOW, sender
    )

    assert event.status == NotificationStatus.SENT
    connection = FakeSMTP.instances[0]
    assert connection.host == "smtp.example.test"
    assert connection.logged_in
    assert len(connection.messages) == 1
    assert connection.messages[0]["To"] == "doctor@example.test"
    assert "EMAIL-TEST-1" in connection.messages[0].get_content()


def test_missing_smtp_configuration_records_failure():
    registry, alert = make_alert()
    event = deliver_notification(
        registry, alert, "ORDERING_PHYSICIAN", NOW, SmtpEmailSender({})
    )

    assert event.status == NotificationStatus.FAILED
    assert "RuntimeError" in event.detail


def test_missing_sender_never_records_false_success():
    registry, alert = make_alert()
    event = deliver_notification(
        registry, alert, "ORDERING_PHYSICIAN", NOW, None
    )

    assert event.status == NotificationStatus.FAILED
    assert "No notification sender" in event.detail


def test_smtp_recipient_refusal_records_failure(monkeypatch, smtp_config):
    import labvalidation.email_notifications as module

    monkeypatch.setattr(module.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.refused = {"doctor@example.test": (550, b"Rejected")}
    registry, alert = make_alert()

    event = deliver_notification(
        registry, alert, "ORDERING_PHYSICIAN", NOW,
        SmtpEmailSender(smtp_config),
    )

    assert event.status == NotificationStatus.FAILED
    assert "RuntimeError" in event.detail