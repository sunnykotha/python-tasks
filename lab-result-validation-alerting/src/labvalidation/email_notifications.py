import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage

from labvalidation.critical_alerts import NotificationStatus


def deliver_notification(registry, alert, recipient_role, attempted_at, sender):
    status = NotificationStatus.FAILED
    detail = "No notification sender configured."

    if sender is not None:
        try:
            sender.send(recipient_role, alert)
            status = NotificationStatus.SENT
            detail = "SMTP server accepted the notification."
        except Exception as exc:
            detail = f"Delivery failed: {type(exc).__name__}"

    return registry.record_notification(
        alert.alert_id,
        recipient_role,
        status,
        attempted_at=attempted_at or datetime.now(timezone.utc),
        detail=detail,
    )


class SmtpEmailSender:
    """Send alert metadata through authenticated SMTP with TLS."""

    def __init__(self, environ=None):
        self._environ = os.environ if environ is None else environ

    def send(self, recipient_role, alert):
        env = self._environ
        role_key = "".join(
            character if character.isalnum() else "_"
            for character in recipient_role.strip().upper()
        )
        recipient = env.get(f"LAB_ALERT_RECIPIENT_{role_key}", "").strip()
        host = env.get("LAB_SMTP_HOST", "").strip()
        username = env.get("LAB_SMTP_USERNAME", "").strip()
        password = env.get("LAB_SMTP_PASSWORD", "")
        sender_address = env.get("LAB_SMTP_FROM", "").strip()
        port_text = env.get("LAB_SMTP_PORT", "587").strip()

        if not all((recipient, host, username, password, sender_address)):
            raise RuntimeError("SMTP configuration or recipient is missing.")

        try:
            port = int(port_text)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("SMTP port must be an integer.") from exc

        if not 1 <= port <= 65535:
            raise RuntimeError("SMTP port is out of range.")

        message = EmailMessage()
        message["Subject"] = f"Critical laboratory alert: {alert.flag.value}"
        message["From"] = sender_address
        message["To"] = recipient
        message.set_content(
            "A critical laboratory result requires review.\n"
            f"Alert ID: {alert.alert_id}\n"
            f"Result ID: {alert.result_id}\n"
            f"Flag: {alert.flag.value}\n"
            "Please use the authorized clinical system to review the result "
            "and document acknowledgement and read-back."
        )

        if port == 465:
            with smtplib.SMTP_SSL(
                host, port, timeout=10,
                context=ssl.create_default_context()
            ) as connection:
                connection.login(username, password)
                refused = connection.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=10) as connection:
                connection.ehlo()
                connection.starttls(context=ssl.create_default_context())
                connection.ehlo()
                connection.login(username, password)
                refused = connection.send_message(message)

        if refused:
            raise RuntimeError("SMTP server refused one or more recipients.")