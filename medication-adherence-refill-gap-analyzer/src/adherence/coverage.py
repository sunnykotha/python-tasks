from datetime import date, timedelta

from adherence.models import (
    FillEvent,
    Hospitalization,
    MeasurementPeriod,
)


def _hospital_days_between(
    start: date,
    end: date,
    hospitalizations: list[Hospitalization],
    patient_id: str,
) -> set[date]:
    days: set[date] = set()

    for stay in hospitalizations:
        if stay.patient_id != patient_id:
            continue

        overlap_start = max(start, stay.start_date)
        overlap_end = min(end, stay.end_date)

        if overlap_start <= overlap_end:
            current_day = overlap_start
            while current_day <= overlap_end:
                days.add(current_day)
                current_day += timedelta(days=1)

    return days


def _extended_supply_end(
    start: date,
    supply_days: int,
    hospitalizations: list[Hospitalization],
    patient_id: str,
) -> date:
    end = start + timedelta(days=supply_days - 1)

    while True:
        inpatient_days = _hospital_days_between(
            start,
            end,
            hospitalizations,
            patient_id,
        )
        extended_end = start + timedelta(
            days=supply_days + len(inpatient_days) - 1
        )

        if extended_end == end:
            return end

        end = extended_end


def calculate_coverage_days(
    fills: list[FillEvent],
    period: MeasurementPeriod,
    patient_id: str | None = None,
    drug_id: str | None = None,
    hospitalizations: list[Hospitalization] | None = None,
) -> set[date]:
    hospitalizations = hospitalizations or []

    relevant_fills = [
        fill
        for fill in fills
        if fill.has_valid_supply
        and (patient_id is None or fill.patient_id == patient_id)
        and (drug_id is None or fill.drug_id == drug_id)
    ]

    relevant_fills.sort(key=lambda fill: fill.fill_date)

    covered_days: set[date] = set()
    coverage_end: date | None = None

    for fill in relevant_fills:
        effective_start = fill.fill_date

        if coverage_end is not None:
            effective_start = max(
                fill.fill_date,
                coverage_end + timedelta(days=1),
            )

        coverage_end = _extended_supply_end(
            effective_start,
            fill.effective_days_supply,
            hospitalizations,
            fill.patient_id,
        )

        clipped_start = max(effective_start, period.start_date)
        clipped_end = min(coverage_end, period.end_date)

        if clipped_start <= clipped_end:
            current_day = clipped_start
            while current_day <= clipped_end:
                covered_days.add(current_day)
                current_day += timedelta(days=1)

    # Inpatient medication counts as covered for the hospitalization dates.
    for stay in hospitalizations:
        if patient_id is not None and stay.patient_id != patient_id:
            continue

        overlap_start = max(period.start_date, stay.start_date)
        overlap_end = min(period.end_date, stay.end_date)

        if overlap_start <= overlap_end:
            current_day = overlap_start
            while current_day <= overlap_end:
                covered_days.add(current_day)
                current_day += timedelta(days=1)

    return covered_days