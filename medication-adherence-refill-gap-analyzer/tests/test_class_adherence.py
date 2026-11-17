from datetime import date, timedelta

from adherence.class_adherence import (
    calculate_class_coverage_days,
    calculate_class_pdc,
)
from adherence.models import Drug, FillEvent, MeasurementPeriod


def make_period(start, days):
    return MeasurementPeriod(
        start,
        start + timedelta(days=days - 1),
    )


def make_fill(patient_id, drug_id, fill_date, days_supply):
    return FillEvent(patient_id, drug_id, fill_date, days_supply)


def test_switching_drugs_in_same_class_preserves_coverage():
    start = date(2026, 1, 1)
    period = make_period(start, 60)

    drugs = [
        Drug("D001", "antihypertensive"),
        Drug("D002", "antihypertensive"),
    ]
    fills = [
        make_fill("P001", "D001", start, 30),
        make_fill("P001", "D002", date(2026, 1, 31), 30),
    ]

    covered = calculate_class_coverage_days(
        "P001",
        "antihypertensive",
        drugs,
        fills,
        period,
    )

    assert len(covered) == 60
    assert date(2026, 1, 30) in covered
    assert date(2026, 1, 31) in covered
    assert date(2026, 3, 1) in covered


def test_fills_from_another_class_do_not_contribute():
    start = date(2026, 1, 1)
    period = make_period(start, 60)

    drugs = [
        Drug("D001", "antihypertensive"),
        Drug("D002", "antidiabetic"),
    ]
    fills = [
        make_fill("P001", "D001", start, 10),
        make_fill("P001", "D002", start, 30),
    ]

    covered = calculate_class_coverage_days(
        "P001",
        "antihypertensive",
        drugs,
        fills,
        period,
    )

    assert len(covered) == 10


def test_fills_from_another_patient_do_not_contribute():
    start = date(2026, 1, 1)
    period = make_period(start, 60)

    drugs = [Drug("D001", "antihypertensive")]
    fills = [
        make_fill("P001", "D001", start, 10),
        make_fill("P002", "D001", start, 30),
    ]

    covered = calculate_class_coverage_days(
        "P001",
        "antihypertensive",
        drugs,
        fills,
        period,
    )

    assert len(covered) == 10


def test_class_coverage_does_not_double_count_overlaps():
    start = date(2026, 1, 1)
    period = make_period(start, 60)

    drugs = [
        Drug("D001", "antihypertensive"),
        Drug("D002", "antihypertensive"),
    ]
    fills = [
        make_fill("P001", "D001", start, 30),
        make_fill("P001", "D002", date(2026, 1, 20), 30),
    ]

    covered = calculate_class_coverage_days(
        "P001",
        "antihypertensive",
        drugs,
        fills,
        period,
    )

    assert len(covered) == 60
    assert len(covered) <= period.days


def test_class_pdc_uses_full_measurement_period():
    start = date(2026, 1, 1)
    period = make_period(start, 100)

    drugs = [Drug("D001", "antihypertensive")]
    fills = [make_fill("P001", "D001", start, 80)]

    result = calculate_class_pdc(
        "P001",
        "antihypertensive",
        drugs,
        fills,
        period,
    )

    assert result.covered_days == 80
    assert result.period_days == 100
    assert result.pdc == 0.80
    assert result.adherent is True


def test_unknown_class_returns_zero_coverage():
    start = date(2026, 1, 1)
    period = make_period(start, 30)

    drugs = [Drug("D001", "antihypertensive")]
    fills = [make_fill("P001", "D001", start, 30)]

    result = calculate_class_pdc(
        "P001",
        "unknown-class",
        drugs,
        fills,
        period,
    )

    assert result.covered_days == 0
    assert result.pdc == 0.0
    assert result.adherent is False


def test_class_pdc_never_exceeds_one_hundred_percent():
    start = date(2026, 1, 1)
    period = make_period(start, 30)

    drugs = [
        Drug("D001", "antihypertensive"),
        Drug("D002", "antihypertensive"),
    ]
    fills = [
        make_fill("P001", "D001", start, 90),
        make_fill("P001", "D002", date(2026, 1, 2), 90),
    ]

    result = calculate_class_pdc(
        "P001",
        "antihypertensive",
        drugs,
        fills,
        period,
    )

    assert result.covered_days == 30
    assert result.pdc == 1.0