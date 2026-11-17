from adherence.coverage import calculate_coverage_days
from adherence.models import (
    Drug,
    FillEvent,
    Hospitalization,
    MeasurementPeriod,
    PDCResult,
)


def calculate_class_coverage_days(
    patient_id: str,
    drug_class: str,
    drugs: list[Drug],
    fills: list[FillEvent],
    period: MeasurementPeriod,
    hospitalizations: list[Hospitalization] | None = None,
) -> set:
    class_drug_ids = {
        drug.drug_id
        for drug in drugs
        if drug.drug_class == drug_class
    }

    class_fills = [
        fill
        for fill in fills
        if fill.patient_id == patient_id
        and fill.drug_id in class_drug_ids
    ]

    return calculate_coverage_days(
        fills=class_fills,
        period=period,
        patient_id=patient_id,
        hospitalizations=hospitalizations,
    )


def calculate_class_pdc(
    patient_id: str,
    drug_class: str,
    drugs: list[Drug],
    fills: list[FillEvent],
    period: MeasurementPeriod,
    hospitalizations: list[Hospitalization] | None = None,
) -> PDCResult:
    covered_days = calculate_class_coverage_days(
        patient_id=patient_id,
        drug_class=drug_class,
        drugs=drugs,
        fills=fills,
        period=period,
        hospitalizations=hospitalizations,
    )

    return PDCResult(
        covered_days=len(covered_days),
        period_days=period.days,
    )