from datetime import date

import pytest

from adherence.measurement_period import calculate_measurement_period
from adherence.models import FillEvent, Patient


def make_fill(fill_date, days_supply=30, patient_id="P001"):
    return FillEvent(
        patient_id,
        "D001",
        fill_date,
        days_supply,
    )


def test_default_period_is_365_inclusive_days():
    patient = Patient("P001")
    fills = [make_fill(date(2026, 1, 1))]

    period = calculate_measurement_period(patient, fills)

    assert period.start_date == date(2026, 1, 1)
    assert period.end_date == date(2026, 12, 31)
    assert period.days == 365


@pytest.mark.parametrize(
    ("period_days", "expected_end", "expected_days"),
    [
        (1, date(2026, 1, 1), 1),
        (30, date(2026, 1, 30), 30),
        (90, date(2026, 3, 31), 90),
        (365, date(2026, 12, 31), 365),
    ],
)
def test_custom_period_length(period_days, expected_end, expected_days):
    patient = Patient("P001")
    fills = [make_fill(date(2026, 1, 1))]

    period = calculate_measurement_period(
        patient,
        fills,
        period_days=period_days,
    )

    assert period.end_date == expected_end
    assert period.days == expected_days


def test_earliest_valid_fill_starts_period():
    patient = Patient("P001")
    fills = [
        make_fill(date(2026, 2, 1)),
        make_fill(date(2026, 1, 10)),
        make_fill(date(2026, 1, 1), days_supply=0),
    ]

    period = calculate_measurement_period(patient, fills)

    assert period.start_date == date(2026, 1, 10)


def test_ignores_fills_for_other_patients():
    patient = Patient("P001")
    fills = [
        make_fill(date(2026, 1, 10), patient_id="P001"),
        make_fill(date(2025, 12, 1), patient_id="P002"),
    ]

    period = calculate_measurement_period(patient, fills)

    assert period.start_date == date(2026, 1, 10)


def test_death_truncates_period_inclusively():
    patient = Patient(
        "P001",
        death_date=date(2026, 6, 30),
    )
    fills = [make_fill(date(2026, 1, 1))]

    period = calculate_measurement_period(patient, fills)

    assert period.end_date == date(2026, 6, 30)
    assert period.days == 181


def test_disenrollment_truncates_period_inclusively():
    patient = Patient(
        "P001",
        disenrollment_date=date(2026, 4, 1),
    )
    fills = [make_fill(date(2026, 1, 1))]

    period = calculate_measurement_period(patient, fills)

    assert period.end_date == date(2026, 4, 1)
    assert period.days == 91


def test_earliest_of_death_and_disenrollment_truncates_period():
    patient = Patient(
        "P001",
        death_date=date(2026, 8, 1),
        disenrollment_date=date(2026, 5, 1),
    )
    fills = [make_fill(date(2026, 1, 1))]

    period = calculate_measurement_period(patient, fills)

    assert period.end_date == date(2026, 5, 1)


def test_event_before_first_fill_does_not_truncate_period():
    patient = Patient(
        "P001",
        disenrollment_date=date(2025, 12, 31),
    )
    fills = [make_fill(date(2026, 1, 1))]

    period = calculate_measurement_period(patient, fills)

    assert period.end_date == date(2026, 12, 31)


@pytest.mark.parametrize("period_days", [0, -1])
def test_rejects_nonpositive_period_length(period_days):
    patient = Patient("P001")
    fills = [make_fill(date(2026, 1, 1))]

    with pytest.raises(ValueError):
        calculate_measurement_period(patient, fills, period_days)


def test_rejects_patient_without_valid_fills():
    patient = Patient("P001")
    fills = [
        make_fill(date(2026, 1, 1), days_supply=None),
        make_fill(date(2026, 1, 2), days_supply=0),
    ]

    with pytest.raises(ValueError, match="valid medication fill"):
        calculate_measurement_period(patient, fills)


def test_rejects_empty_fill_list():
    with pytest.raises(ValueError, match="valid medication fill"):
        calculate_measurement_period(Patient("P001"), [])