from datetime import date

import pytest

from adherence.models import (
    Drug,
    FillEvent,
    Hospitalization,
    MeasurementPeriod,
    PDCResult,
    Patient,
)


def test_patient_creation():
    patient = Patient("P001", death_date=date(2026, 10, 1))

    assert patient.patient_id == "P001"
    assert patient.death_date == date(2026, 10, 1)
    assert patient.disenrollment_date is None


def test_patient_rejects_empty_id():
    with pytest.raises(ValueError):
        Patient(" ")


def test_drug_records_class():
    drug = Drug("D001", "antihypertensive")

    assert drug.drug_id == "D001"
    assert drug.drug_class == "antihypertensive"


def test_drug_rejects_empty_class():
    with pytest.raises(ValueError):
        Drug("D001", "")


@pytest.mark.parametrize("days_supply", [None, 0])
def test_fill_accepts_missing_or_zero_supply(days_supply):
    fill = FillEvent("P001", "D001", date(2026, 1, 1), days_supply)

    assert fill.has_valid_supply is False


def test_fill_accepts_positive_supply():
    fill = FillEvent("P001", "D001", date(2026, 1, 1), 30)

    assert fill.has_valid_supply is True


def test_fill_rejects_negative_supply():
    with pytest.raises(ValueError):
        FillEvent("P001", "D001", date(2026, 1, 1), -1)


def test_hospitalization_counts_both_boundary_days():
    stay = Hospitalization(
        "P001",
        date(2026, 1, 10),
        date(2026, 1, 12),
    )

    assert stay.days == 3


def test_hospitalization_rejects_reversed_dates():
    with pytest.raises(ValueError):
        Hospitalization(
            "P001",
            date(2026, 1, 12),
            date(2026, 1, 10),
        )


def test_measurement_period_counts_both_boundary_days():
    period = MeasurementPeriod(
        date(2026, 1, 1),
        date(2026, 1, 31),
    )

    assert period.days == 31


def test_measurement_period_rejects_reversed_dates():
    with pytest.raises(ValueError):
        MeasurementPeriod(
            date(2026, 2, 1),
            date(2026, 1, 31),
        )


@pytest.mark.parametrize(
    ("covered_days", "period_days", "expected_pdc", "expected_adherent"),
    [
        (80, 100, 0.80, True),
        (79, 100, 0.79, False),
        (100, 100, 1.00, True),
        (0, 100, 0.00, False),
    ],
)
def test_pdc_result(
    covered_days,
    period_days,
    expected_pdc,
    expected_adherent,
):
    result = PDCResult(covered_days, period_days)

    assert result.pdc == expected_pdc
    assert result.adherent is expected_adherent


@pytest.mark.parametrize(
    ("covered_days", "period_days"),
    [
        (-1, 100),
        (101, 100),
        (0, 0),
    ],
)
def test_pdc_result_rejects_invalid_counts(covered_days, period_days):
    with pytest.raises(ValueError):
        PDCResult(covered_days, period_days)