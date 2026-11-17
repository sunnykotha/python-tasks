from datetime import date, timedelta

import pytest

from adherence.coverage import calculate_coverage_days
from adherence.models import (
    FillEvent,
    Hospitalization,
    MeasurementPeriod,
)


def make_period(start, days):
    return MeasurementPeriod(start, start + timedelta(days=days - 1))


def test_hospitalization_extends_outpatient_supply():
    start = date(2026, 1, 1)
    period = make_period(start, 40)
    fills = [FillEvent("P001", "D001", start, 10)]
    hospitalizations = [
        Hospitalization(
            "P001",
            date(2026, 1, 5),
            date(2026, 1, 9),
        )
    ]

    covered = calculate_coverage_days(
        fills,
        period,
        patient_id="P001",
        hospitalizations=hospitalizations,
    )

    assert len(covered) == 15
    assert date(2026, 1, 10) in covered
    assert date(2026, 1, 15) in covered
    assert date(2026, 1, 16) not in covered


def test_hospitalization_days_count_as_covered():
    start = date(2026, 1, 1)
    period = make_period(start, 30)
    hospitalizations = [
        Hospitalization(
            "P001",
            date(2026, 1, 10),
            date(2026, 1, 12),
        )
    ]

    covered = calculate_coverage_days(
        [],
        period,
        patient_id="P001",
        hospitalizations=hospitalizations,
    )

    assert covered == {
        date(2026, 1, 10),
        date(2026, 1, 11),
        date(2026, 1, 12),
    }


def test_other_patient_hospitalization_does_not_extend_supply():
    start = date(2026, 1, 1)
    period = make_period(start, 30)
    fills = [FillEvent("P001", "D001", start, 10)]
    hospitalizations = [
        Hospitalization(
            "P002",
            date(2026, 1, 5),
            date(2026, 1, 9),
        )
    ]

    covered = calculate_coverage_days(
        fills,
        period,
        patient_id="P001",
        hospitalizations=hospitalizations,
    )

    assert len(covered) == 10


def test_dose_change_changes_effective_supply():
    fill = FillEvent(
        "P001",
        "D001",
        date(2026, 1, 1),
        days_supply=30,
        quantity=60,
        daily_dose=2,
    )

    assert fill.effective_days_supply == 30


def test_higher_daily_dose_shortens_effective_supply():
    fill = FillEvent(
        "P001",
        "D001",
        date(2026, 1, 1),
        days_supply=30,
        quantity=60,
        daily_dose=4,
    )

    assert fill.effective_days_supply == 15


def test_lower_daily_dose_extends_effective_supply():
    fill = FillEvent(
        "P001",
        "D001",
        date(2026, 1, 1),
        days_supply=30,
        quantity=60,
        daily_dose=1,
    )

    assert fill.effective_days_supply == 60


def test_dose_adjusted_supply_drives_coverage():
    start = date(2026, 1, 1)
    period = make_period(start, 30)
    fill = FillEvent(
        "P001",
        "D001",
        start,
        days_supply=30,
        quantity=60,
        daily_dose=4,
    )

    covered = calculate_coverage_days([fill], period)

    assert len(covered) == 15
    assert date(2026, 1, 15) in covered
    assert date(2026, 1, 16) not in covered


def test_quantity_and_dose_must_be_provided_together():
    with pytest.raises(ValueError, match="supplied together"):
        FillEvent(
            "P001",
            "D001",
            date(2026, 1, 1),
            30,
            quantity=60,
        )


@pytest.mark.parametrize(
    ("quantity", "daily_dose"),
    [(0, 1), (10, 0), (-1, 1), (10, -2)],
)
def test_quantity_and_dose_must_be_positive(quantity, daily_dose):
    with pytest.raises(ValueError, match="must be positive"):
        FillEvent(
            "P001",
            "D001",
            date(2026, 1, 1),
            30,
            quantity=quantity,
            daily_dose=daily_dose,
        )


def test_dose_change_can_make_supply_invalid():
    fill = FillEvent(
        "P001",
        "D001",
        date(2026, 1, 1),
        days_supply=30,
        quantity=1,
        daily_dose=2,
    )

    assert fill.effective_days_supply == 0
    assert fill.has_valid_supply is False
def test_overlapping_hospitalizations_do_not_extend_supply_twice_for_same_day():
    start = date(2026, 1, 1)
    period = make_period(start, 40)
    fills = [FillEvent("P001", "D001", start, 10)]
    hospitalizations = [
        Hospitalization("P001", date(2026, 1, 5), date(2026, 1, 9)),
        Hospitalization("P001", date(2026, 1, 8), date(2026, 1, 11)),
    ]

    covered = calculate_coverage_days(
        fills,
        period,
        patient_id="P001",
        hospitalizations=hospitalizations,
    )

    # Unique inpatient dates Jan 5-11 extend the 10-day supply to Jan 17.
    assert len(covered) == 17
    assert date(2026, 1, 17) in covered
    assert date(2026, 1, 18) not in covered


def test_hospitalization_extending_past_initial_supply_end_extends_supply():
    start = date(2026, 1, 1)
    period = make_period(start, 40)
    fills = [FillEvent("P001", "D001", start, 5)]
    hospitalizations = [
        Hospitalization("P001", date(2026, 1, 4), date(2026, 1, 10)),
    ]

    covered = calculate_coverage_days(
        fills,
        period,
        patient_id="P001",
        hospitalizations=hospitalizations,
    )

    # The stay overlaps the supply, so inpatient days extend its end.
    assert len(covered) == 12
    assert date(2026, 1, 12) in covered
    assert date(2026, 1, 13) not in covered
def test_hospitalization_after_supply_expires_does_not_extend_old_supply():
    start = date(2026, 1, 1)
    period = make_period(start, 30)
    fills = [FillEvent("P001", "D001", start, 5)]
    hospitalizations = [
        Hospitalization("P001", date(2026, 1, 10), date(2026, 1, 12)),
    ]

    covered = calculate_coverage_days(
        fills, period, patient_id="P001", hospitalizations=hospitalizations
    )

    assert len(covered) == 8
    assert date(2026, 1, 5) in covered
    assert date(2026, 1, 9) not in covered
    assert date(2026, 1, 10) in covered
    assert date(2026, 1, 12) in covered
    assert date(2026, 1, 13) not in covered
