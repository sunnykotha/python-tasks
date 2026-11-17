from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation


class DeltaCheckError(ValueError):
    """Raised when a delta comparison cannot be performed safely."""


@dataclass(frozen=True)
class DeltaCheck:
    significant_change: bool
    difference: Decimal | None
    elapsed: timedelta | None
    reason: str


def check_delta(current, previous, threshold, window, direction="any"):
    if direction not in ("any", "decrease", "increase"):
        raise DeltaCheckError("Direction must be any, decrease, or increase.")

    try:
        limit = Decimal(str(threshold))
    except (InvalidOperation, ValueError):
        raise DeltaCheckError("Threshold must be numeric.") from None

    if not limit.is_finite() or limit <= 0:
        raise DeltaCheckError("Threshold must be finite and greater than zero.")

    if not isinstance(window, timedelta) or window <= timedelta(0):
        raise DeltaCheckError("Window must be a positive timedelta.")

    if previous is None:
        return DeltaCheck(False, None, None, "No previous result available.")

    if current.patient_id != previous.patient_id:
        raise DeltaCheckError("Results belong to different patients.")

    if current.test.code != previous.test.code:
        raise DeltaCheckError("Results belong to different tests.")

    if current.unit.code != previous.unit.code:
        raise DeltaCheckError("Result units differ; convert to a common unit first.")

    if not isinstance(current.collected_at, datetime):
        raise DeltaCheckError("Current collection time must be a datetime.")

    if not isinstance(previous.collected_at, datetime):
        raise DeltaCheckError("Previous collection time must be a datetime.")

    try:
        elapsed = current.collected_at - previous.collected_at
    except TypeError:
        raise DeltaCheckError(
            "Collection timestamps must use compatible time zones."
        ) from None

    if elapsed < timedelta(0):
        raise DeltaCheckError("Previous result was collected after the current result.")

    if elapsed == timedelta(0):
        return DeltaCheck(
            False, None, elapsed,
            "Collection timestamps are identical; delta check skipped."
        )

    if elapsed > window:
        return DeltaCheck(
            False, None, elapsed,
            "Previous result is outside the configured time window."
        )

    try:
        current_value = Decimal(str(current.value))
        previous_value = Decimal(str(previous.value))
    except (InvalidOperation, ValueError, TypeError):
        raise DeltaCheckError("Both result values must be numeric.") from None

    if not current_value.is_finite() or not previous_value.is_finite():
        raise DeltaCheckError("Result values must be finite.")

    difference = current_value - previous_value

    if direction == "decrease":
        significant = difference < -limit
    if direction == "increase":
        significant = difference > limit
    if direction == "any":
        significant = abs(difference) > limit

    if significant:
        return DeltaCheck(
            True, difference, elapsed,
            "Change exceeds the configured threshold."
        )

    return DeltaCheck(
        False, difference, elapsed,
        "Change does not exceed the configured threshold."
    )
