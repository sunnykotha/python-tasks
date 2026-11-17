# Lab Result Validation and Critical Value Alerting

A Python library for validating laboratory results, interpreting result flags,
checking changes from prior results, and tracking critical-result alerts and
escalation events.

## Features

- Configurable reference ranges and result interpretation.
- Unit conversion for supported laboratory measurements.
- Normal, low, high, critical-low, and critical-high result flags.
- Delta checks against prior results.
- Specimen-quality handling, including hemolysis-related suppression rules.
- Critical-alert tracking, acknowledgement, read-back, and escalation audit events.
- Optional SMTP email notification adapter.
- Automated tests for core behavior and integration scenarios.

Clinical reference ranges and thresholds must be reviewed and configured for
the intended laboratory, population, units, and clinical policies. This
project is not independently validated for clinical production use.

## Requirements

- Python 3.13 is the development environment used for this project.
- Install dependencies from `requirements.txt`.
- Git is required for source control.

## Setup

From the project root in PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Optional SMTP notifications

The SMTP adapter is provider-agnostic and uses Python's standard library.
No particular SMTP provider is required by the library. Configure a provider
that supports the organization's security and delivery requirements.

Supported environment variables:

| Variable | Purpose |
|---|---|
| `LAB_SMTP_HOST` | SMTP server hostname |
| `LAB_SMTP_PORT` | SMTP port; defaults to `587` |
| `LAB_SMTP_USERNAME` | SMTP username, if required |
| `LAB_SMTP_PASSWORD` | SMTP password, if required |
| `LAB_SMTP_FROM` | Sender email address |
| `LAB_ALERT_RECIPIENT_<ROLE>` | Recipient address for the configured alert role |

Keep credentials in environment variables or a secrets manager. Do not commit
credentials to source control.

To enable notifications, inject `SmtpEmailSender` into the workflow:

```python
from labvalidation.email_notifications import SmtpEmailSender
from labvalidation.workflow import LabResultWorkflow

workflow = LabResultWorkflow(
    reference_ranges=reference_ranges,
    notification_sender=SmtpEmailSender(),
)
```

The `reference_ranges` value must be configured for the intended laboratory.
The example demonstrates dependency injection; it does not configure a
provider or establish a live connection.

## Notification limitations

- Without a configured notification sender, email delivery is not attempted.
- SMTP server acceptance is not proof that an email reached the recipient's inbox.
- Email delivery is not proof that a clinician acknowledged or read back a critical result.
- Clinical acknowledgement and escalation must be tracked separately.
- Configure and verify provider credentials, recipients, transport security,
  delivery monitoring, and operational escalation policies before deployment.

This project is an implementation and test exercise, not a validated clinical
system. It must not replace approved laboratory procedures or clinical review.