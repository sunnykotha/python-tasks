from pathlib import Path
import subprocess

project = Path(r"C:\Users\GK\lab-result-validation-alerting")
python = project / ".venv" / "Scripts" / "python.exe"

service = r'''
from decimal import Decimal, InvalidOperation


class UnitConversionError(ValueError):
    """Raised when a result cannot be converted safely."""


CONVERSIONS = {
    ("glucose", "mg/dL", "mmol/L"): Decimal("0.0555"),
    ("creatinine", "umol/L", "mg/dL"): Decimal(1) / Decimal("88.4"),
}


def normalize_value(test_code: str, value: str, source_unit: str,
                    target_unit: str) -> Decimal:
    try:
        numeric_value = Decimal(value.strip())
    except (InvalidOperation, AttributeError):
        raise UnitConversionError(
            f"Value {value!r} is not a plain numeric value."
        ) from None

    if not numeric_value.is_finite():
        raise UnitConversionError("Value must be finite.")

    if source_unit == target_unit:
        return numeric_value

    key = (test_code.strip().lower(), source_unit, target_unit)
    factor = CONVERSIONS.get(key)

    if factor is None:
        raise UnitConversionError(
            f"Unsupported conversion: {test_code} {source_unit} to {target_unit}."
        )

    return numeric_value * factor
'''

tests = r'''
from decimal import Decimal
import pytest

from labvalidation.unit_conversion import (
    normalize_value, UnitConversionError
)


def test_glucose_mg_dl_to_mmol_l():
    result = normalize_value("glucose", "100", "mg/dL", "mmol/L")
    assert result == Decimal("5.5500")


def test_creatinine_umol_l_to_mg_dl():
    result = normalize_value("creatinine", "88.4", "umol/L", "mg/dL")
    assert result == Decimal("1")


def test_same_unit_keeps_value():
    result = normalize_value("glucose", "101.25", "mg/dL", "mg/dL")
    assert result == Decimal("101.25")


def test_unsupported_conversion_raises_error():
    with pytest.raises(UnitConversionError, match="Unsupported conversion"):
        normalize_value("potassium", "4.2", "mg/dL", "mmol/L")


def test_non_numeric_result_is_rejected():
    with pytest.raises(UnitConversionError, match="not a plain numeric"):
        normalize_value("glucose", "positive", "mg/dL", "mmol/L")


def test_non_finite_value_is_rejected():
    with pytest.raises(UnitConversionError, match="finite"):
        normalize_value("glucose", "NaN", "mg/dL", "mmol/L")


def test_negative_numeric_value_can_be_normalized():
    result = normalize_value("glucose", "-2", "mg/dL", "mmol/L")
    assert result == Decimal("-0.1110")


def test_test_code_matching_is_case_insensitive():
    result = normalize_value("GLUCOSE", "100", "mg/dL", "mmol/L")
    assert result == Decimal("5.5500")
'''

(project / "src/labvalidation/unit_conversion.py").write_text(
    service.lstrip(), encoding="utf-8"
)
(project / "tests/test_unit_conversion.py").write_text(
    tests.lstrip(), encoding="utf-8"
)

result = subprocess.run(
    [str(python), "-m", "pytest", "-v"],
    cwd=project,
)

if result.returncode == 0:
    print("\nSTEP 4 PASSED: Unit conversion tests passed.")
else:
    print(f"\nSTEP 4 FAILED: pytest returned {result.returncode}.")