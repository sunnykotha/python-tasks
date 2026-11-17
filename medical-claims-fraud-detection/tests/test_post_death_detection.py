from datetime import date

from claims_fraud.models import Claim, ClaimLine, Patient
from claims_fraud.post_death_detection import detect_post_death_services


def make_claim(claim_id, patient_id, service_date, status="active"):
    line = ClaimLine(
        id=f"{claim_id}-line",
        procedure_code="PROC-1",
        service_date=service_date,
        billed_amount=100.0,
    )
    return Claim(
        id=claim_id,
        patient_id=patient_id,
        provider_id="provider-1",
        lines=(line,),
        status=status,
    )


def test_flags_service_after_date_of_death():
    patient = Patient("patient-1", date(2026, 9, 30))
    claim = make_claim("claim-1", "patient-1", date(2026, 10, 1))

    flags = detect_post_death_services([claim], [patient])

    assert len(flags) == 1
    assert flags[0].reason_code == "SERVICE_AFTER_DATE_OF_DEATH"
    assert flags[0].severity == "critical"
    assert flags[0].evidence["date_of_death"] == "2026-09-30"
    assert flags[0].evidence["service_date"] == "2026-10-01"
    assert flags[0].claim_line_ids == ("claim-1-line",)


def test_does_not_flag_service_on_date_of_death():
    patient = Patient("patient-1", date(2026, 9, 30))
    claim = make_claim("claim-1", "patient-1", date(2026, 9, 30))

    assert detect_post_death_services([claim], [patient]) == []


def test_does_not_flag_service_before_date_of_death():
    patient = Patient("patient-1", date(2026, 9, 30))
    claim = make_claim("claim-1", "patient-1", date(2026, 9, 29))

    assert detect_post_death_services([claim], [patient]) == []


def test_ignores_patient_without_date_of_death():
    patient = Patient("patient-1")
    claim = make_claim("claim-1", "patient-1", date(2026, 10, 1))

    assert detect_post_death_services([claim], [patient]) == []


def test_ignores_unknown_patient():
    claim = make_claim("claim-1", "unknown-patient", date(2026, 10, 1))

    assert detect_post_death_services([claim], []) == []


def test_ignores_reversed_claim():
    patient = Patient("patient-1", date(2026, 9, 30))
    claim = make_claim(
        "claim-1", "patient-1", date(2026, 10, 1), status="reversed"
    )

    assert detect_post_death_services([claim], [patient]) == []


def test_ignores_corrected_claim():
    patient = Patient("patient-1", date(2026, 9, 30))
    claim = make_claim(
        "claim-1", "patient-1", date(2026, 10, 1), status="corrected"
    )

    assert detect_post_death_services([claim], [patient]) == []


def test_only_flags_lines_after_death():
    patient = Patient("patient-1", date(2026, 9, 30))
    claim = Claim(
        id="claim-1",
        patient_id="patient-1",
        provider_id="provider-1",
        lines=(
            ClaimLine(
                "line-before", "PROC-1", date(2026, 9, 29), 100.0
            ),
            ClaimLine(
                "line-after", "PROC-2", date(2026, 10, 1), 100.0
            ),
        ),
    )

    flags = detect_post_death_services([claim], [patient])

    assert len(flags) == 1
    assert flags[0].claim_line_ids == ("line-after",)