from decimal import Decimal
from labvalidation.models import ResultFlag


class InterpretationError(ValueError):
    """Raised when a result cannot be safely interpreted."""


def interpret_result(value, reference_low, reference_high,
                     critical_low=None, critical_high=None):
    value = Decimal(str(value))
    low = Decimal(str(reference_low))
    high = Decimal(str(reference_high))

    if not value.is_finite() or not low.is_finite() or not high.is_finite():
        raise InterpretationError("Values and reference limits must be finite.")

    if low > high:
        raise InterpretationError("Reference low cannot exceed reference high.")

    if critical_low is not None:
        critical_low = Decimal(str(critical_low))
        if not critical_low.is_finite():
            raise InterpretationError("Critical limits must be finite.")
        if critical_low > low:
            raise InterpretationError("Critical-low threshold cannot exceed reference low.")

    if critical_high is not None:
        critical_high = Decimal(str(critical_high))
        if not critical_high.is_finite():
            raise InterpretationError("Critical limits must be finite.")
        if critical_high < high:
            raise InterpretationError("Critical-high threshold cannot be below reference high.")

    if critical_low is not None and value < critical_low:
        return ResultFlag.CRITICAL_LOW

    if critical_high is not None and value > critical_high:
        return ResultFlag.CRITICAL_HIGH

    if value < low:
        return ResultFlag.LOW

    if value > high:
        return ResultFlag.HIGH

    return ResultFlag.NORMAL
