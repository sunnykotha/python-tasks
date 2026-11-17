from pathlib import Path
import subprocess
import sys

project = Path(r"C:\Users\GK\lab-result-validation-alerting")
python = project / ".venv" / "Scripts" / "python.exe"

source = r'''
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


@dataclass(frozen=True)
class Unit:
    code: str
    name: str

    def __post_init__(self):
        if not self.code.strip():
            raise ValueError("Unit code cannot be empty.")
        if not self.name.strip():
            raise ValueError("Unit name cannot be empty.")


@dataclass(frozen=True)
class TestDefinition:
    code: str
    name: str
    default_unit: Unit

    def __post_init__(self):
        if not self.code.strip():
            raise ValueError("Test code cannot be empty.")
        if not self.name.strip():
            raise ValueError("Test name cannot be empty.")


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
            raise ValueError("Reference range low cannot exceed high.")
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
    test: TestDefinition
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
        if not self.result_id.strip():
            raise ValueError("Result ID cannot be empty.")
        if not self.patient_id.strip():
            raise ValueError("Patient ID cannot be empty.")
        if not self.value.strip():
            raise ValueError("Result value cannot be empty.")
        if self.patient_age_days is not None and self.patient_age_days < 0:
            raise ValueError("Patient age in days cannot be negative.")


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
        if not self.alert_id.strip():
            raise ValueError("Alert ID cannot be empty.")
        if not self.recipient_role.strip():
            raise ValueError("Recipient role cannot be empty.")


@dataclass(frozen=True)
class CriticalAlert:
    alert_id: str
    result_id: str
    flag: ResultFlag
    created_at: datetime
    status: AlertStatus = AlertStatus.OPEN
    escalation_steps: tuple[EscalationStep, ...] = ()

    def __post_init__(self):
        if not self.alert_id.strip():
            raise ValueError("Alert ID cannot be empty.")
        if not self.result_id.strip():
            raise ValueError("Result ID cannot be empty.")
        if self.flag not in (ResultFlag.CRITICAL_LOW, ResultFlag.CRITICAL_HIGH):
            raise ValueError("Critical alerts require a critical result flag.")
''' 

test_source = r'''
from datetime import datetime, timezone
import pytest

from labvalidation.models import (
    Unit, TestDefinition, ReferenceRange, LabResult, PreviousResult,
    CriticalAlert, EscalationStep, Sex, ResultFlag, AlertStatus
)


@pytest.fixture
def sample():
    unit = Unit("mmol/L", "millimoles per litre")
    test = TestDefinition("K", "Potassium", unit)
    result = LabResult(
        result_id="R001",
        patient_id="P001",
        test=test,
        value="6.9",
        unit=unit,
        collected_at=datetime.now(timezone.utc),
        patient_age_days=60 * 365,
        sex=Sex.MALE,
    )
    return unit, test, result


def test_unit_and_test_definition(sample):
    unit, test, _ = sample
    assert unit.code == "mmol/L"
    assert test.code == "K"


def test_reference_range_accepts_age_and_sex(sample):
    unit, _, _ = sample
    reference = ReferenceRange(
        test_code="K",
        low=3.5,
        high=5.1,
        unit=unit,
        min_age_days=18 * 365,
        sex=Sex.MALE,
    )
    assert reference.low == 3.5
    assert reference.max_age_days is None


def test_lab_result_preserves_raw_value(sample):
    _, _, result = sample
    assert result.value == "6.9"
    assert result.patient_age_days is not None


def test_previous_result_wraps_lab_result(sample):
    _, _, result = sample
    assert PreviousResult(result).result.result_id == "R001"


def test_escalation_step_records_recipient_and_readback():
    step = EscalationStep(
        alert_id="A001",
        recipient_role="charge_nurse",
        sent_at=datetime.now(timezone.utc),
        read_back="Potassium 6.9 mmol/L confirmed",
    )
    assert step.recipient_role == "charge_nurse"
    assert step.read_back is not None


def test_critical_alert_requires_critical_flag():
    alert = CriticalAlert(
        alert_id="A001",
        result_id="R001",
        flag=ResultFlag.CRITICAL_HIGH,
        created_at=datetime.now(timezone.utc),
    )
    assert alert.status == AlertStatus.OPEN


def test_critical_alert_rejects_normal_flag():
    with pytest.raises(ValueError):
        CriticalAlert(
            alert_id="A002",
            result_id="R001",
            flag=ResultFlag.NORMAL,
            created_at=datetime.now(timezone.utc),
        )


def test_invalid_reference_range_is_rejected(sample):
    unit, _, _ = sample
    with pytest.raises(ValueError):
        ReferenceRange("K", 6.0, 3.0, unit)


def test_negative_patient_age_is_rejected(sample):
    _, test, _ = sample
    with pytest.raises(ValueError):
        LabResult(
            result_id="R002",
            patient_id="P002",
            test=test,
            value="4.0",
            unit=test.default_unit,
            collected_at=datetime.now(timezone.utc),
            patient_age_days=-1,
        )
'''

files = {
    "src/labvalidation/models.py": source,
    "tests/test_models.py": test_source,
}

for name, content in files.items():
    (project / name).write_text(content.lstrip(), encoding="utf-8")

result = subprocess.run(
    [str(python), "-m", "pytest", "-v"],
    cwd=project,
)

if result.returncode == 0:
    print("\nSTEP 2 PASSED: Core data model tests passed.")
else:
    print(f"\nSTEP 2 FAILED: pytest returned {result.returncode}.")
'''

script_path = Path(sys.argv[0]).parent / "step2_create_models.py"
script_path.write_text(source, encoding="utf-8")
subprocess.run([sys.executable, str(script_path)], check=False)