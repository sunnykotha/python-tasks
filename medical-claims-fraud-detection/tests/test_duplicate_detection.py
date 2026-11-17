from datetime import date

from claims_fraud.duplicate_detection import detect_duplicate_billing
from claims_fraud.models import Claim, ClaimLine


def make_line(line_id, code="99213", day=date(2026, 10, 1)):
    return ClaimLine(
        id=line_id,
        procedure_code=code,
        service_date=day,
        billed_amount=125.0,
    )


def make_claim(
    claim_id,
    patient="patient-1",
    provider="provider-1",
    lines=None,
    status="active",
):
    return Claim(
        id=claim_id,
        patient_id=patient,
        provider_id=provider,
        lines=tuple(lines or [make_line(f"{claim_id}-line")]),
        status=status,
    )


def test_detects_duplicate_billing_across_claims():
    claims = [
        make_claim("claim-1", lines=[make_line("line-1")]),
        make_claim("claim-2", lines=[make_line("line-2")]),
    ]

    flags = detect_duplicate_billing(claims)

    assert len(flags) == 1
    assert flags[0].reason_code == "DUPLICATE_BILLING"
    assert flags[0].severity == "high"
    assert set(flags[0].claim_line_ids) == {"line-1", "line-2"}
    assert flags[0].evidence["occurrences"] == 2


def test_does_not_flag_different_patients():
    claims = [
        make_claim("claim-1", patient="patient-1"),
        make_claim("claim-2", patient="patient-2"),
    ]
    assert detect_duplicate_billing(claims) == []


def test_does_not_flag_different_providers():
    claims = [
        make_claim("claim-1", provider="provider-1"),
        make_claim("claim-2", provider="provider-2"),
    ]
    assert detect_duplicate_billing(claims) == []


def test_does_not_flag_different_procedure_codes():
    claims = [
        make_claim("claim-1", lines=[make_line("line-1", code="99213")]),
        make_claim("claim-2", lines=[make_line("line-2", code="99214")]),
    ]
    assert detect_duplicate_billing(claims) == []


def test_does_not_flag_different_service_dates():
    claims = [
        make_claim(
            "claim-1",
            lines=[make_line("line-1", day=date(2026, 10, 1))],
        ),
        make_claim(
            "claim-2",
            lines=[make_line("line-2", day=date(2026, 10, 2))],
        ),
    ]
    assert detect_duplicate_billing(claims) == []


def test_ignores_corrected_claims():
    claims = [
        make_claim("claim-1"),
        make_claim("claim-2", status="corrected"),
    ]
    assert detect_duplicate_billing(claims) == []


def test_ignores_reversed_claims():
    claims = [
        make_claim("claim-1"),
        make_claim("claim-2", status="reversed"),
    ]
    assert detect_duplicate_billing(claims) == []


def test_detects_duplicate_lines_within_one_claim():
    claim = make_claim(
        "claim-1",
        lines=[make_line("line-1"), make_line("line-2")],
    )

    flags = detect_duplicate_billing([claim])

    assert len(flags) == 1
    assert set(flags[0].claim_line_ids) == {"line-1", "line-2"}


def test_three_matching_lines_are_reported_together():
    claims = [
        make_claim("claim-1", lines=[make_line("line-1")]),
        make_claim("claim-2", lines=[make_line("line-2")]),
        make_claim("claim-3", lines=[make_line("line-3")]),
    ]

    flags = detect_duplicate_billing(claims)

    assert len(flags) == 1
    assert flags[0].evidence["occurrences"] == 3
    assert len(flags[0].claim_line_ids) == 3