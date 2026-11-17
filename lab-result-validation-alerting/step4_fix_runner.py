from pathlib import Path
import subprocess

project = Path(r"C:\Users\GK\lab-result-validation-alerting")
python = project / ".venv" / "Scripts" / "python.exe"

service = r'''
from decimal import Decimal, InvalidOperation


class UnitConversionError(ValueError):
    """Raised when a result cannot be converted safely."""


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

    test = test_code.strip().lower()
    if test == "glucose" and source_unit == "mg/dL" and target_unit == "mmol/L":
        return numeric_value * Decimal("0.0555")

    if test == "glucose" and source_unit == "mmol/L" and target_unit == "mg/dL":
        return numeric_value / Decimal("0.0555")

    if test == "creatinine" and source_unit in ("umol/L", "µmol/L", "μmol/L") and target_unit == "mg/dL":
        return numeric_value / Decimal("88.4")

    if test == "creatinine" and source_unit == "mg/dL" and target_unit in ("umol/L", "µmol/L", "μmol/L"):
        return numeric_value * Decimal("88.4")

    raise UnitConversionError(
        f"Unsupported conversion: {test_code} {source_unit} to {target_unit}."
    )
'''

(project / "src/labvalidation/unit_conversion.py").write_text(
    service.lstrip(), encoding="utf-8"
)

result = subprocess.run(
    [str(python), "-m", "pytest", "-v"],
    cwd=project,
)

if result.returncode == 0:
    print("\nSTEP 4 PASSED: Unit conversion tests passed.")
if result.returncode != 0:
    print(f"\nSTEP 4 FAILED: pytest returned {result.returncode}.")