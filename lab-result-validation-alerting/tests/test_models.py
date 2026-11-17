from datetime import datetime, timezone
import pytest

from labvalidation.models import (
    Unit, LabTestDefinition, ReferenceRange, LabResult, PreviousResult,
    CriticalAlert, EscalationStep, Sex, ResultFlag, AlertStatus
)


@pytest.fixture
def sample():
    unit = Unit("mmol/L", "millimoles per litre")
    test = LabTestDefinition("K", "Potassium", unit)
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


def test_reference_range_supports_age_and_sex(sample):
    unit, _, _ = sample
    reference = ReferenceRange(
        "K", 3.5, 5.1, unit,
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


def test_escalation_step_records_readback():
    step = EscalationStep(
        "A001", "charge_nurse",
        datetime.now(timezone.utc),
        read_back="Potassium 6.9 mmol/L confirmed",
    )
    assert step.recipient_role == "charge_nurse"
    assert step.read_back is not None


def test_critical_alert_creation():
    alert = CriticalAlert(
        "A001", "R001", ResultFlag.CRITICAL_HIGH,
        datetime.now(timezone.utc),
    )
    assert alert.status == AlertStatus.OPEN


def test_critical_alert_rejects_normal_flag():
    with pytest.raises(ValueError):
        CriticalAlert(
            "A002", "R001", ResultFlag.NORMAL,
            datetime.now(timezone.utc),
        )


def test_invalid_reference_range_is_rejected(sample):
    unit, _, _ = sample
    with pytest.raises(ValueError):
        ReferenceRange("K", 6.0, 3.0, unit)


def test_negative_patient_age_is_rejected(sample):
    _, test, _ = sample
    with pytest.raises(ValueError):
        LabResult(
            "R002", "P002", test, "4.0", test.default_unit,
            datetime.now(timezone.utc), patient_age_days=-1,
        )


def test_empty_unit_is_rejected():
    with pytest.raises(ValueError):
        Unit("", "unknown")