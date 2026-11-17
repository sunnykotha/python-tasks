from pathlib import Path
import subprocess

project = Path(r"C:\Users\GK\lab-result-validation-alerting")
python = project / ".venv" / "Scripts" / "python.exe"

service = r'''
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
'''

tests = r'''
from decimal import Decimal
import pytest

from labvalidation.result_parser import parse_result, ResultParseError


def test_parses_plain_integer():
    result = parse_result("4")
    assert result.kind == "NUMERIC"
    assert result.numeric_value == Decimal("4")


def test_parses_decimal_value():
    result = parse_result("4.7")
    assert result.kind == "NUMERIC"
    assert result.numeric_value == Decimal("4.7")


def test_parses_leading_decimal():
    assert parse_result(".05").numeric_value == Decimal(".05")


def test_parses_less_than_result():
    result = parse_result("<0.01")
    assert result.kind == "COMPARISON"
    assert result.comparator == "<"
    assert result.numeric_value == Decimal("0.01")


def test_parses_greater_than_result_with_spaces():
    result = parse_result("> 200")
    assert result.kind == "COMPARISON"
    assert result.comparator == ">"
    assert result.numeric_value == Decimal("200")


def test_parses_inclusive_comparators():
    assert parse_result("<=5").comparator == "<="
    assert parse_result(">=5").comparator == ">="


def test_parses_negative_numeric_value():
    assert parse_result("-2.5").numeric_value == Decimal("-2.5")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Positive", "POSITIVE"),
        ("negative", "NEGATIVE"),
        ("Detected", "DETECTED"),
        ("not detected", "NOT_DETECTED"),
        ("Reactive", "REACTIVE"),
        ("non-reactive", "NON_REACTIVE"),
        ("Indeterminate", "INDETERMINATE"),
    ],
)
def test_parses_qualitative_values(raw, expected):
    result = parse_result(raw)
    assert result.kind == "QUALITATIVE"
    assert result.qualitative_value == expected


@pytest.mark.parametrize("raw", ["", "   ", "unknown-result", "<", ">", "NaN", "Infinity"])
def test_rejects_invalid_values(raw):
    with pytest.raises(ResultParseError):
        parse_result(raw)


def test_rejects_non_text_input():
    with pytest.raises(ResultParseError, match="text"):
        parse_result(4.7)
'''

(project / "src/labvalidation/result_parser.py").write_text(
    service.lstrip(), encoding="utf-8"
)
(project / "tests/test_result_parser.py").write_text(
    tests.lstrip(), encoding="utf-8"
)

result = subprocess.run(
    [str(python), "-m", "pytest", "-v"],
    cwd=project,
)

if result.returncode == 0:
    print("\nSTEP 5 PASSED: Result parsing tests passed.")
if result.returncode != 0:
    print(f"\nSTEP 5 FAILED: pytest returned {result.returncode}.")