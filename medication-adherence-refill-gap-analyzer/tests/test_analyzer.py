from datetime import date

import pytest

from adherence.analyzer import analyze_adherence
from adherence.models import Drug, FillEvent, Patient


def test_worked_example_has_continuous_coverage():
    patient = Patient("P001")
    drugs = [Drug("D001", "chronic")]
    fills = [
        FillEvent("P001", "D001", date(2026, 1, 1), 90),
        FillEvent("P001", "D001", date(2026, 3, 15), 90),
    ]

    report = analyze_adherence(
        patient=patient,
        fills=fills,
        drugs=drugs,
        drug_class="chronic",
        period_days=180,
    )

    assert report.measurement_period.start_date == date(2026, 1, 1)
    assert report.measurement_period.end_date == date(2026, 6, 29)
    assert report.covered_days == 180
    assert report.period_days == 180
    assert report.pdc == 1.0
    assert report.adherent is True
    assert report.uncovered_dates == frozenset()


def test_end_to_end_report_includes_refill_gap_dates():
    patient = Patient("P001")
    drugs = [Drug("D001", "chronic")]
    fills = [
        FillEvent("P001", "D001", date(2026, 1, 1), 10),
        FillEvent("P001", "D001", date(2026, 1, 15), 10),
    ]

    report = analyze_adherence(
        patient,
        fills,
        drugs,
        "chronic",
        period_days=30,
    )

    assert report.covered_days == 20
    assert report.period_days == 30
    assert report.pdc == pytest.approx(20 / 30)
    assert date(2026, 1, 11) in report.uncovered_dates
    assert date(2026, 1, 14) in report.uncovered_dates
    assert date(2026, 1, 15) in report.covered_dates


def test_end_to_end_report_truncates_at_death():
    patient = Patient(
        "P001",
        death_date=date(2026, 1, 10),
    )
    drugs = [Drug("D001", "chronic")]
    fills = [FillEvent("P001", "D001", date(2026, 1, 1), 30)]

    report = analyze_adherence(
        patient,
        fills,
        drugs,
        "chronic",
    )

    assert report.period_days == 10
    assert report.covered_days == 10
    assert report.pdc == 1.0


def test_end_to_end_report_supports_drug_switching():
    patient = Patient("P001")
    drugs = [
        Drug("D001", "chronic"),
        Drug("D002", "chronic"),
    ]
    fills = [
        FillEvent("P001", "D001", date(2026, 1, 1), 15),
        FillEvent("P001", "D002", date(2026, 1, 16), 15),
    ]

    report = analyze_adherence(
        patient,
        fills,
        drugs,
        "chronic",
        period_days=30,
    )

    assert report.covered_days == 30
    assert report.pdc == 1.0


def test_end_to_end_report_ignores_other_classes():
    patient = Patient("P001")
    drugs = [
        Drug("D001", "chronic"),
        Drug("D002", "other"),
    ]
    fills = [
        FillEvent("P001", "D001", date(2026, 1, 1), 10),
        FillEvent("P001", "D002", date(2026, 1, 1), 30),
    ]

    report = analyze_adherence(
        patient,
        fills,
        drugs,
        "chronic",
        period_days=30,
    )

    assert report.covered_days == 10
    assert report.pdc == pytest.approx(10 / 30)


def test_end_to_end_report_rejects_class_without_valid_fills():
    patient = Patient("P001")
    drugs = [Drug("D001", "chronic")]
    fills = [FillEvent("P001", "D001", date(2026, 1, 1), 0)]

    with pytest.raises(ValueError, match="valid medication fill"):
        analyze_adherence(
            patient,
            fills,
            drugs,
            "chronic",
        )