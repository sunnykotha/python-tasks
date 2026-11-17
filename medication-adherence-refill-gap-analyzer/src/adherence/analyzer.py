from dataclasses import dataclass
from datetime import date

from adherence.class_adherence import calculate_class_coverage_days
from adherence.measurement_period import calculate_measurement_period
from adherence.models import (
    Drug,
    FillEvent,
    Hospitalization,
    MeasurementPeriod,
    Patient,
    PDCResult,
)


@dataclass(frozen=True)
class AdherenceReport:
    measurement_period: MeasurementPeriod
    covered_dates: frozenset[date]
    uncovered_dates: frozenset[date]
    result: PDCResult

    @property
    def pdc(self) -> float:
        return self.result.pdc

    @property
    def adherent(self) -> bool:
        return self.result.adherent

    @property
    def covered_days(self) -> int:
        return self.result.covered_days

    @property
    def period_days(self) -> int:
        return self.result.period_days


def analyze_adherence(
    patient: Patient,
    fills: list[FillEvent],
    drugs: list[Drug],
    drug_class: str,
    period_days: int = 365,
    hospitalizations: list[Hospitalization] | None = None,
) -> AdherenceReport:
    if not drug_class or not drug_class.strip():
        raise ValueError("Drug class must not be empty.")

    class_drug_ids = {
        drug.drug_id
        for drug in drugs
        if drug.drug_class == drug_class
    }

    class_fills = [
        fill
        for fill in fills
        if fill.patient_id == patient.patient_id
        and fill.drug_id in class_drug_ids
        and fill.has_valid_supply
    ]

    period = calculate_measurement_period(
        patient=patient,
        fills=class_fills,
        period_days=period_days,
    )

    covered_dates = calculate_class_coverage_days(
        patient_id=patient.patient_id,
        drug_class=drug_class,
        drugs=drugs,
        fills=class_fills,
        period=period,
        hospitalizations=hospitalizations,
    )

    all_period_dates = {
        period.start_date.fromordinal(ordinal)
        for ordinal in range(
            period.start_date.toordinal(),
            period.end_date.toordinal() + 1,
        )
    }

    # Defensive clipping guarantees coverage cannot exceed the period.
    covered_dates = covered_dates.intersection(all_period_dates)
    uncovered_dates = all_period_dates - covered_dates

    result = PDCResult(
        covered_days=len(covered_dates),
        period_days=period.days,
    )

    return AdherenceReport(
        measurement_period=period,
        covered_dates=frozenset(covered_dates),
        uncovered_dates=frozenset(uncovered_dates),
        result=result,
    )