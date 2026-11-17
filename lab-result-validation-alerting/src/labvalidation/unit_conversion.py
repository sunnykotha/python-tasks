from decimal import Decimal, InvalidOperation


class UnitConversionError(ValueError):
    """Raised when a result cannot be converted safely."""


def _canonical_test(test_code: str) -> str:
    normalized = "".join(
        character for character in str(test_code).casefold()
        if character.isalnum()
    )
    if "glucose" in normalized or normalized in ("glu", "glc"):
        return "glucose"
    if "creatinine" in normalized or normalized in ("creat", "cr"):
        return "creatinine"
    return normalized


def _canonical_test_code(test_code: str) -> str:
    """Normalize supported test names without changing their meaning."""
    if not isinstance(test_code, str):
        raise UnitConversionError("Test code must be text.")
    return test_code.strip().casefold()

def _canonical_unit(unit: str) -> str:
    cleaned = (
        unit.strip()
        .replace("Î¼", "µ")
        .replace("Âµ", "µ")
        .replace("μ", "µ")
    )
    lowered = cleaned.casefold()
    if lowered == "mg/dl":
        return "mg/dL"
    if lowered == "mmol/l":
        return "mmol/L"
    if lowered in ("umol/l", "µmol/l"):
        return "µmol/L"
    return cleaned


def _is_creatinine_unit(unit: str) -> bool:
    return _canonical_unit(unit) == "µmol/L"


def normalize_value(test_code: str, value: str, source_unit: str,
                    target_unit: str) -> Decimal:
    if not isinstance(source_unit, str) or not isinstance(target_unit, str):
        raise UnitConversionError("Source and target units must be text.")

    try:
        numeric_value = Decimal(str(value))
    except (InvalidOperation, AttributeError, TypeError):
        raise UnitConversionError(
            f"Value {value!r} is not a plain numeric value."
        ) from None

    if not numeric_value.is_finite():
        raise UnitConversionError("Value must be finite.")

    source = _canonical_unit(source_unit)
    target = _canonical_unit(target_unit)

    if source == target:
        return numeric_value

    test = _canonical_test_code(test_code)

    if test == "glucose" and source == "mg/dL" and target == "mmol/L":
        return numeric_value * Decimal("0.0555")

    if test == "glucose" and source == "mmol/L" and target == "mg/dL":
        return numeric_value / Decimal("0.0555")

    if test == "creatinine" and source == "µmol/L" and target == "mg/dL":
        return numeric_value / Decimal("88.4")

    if test == "creatinine" and source == "mg/dL" and target == "µmol/L":
        return numeric_value * Decimal("88.4")

    raise UnitConversionError(
        f"Unsupported conversion: {test_code} {source_unit} to {target_unit}."
    )
