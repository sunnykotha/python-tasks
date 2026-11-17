from datetime import date, datetime, timedelta

from claims_fraud.impossible_schedule_detection import (
    detect_impossible_schedules,
)
from claims_fraud.models import (
    Claim,
    ClaimLine,
    ProcedureTimeEstimate,
)


SERVICE_DATE = date(2026, 10, 1)


def make_claim(
    claim_id,
    line_id,
    code="PROC",
    provider="provider-1",
    start=None,
    end=None,
    location=None,
    units=1,
    status="active",
):
    line = ClaimLine(
        id=line_id,
        procedure_code=code,
        service_date=SERVICE_DATE,
        billed_amount=100.0,
        start_time=start,
        end_time=end,
        location=location,
        units=units,
    )
    return Claim(
        id=claim_id,
        patient_id=f"patient-{claim_id}",
        provider_id=provider,
        lines=(line,),
        status=status,
    )


def test_flags_more_than_24_hours_of_estimated_procedures():
    claims = [
        make_claim(f"claim-{i}", f"line-{i}")
        for i in range(13)
    ]
    estimates = [ProcedureTimeEstimate("PROC", 120)]

    flags = detect_impossible_schedules(claims, estimates)

    daily_flags = [
        flag for flag in flags
        if flag.reason_code == "IMPOSSIBLE_DAILY_SCHEDULE"
    ]
    assert len(daily_flags) == 1
    assert daily_flags[0].severity == "high"
    assert daily_flags[0].evidence["total_procedure_hours"] == 26
    assert len(daily_flags[0].claim_line_ids) == 13


def test_exactly_24_hours_does_not_trigger_daily_limit():
    claims = [
        make_claim("claim-1", "line-1", units=24),
    ]
    estimates = [ProcedureTimeEstimate("PROC", 60)]

    flags = detect_impossible_schedules(claims, estimates)
    assert not any(
        flag.reason_code == "IMPOSSIBLE_DAILY_SCHEDULE"
        for flag in flags
    )


def test_missing_estimate_skips_daily_total():
    claims = [
        make_claim("claim-1", "line-1", code="UNKNOWN", units=30),
    ]

    flags = detect_impossible_schedules(claims, [])
    assert not any(
        flag.reason_code == "IMPOSSIBLE_DAILY_SCHEDULE"
        for flag in flags
    )


def test_detects_overlapping_services_at_different_locations():
    start_a = datetime(2026, 10, 1, 10, 0)
    end_a = datetime(2026, 10, 1, 11, 0)
    start_b = datetime(2026, 10, 1, 10, 30)
    end_b = datetime(2026, 10, 1, 11, 30)

    claims = [
        make_claim(
            "claim-1", "line-1",
            start=start_a, end=end_a, location="Clinic A",
        ),
        make_claim(
            "claim-2", "line-2",
            start=start_b, end=end_b, location="Clinic B",
        ),
    ]

    flags = detect_impossible_schedules(claims, [])
    overlap_flags = [
        flag for flag in flags
        if flag.reason_code == "OVERLAPPING_SERVICE_LOCATIONS"
    ]

    assert len(overlap_flags) == 1
    assert set(overlap_flags[0].claim_line_ids) == {"line-1", "line-2"}
    overlap = overlap_flags[0].evidence["overlaps"][0]
    assert overlap["first_location"] == "Clinic A"
    assert overlap["second_location"] == "Clinic B"


def test_does_not_flag_non_overlapping_locations():
    claims = [
        make_claim(
            "claim-1", "line-1",
            start=datetime(2026, 10, 1, 9, 0),
            end=datetime(2026, 10, 1, 10, 0),
            location="Clinic A",
        ),
        make_claim(
            "claim-2", "line-2",
            start=datetime(2026, 10, 1, 10, 0),
            end=datetime(2026, 10, 1, 11, 0),
            location="Clinic B",
        ),
    ]

    flags = detect_impossible_schedules(claims, [])
    assert not any(
        flag.reason_code == "OVERLAPPING_SERVICE_LOCATIONS"
        for flag in flags
    )


def test_same_location_overlap_is_not_flagged_by_location_rule():
    claims = [
        make_claim(
            "claim-1", "line-1",
            start=datetime(2026, 10, 1, 9, 0),
            end=datetime(2026, 10, 1, 11, 0),
            location="Clinic A",
        ),
        make_claim(
            "claim-2", "line-2",
            start=datetime(2026, 10, 1, 10, 0),
            end=datetime(2026, 10, 1, 12, 0),
            location="Clinic A",
        ),
    ]

    flags = detect_impossible_schedules(claims, [])
    assert not any(
        flag.reason_code == "OVERLAPPING_SERVICE_LOCATIONS"
        for flag in flags
    )


def test_ignores_reversed_claims():
    claims = [
        make_claim("claim-1", "line-1", status="active"),
        make_claim("claim-2", "line-2", status="reversed"),
    ]
    estimates = [ProcedureTimeEstimate("PROC", 120)]

    flags = detect_impossible_schedules(claims, estimates)
    assert not any(
        flag.reason_code == "IMPOSSIBLE_DAILY_SCHEDULE"
        for flag in flags
    )


def test_ignores_overlapping_lines_from_reversed_claim():
    claims = [
        make_claim(
            "claim-1", "line-1",
            start=datetime(2026, 10, 1, 10, 0),
            end=datetime(2026, 10, 1, 11, 0),
            location="Clinic A",
        ),
        make_claim(
            "claim-2", "line-2",
            start=datetime(2026, 10, 1, 10, 15),
            end=datetime(2026, 10, 1, 11, 15),
            location="Clinic B",
            status="reversed",
        ),
    ]

    flags = detect_impossible_schedules(claims, [])
    assert not any(
        flag.reason_code == "OVERLAPPING_SERVICE_LOCATIONS"
        for flag in flags
    )


def test_daily_totals_are_separate_for_each_provider():
    claims = [
        make_claim("claim-1", "line-1", provider="provider-1", units=13),
        make_claim("claim-2", "line-2", provider="provider-2", units=13),
    ]
    estimates = [ProcedureTimeEstimate("PROC", 60)]

    flags = detect_impossible_schedules(claims, estimates)
    assert not any(
        flag.reason_code == "IMPOSSIBLE_DAILY_SCHEDULE"
        for flag in flags
    )
def test_worked_example_flags_42_hours_and_overlapping_clinics():
    claims = [
        make_claim(
            "claim-1",
            "line-1",
            start=datetime(2026, 10, 1, 9, 0),
            end=datetime(2026, 10, 1, 10, 0),
            location="Clinic A",
            units=21,
        ),
        make_claim(
            "claim-2",
            "line-2",
            start=datetime(2026, 10, 1, 9, 30),
            end=datetime(2026, 10, 1, 10, 30),
            location="Clinic B (30 miles from Clinic A)",
            units=21,
        ),
    ]

    flags = detect_impossible_schedules(
        claims,
        [ProcedureTimeEstimate("PROC", 60)],
    )

    daily_flags = [
        flag for flag in flags
        if flag.reason_code == "IMPOSSIBLE_DAILY_SCHEDULE"
    ]
    overlap_flags = [
        flag for flag in flags
        if flag.reason_code == "OVERLAPPING_SERVICE_LOCATIONS"
    ]

    assert len(daily_flags) == 1
    assert set(daily_flags[0].claim_line_ids) == {"line-1", "line-2"}

    assert len(overlap_flags) == 1
    assert set(overlap_flags[0].claim_line_ids) == {"line-1", "line-2"}
    overlap = overlap_flags[0].evidence["overlaps"][0]
    assert overlap["first_location"] == "Clinic A"
    assert overlap["second_location"] == "Clinic B (30 miles from Clinic A)"
