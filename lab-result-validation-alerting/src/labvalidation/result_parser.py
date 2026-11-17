from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re


class ResultParseError(ValueError):
    """Raised when a laboratory result cannot be parsed safely."""


@dataclass(frozen=True)
class ParsedResult:
    raw_value: str
    kind: str
    numeric_value: Decimal | None = None
    comparator: str | None = None
    qualitative_value: str | None = None


QUALITATIVE_VALUES = {
    "positive": "POSITIVE",
    "negative": "NEGATIVE",
    "detected": "DETECTED",
    "not detected": "NOT_DETECTED",
    "present": "PRESENT",
    "absent": "ABSENT",
    "reactive": "REACTIVE",
    "non-reactive": "NON_REACTIVE",
    "nonreactive": "NON_REACTIVE",
    "indeterminate": "INDETERMINATE",
    "inconclusive": "INCONCLUSIVE",
}


def parse_result(value: str) -> ParsedResult:
    if not isinstance(value, str):
        raise ResultParseError("Result must be supplied as text.")

    raw = value.strip()
    if not raw:
        raise ResultParseError("Result cannot be empty.")

    match = re.fullmatch(r"(<=|>=|<|>)\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))", raw)
    if match:
        comparator, number_text = match.groups()
        try:
            number = Decimal(number_text)
        except InvalidOperation:
            raise ResultParseError("Invalid numeric comparison value.") from None
        if not number.is_finite():
            raise ResultParseError("Numeric result must be finite.")
        return ParsedResult(
            raw_value=raw,
            kind="COMPARISON",
            numeric_value=number,
            comparator=comparator,
        )

    try:
        number = Decimal(raw)
        if number.is_finite():
            return ParsedResult(
                raw_value=raw,
                kind="NUMERIC",
                numeric_value=number,
            )
    except InvalidOperation:
        pass

    qualitative = QUALITATIVE_VALUES.get(raw.casefold())
    if qualitative is not None:
        return ParsedResult(
            raw_value=raw,
            kind="QUALITATIVE",
            qualitative_value=qualitative,
        )

    raise ResultParseError(f"Unrecognized laboratory result: {raw!r}.")
