from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class Sex(str, Enum):
    FEMALE = "female"
    MALE = "male"
    OTHER = "other"
    UNKNOWN = "unknown"


class ResultFlag(str, Enum):
    NORMAL = "normal"
    LOW = "low"
    HIGH = "high"
    CRITICAL_LOW = "critical-low"
    CRITICAL_HIGH = "critical-high"
    UNINTERPRETED = "uninterpreted"


class AlertStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    CLOSED = "closed"
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class Unit:
    code: str
    name: str

    def __post_init__(self):
        if not self.code.strip() or not self.name.strip():
            raise ValueError("Unit code and name cannot be empty.")


@dataclass(frozen=True)
class LabTestDefinition:
    code: str
    name: str
    default_unit: Unit

    def __post_init__(self):
        if not self.code.strip() or not self.name.strip():
            raise ValueError("Test code and name cannot be empty.")


@dataclass(frozen=True)
class ReferenceRange:
    test_code: str
    low: float
    high: float
    unit: Unit
    min_age_days: Optional[int] = None
    max_age_days: Optional[int] = None
    sex: Optional[Sex] = None
    pregnancy_required: Optional[bool] = None
    condition: Optional[str] = None

    def __post_init__(self):
        if self.low > self.high:
            raise ValueError("Range low cannot exceed high.")
        if self.min_age_days is not None and self.min_age_days < 0:
            raise ValueError("Minimum age cannot be negative.")
        if self.max_age_days is not None and self.max_age_days < 0:
            raise ValueError("Maximum age cannot be negative.")
        if (
            self.min_age_days is not None
            and self.max_age_days is not None
            and self.min_age_days > self.max_age_days
        ):
            raise ValueError("Minimum age cannot exceed maximum age.")


@dataclass(frozen=True)
class LabResult:
    result_id: str
    patient_id: str
    test: LabTestDefinition
    value: str
    unit: Unit
    collected_at: datetime
    patient_age_days: Optional[int] = None
    sex: Sex = Sex.UNKNOWN
    is_pregnant: Optional[bool] = None
    condition: Optional[str] = None
    specimen_hemolyzed: bool = False
    amended: bool = False

    def __post_init__(self):
        if not self.result_id.strip() or not self.patient_id.strip():
            raise ValueError("Result ID and patient ID cannot be empty.")
        if not self.value.strip():
            raise ValueError("Result value cannot be empty.")
        if self.patient_age_days is not None and self.patient_age_days < 0:
            raise ValueError("Patient age cannot be negative.")


@dataclass(frozen=True)
class PreviousResult:
    result: LabResult


@dataclass(frozen=True)
class EscalationStep:
    alert_id: str
    recipient_role: str
    sent_at: datetime
    acknowledged_at: Optional[datetime] = None
    read_back: Optional[str] = None

    def __post_init__(self):
        if not self.alert_id.strip() or not self.recipient_role.strip():
            raise ValueError("Alert ID and recipient role cannot be empty.")


@dataclass(frozen=True)
class CriticalAlert:
    alert_id: str
    result_id: str
    flag: ResultFlag
    created_at: datetime
    status: AlertStatus = AlertStatus.OPEN
    escalation_steps: tuple[EscalationStep, ...] = ()

    def __post_init__(self):
        if not self.alert_id.strip() or not self.result_id.strip():
            raise ValueError("Alert ID and result ID cannot be empty.")
        if self.flag not in (
            ResultFlag.CRITICAL_LOW,
            ResultFlag.CRITICAL_HIGH,
        ):
            raise ValueError("A critical alert requires a critical flag.")