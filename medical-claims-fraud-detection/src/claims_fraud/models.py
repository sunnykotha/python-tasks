"""Core domain models for medical claims fraud detection."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class ClaimLine:
    id: str
    procedure_code: str
    service_date: date
    billed_amount: float
    start_time: datetime | None = None
    end_time: datetime | None = None
    location: str | None = None
    units: int = 1

    def __post_init__(self):
        if not self.id.strip():
            raise ValueError("Claim line id is required.")
        if not self.procedure_code.strip():
            raise ValueError("Procedure code is required.")
        if self.billed_amount < 0:
            raise ValueError("Billed amount cannot be negative.")
        if self.units < 1:
            raise ValueError("Units must be at least 1.")
        if self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                raise ValueError("End time must be after start time.")


@dataclass(frozen=True)
class Claim:
    id: str
    patient_id: str
    provider_id: str
    lines: tuple[ClaimLine, ...]
    status: str = "active"
    submitted_at: datetime | None = None

    def __post_init__(self):
        if not self.id.strip():
            raise ValueError("Claim id is required.")
        if not self.patient_id.strip():
            raise ValueError("Patient id is required.")
        if not self.provider_id.strip():
            raise ValueError("Provider id is required.")
        if not self.lines:
            raise ValueError("A claim must contain at least one line.")
        if self.status not in {"active", "corrected", "reversed"}:
            raise ValueError("Status must be active, corrected, or reversed.")


@dataclass(frozen=True)
class Provider:
    id: str
    specialty: str

    def __post_init__(self):
        if not self.id.strip() or not self.specialty.strip():
            raise ValueError("Provider id and specialty are required.")


@dataclass(frozen=True)
class Patient:
    id: str
    date_of_death: date | None = None

    def __post_init__(self):
        if not self.id.strip():
            raise ValueError("Patient id is required.")


@dataclass(frozen=True)
class ProcedureTimeEstimate:
    procedure_code: str
    estimated_minutes: int

    def __post_init__(self):
        if not self.procedure_code.strip():
            raise ValueError("Procedure code is required.")
        if self.estimated_minutes <= 0:
            raise ValueError("Estimated minutes must be positive.")


@dataclass(frozen=True)
class PeerGroup:
    specialty: str
    provider_ids: tuple[str, ...]

    def __post_init__(self):
        if not self.specialty.strip():
            raise ValueError("Peer group specialty is required.")
        if not self.provider_ids:
            raise ValueError("Peer group must contain providers.")


@dataclass(frozen=True)
class AnomalyFlag:
    reason_code: str
    description: str
    severity: str
    score: float
    claim_line_ids: tuple[str, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.reason_code.strip():
            raise ValueError("Reason code is required.")
        if not self.description.strip():
            raise ValueError("Description is required.")
        if self.severity not in {"low", "medium", "high", "critical"}:
            raise ValueError("Invalid severity.")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("Score must be between 0 and 1.")


@dataclass(frozen=True)
class CaseFile:
    id: str
    provider_id: str
    flags: tuple[AnomalyFlag, ...]
    claim_line_ids: tuple[str, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id.strip():
            raise ValueError("Case file id is required.")
        if not self.provider_id.strip():
            raise ValueError("Provider id is required.")
        if not self.flags:
            raise ValueError("A case file must contain at least one anomaly flag.")