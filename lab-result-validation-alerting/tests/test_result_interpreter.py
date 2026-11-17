from decimal import Decimal
import pytest

from labvalidation.models import ResultFlag
from labvalidation.result_interpreter import (
    interpret_result, InterpretationError
)


def test_normal_result():
    assert interpret_result(4.0, 3.5, 5.0) == ResultFlag.NORMAL


def test_low_result():
    assert interpret_result(3.0, 3.5, 5.0) == ResultFlag.LOW


def test_high_result():
    assert interpret_result(5.5, 3.5, 5.0) == ResultFlag.HIGH


def test_reference_boundaries_are_normal():
    assert interpret_result(3.5, 3.5, 5.0) == ResultFlag.NORMAL
    assert interpret_result(5.0, 3.5, 5.0) == ResultFlag.NORMAL


def test_critical_low_potassium():
    assert interpret_result(2.7, 3.5, 5.0, critical_low=2.8, critical_high=6.2) == ResultFlag.CRITICAL_LOW


def test_critical_high_potassium():
    assert interpret_result(6.3, 3.5, 5.0, critical_low=2.8, critical_high=6.2) == ResultFlag.CRITICAL_HIGH


def test_exact_critical_threshold_is_not_beyond_threshold():
    assert interpret_result(2.8, 3.5, 5.0, critical_low=2.8, critical_high=6.2) == ResultFlag.LOW
    assert interpret_result(6.2, 3.5, 5.0, critical_low=2.8, critical_high=6.2) == ResultFlag.HIGH


def test_critical_thresholds_are_optional():
    assert interpret_result(2.0, 3.5, 5.0) == ResultFlag.LOW
    assert interpret_result(7.0, 3.5, 5.0) == ResultFlag.HIGH


def test_decimal_values_are_supported():
    assert interpret_result(Decimal("2.79"), 3.5, 5.0, critical_low=2.8) == ResultFlag.CRITICAL_LOW


def test_invalid_reference_range_is_rejected():
    with pytest.raises(InterpretationError, match="cannot exceed"):
        interpret_result(4.0, 5.0, 3.0)


def test_critical_low_must_not_exceed_reference_low():
    with pytest.raises(InterpretationError, match="Critical-low"):
        interpret_result(4.0, 3.5, 5.0, critical_low=3.6)


def test_critical_high_must_not_be_below_reference_high():
    with pytest.raises(InterpretationError, match="Critical-high"):
        interpret_result(4.0, 3.5, 5.0, critical_high=4.9)


def test_non_finite_values_are_rejected():
    with pytest.raises(InterpretationError, match="finite"):
        interpret_result("NaN", 3.5, 5.0)
