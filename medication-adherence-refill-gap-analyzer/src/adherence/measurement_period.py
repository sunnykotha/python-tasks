from datetime import timedelta

from adherence.models import (
    FillEvent,
    MeasurementPeriod,
    Patient,
)


def calculate_measurement_period(
    patient: Patient,
    fills: list[FillEvent],
    period_days: int = 365,
) -> MeasurementPeriod:
    if isinstance(period_days, bool) or not isinstance(period_days, int) or period_days <= 0:
        raise ValueError("Period length must be a positive integer.")

    patient_fills = [
        fill
        for fill in fills
        if fill.patient_id == patient.patient_id and fill.has_valid_supply
    ]

    if not patient_fills:
        raise ValueError("At least one valid medication fill is required.")

    start_date = min(fill.fill_date for fill in patient_fills)
    end_date = start_date + timedelta(days=period_days - 1)

    truncation_dates = [
        event_date
        for event_date in (
            patient.death_date,
            patient.disenrollment_date,
        )
        if event_date is not None and event_date >= start_date
    ]

    if truncation_dates:
        end_date = min(end_date, min(truncation_dates))

    return MeasurementPeriod(
        start_date=start_date,
        end_date=end_date,
    )