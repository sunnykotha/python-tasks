from datetime import date, timedelta

import pytest

from adherence.coverage import calculate_coverage_days
from adherence.models import FillEvent, MeasurementPeriod


def make_fill(fill_date, days_supply, patient_id="P001", drug_id="D001"):
    return FillEvent(patient_id, drug_id, fill_date, days_supply)


def make_period(start, days):
    return MeasurementPeriod(
        start,
        start + timedelta(days=days - 1),
    )


def test_single_fill_covers_its_supply_days():
    start = date(2026, 1, 1)
    period = make_period(start, 30)

    covered = calculate_coverage_days(
        [make_fill(start, 10)],
        period,
    )

    assert len(covered) == 10
    assert min(covered) == date(2026, 1, 1)
    assert max(covered) == date(2026, 1, 10)


def test_early_refill_carries_unused_supply_forward():
    start = date(2026, 1, 1)
    period = make_period(start, 180)

    fills = [
        make_fill(date(2026, 1, 1), 90),
        make_fill(date(2026, 3, 15), 90),
    ]

    covered = calculate_coverage_days(fills, period)

    assert len(covered) == 180
    assert date(2026, 3, 31) in covered
    assert date(2026, 4, 1) in covered
    assert date(2026, 6, 29) in covered
    assert date(2026, 6, 30) not in covered


def test_refill_after_supply_runs_out_creates_gap():
    start = date(2026, 1, 1)
    period = make_period(start, 40)

    fills = [
        make_fill(date(2026, 1, 1), 10),
        make_fill(date(2026, 1, 15), 10),
    ]

    covered = calculate_coverage_days(fills, period)

    assert len(covered) == 20
    assert date(2026, 1, 10) in covered
    assert date(2026, 1, 11) not in covered
    assert date(2026, 1, 14) not in covered
    assert date(2026, 1, 15) in covered


def test_overlapping_fills_do_not_double_count_days():
    start = date(2026, 1, 1)
    period = make_period(start, 60)

    fills = [
        make_fill(date(2026, 1, 1), 30),
        make_fill(date(2026, 1, 20), 30),
    ]

    covered = calculate_coverage_days(fills, period)

    assert len(covered) == 60
    assert len(covered) <= period.days


def test_multiple_fills_on_same_day_accumulate_supply():
    start = date(2026, 1, 1)
    period = make_period(start, 30)

    fills = [
        make_fill(start, 10),
        make_fill(start, 5),
    ]

    covered = calculate_coverage_days(fills, period)

    assert len(covered) == 15
    assert date(2026, 1, 15) in covered
    assert date(2026, 1, 16) not in covered


@pytest.mark.parametrize("days_supply", [None, 0])
def test_missing_or_zero_supply_does_not_add_coverage(days_supply):
    start = date(2026, 1, 1)
    period = make_period(start, 30)

    fills = [
        make_fill(start, days_supply),
        make_fill(date(2026, 1, 5), 5),
    ]

    covered = calculate_coverage_days(fills, period)

    assert len(covered) == 5
    assert date(2026, 1, 1) not in covered
    assert date(2026, 1, 5) in covered


def test_coverage_is_clipped_to_measurement_period():
    start = date(2026, 1, 10)
    period = make_period(start, 5)

    fills = [make_fill(date(2026, 1, 1), 30)]

    covered = calculate_coverage_days(fills, period)

    assert len(covered) == 5
    assert min(covered) == date(2026, 1, 10)
    assert max(covered) == date(2026, 1, 14)


def test_coverage_is_filtered_by_patient():
    start = date(2026, 1, 1)
    period = make_period(start, 30)

    fills = [
        make_fill(start, 10, patient_id="P001"),
        make_fill(start, 20, patient_id="P002"),
    ]

    covered = calculate_coverage_days(
        fills,
        period,
        patient_id="P001",
    )

    assert len(covered) == 10


def test_coverage_is_filtered_by_drug():
    start = date(2026, 1, 1)
    period = make_period(start, 30)

    fills = [
        make_fill(start, 10, drug_id="D001"),
        make_fill(start, 20, drug_id="D002"),
    ]

    covered = calculate_coverage_days(
        fills,
        period,
        drug_id="D001",
    )

    assert len(covered) == 10


def test_empty_fills_return_no_covered_days():
    period = make_period(date(2026, 1, 1), 30)

    assert calculate_coverage_days([], period) == set()


def test_gap_is_preserved_after_stockpile_is_exhausted():
    start = date(2026, 1, 1)
    period = make_period(start, 50)

    fills = [
        make_fill(date(2026, 1, 1), 10),
        make_fill(date(2026, 1, 5), 10),
        make_fill(date(2026, 2, 1), 5),
    ]

    covered = calculate_coverage_days(fills, period)

    assert len(covered) == 25
    assert date(2026, 1, 20) in covered
    assert date(2026, 1, 21) not in covered
    assert date(2026, 2, 1) in covered


def test_stockpiled_coverage_never_exceeds_period_length():
    period = make_period(date(2026, 1, 1), 30)

    fills = [
        make_fill(date(2026, 1, 1), 90),
        make_fill(date(2026, 1, 2), 90),
        make_fill(date(2026, 1, 3), 90),
    ]

    covered = calculate_coverage_days(fills, period)

    assert len(covered) == 30
    assert len(covered) <= period.days