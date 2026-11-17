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
