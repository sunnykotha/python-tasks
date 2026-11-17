from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from labvalidation.delta_check import check_delta, DeltaCheckError


BASE_TIME = datetime(2026, 10, 29, 10, 0, 0)


def make_result(value, collected_at, patient="P1",
                test="HEMOGLOBIN", unit="g/dL"):
    return SimpleNamespace(
        value=value,
        collected_at=collected_at,
        patient_id=patient,
        test=SimpleNamespace(code=test),
        unit=SimpleNamespace(code=unit),
    )


def pair(current_value=10, previous_value=14, hours=2):
    previous = make_result(
        previous_value, BASE_TIME - timedelta(hours=hours)
    )
    current = make_result(current_value, BASE_TIME)
    return current, previous


def test_detects_hemoglobin_drop_over_threshold():
    current, previous = pair(10, 14)
    result = check_delta(
        current, previous, threshold=3,
        window=timedelta(hours=24), direction="decrease"
    )
    assert result.significant_change is True
    assert result.difference == Decimal("-4")


def test_exact_threshold_is_not_significant():
    current, previous = pair(11, 14)
    result = check_delta(
        current, previous, 3, timedelta(hours=24), "decrease"
    )
    assert result.significant_change is False
    assert result.difference == Decimal("-3")


def test_detects_increase():
    current, previous = pair(15, 10)
    result = check_delta(
        current, previous, 3, timedelta(hours=24), "increase"
    )
    assert result.significant_change is True
    assert result.difference == Decimal("5")


def test_any_direction_detects_large_change():
    current, previous = pair(5, 10)
    result = check_delta(
        current, previous, 3, timedelta(hours=24)
    )
    assert result.significant_change is True


def test_change_within_threshold_is_not_significant():
    current, previous = pair(13, 14)
    result = check_delta(
        current, previous, 3, timedelta(hours=24)
    )
    assert result.significant_change is False


def test_missing_previous_result_is_handled():
    current = make_result(10, BASE_TIME)
    result = check_delta(
        current, None, 3, timedelta(hours=24)
    )
    assert result.significant_change is False
    assert result.difference is None
    assert "No previous" in result.reason


def test_result_outside_time_window_is_skipped():
    current, previous = pair(5, 14, hours=25)
    result = check_delta(
        current, previous, 3, timedelta(hours=24)
    )
    assert result.significant_change is False
    assert "outside" in result.reason


def test_result_exactly_at_window_boundary_is_checked():
    current, previous = pair(5, 14, hours=24)
    result = check_delta(
        current, previous, 3, timedelta(hours=24)
    )
    assert result.significant_change is True


def test_different_patients_are_rejected():
    current, previous = pair()
    previous.patient_id = "P2"
    with pytest.raises(DeltaCheckError, match="different patients"):
        check_delta(current, previous, 3, timedelta(hours=24))


def test_different_tests_are_rejected():
    current, previous = pair()
    previous.test = SimpleNamespace(code="POTASSIUM")
    with pytest.raises(DeltaCheckError, match="different tests"):
        check_delta(current, previous, 3, timedelta(hours=24))


def test_different_units_are_rejected():
    current, previous = pair()
    previous.unit = SimpleNamespace(code="mmol/L")
    with pytest.raises(DeltaCheckError, match="units differ"):
        check_delta(current, previous, 3, timedelta(hours=24))


def test_future_previous_result_is_rejected():
    current = make_result(10, BASE_TIME)
    previous = make_result(14, BASE_TIME + timedelta(hours=1))
    with pytest.raises(DeltaCheckError, match="after the current"):
        check_delta(current, previous, 3, timedelta(hours=24))


def test_invalid_threshold_is_rejected():
    current, previous = pair()
    with pytest.raises(DeltaCheckError, match="greater than zero"):
        check_delta(current, previous, 0, timedelta(hours=24))


def test_invalid_direction_is_rejected():
    current, previous = pair()
    with pytest.raises(DeltaCheckError, match="Direction"):
        check_delta(
            current, previous, 3, timedelta(hours=24), "sideways"
        )


def test_non_numeric_value_is_rejected():
    current, previous = pair("Positive", 14)
    with pytest.raises(DeltaCheckError, match="numeric"):
        check_delta(current, previous, 3, timedelta(hours=24))
