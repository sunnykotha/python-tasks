from datetime import date, datetime, timedelta

import pytest

from claims_fraud.models import (
    AnomalyFlag,
    CaseFile,
    Claim,
    ClaimLine,
    Patient,
    PeerGroup,
    ProcedureTimeEstimate,
    Provider,
)


def make_line(**overrides):
    values = {
        "id": "line-1",
        "procedure_code": "99213",
        "service_date": date(2026, 10, 1),
        "billed_amount": 125.0,
    }
    values.update(overrides)
    return ClaimLine(**values)


def make_claim(**overrides):
    values = {
        "id": "claim-1",
        "patient_id": "patient-1",
        "provider_id": "provider-1",
        "lines": (make_line(),),
    }
    values.update(overrides)
    return Claim(**values)


def test_claim_line_accepts_valid_data():
    line = make_line()
    assert line.procedure_code == "99213"
    assert line.billed_amount == 125.0


@pytest.mark.parametrize(
    "overrides",
    [
        {"id": ""},
        {"procedure_code": ""},
        {"billed_amount": -1.0},
        {"units": 0},
    ],
)
def test_claim_line_rejects_invalid_data(overrides):
    with pytest.raises(ValueError):
        make_line(**overrides)


def test_claim_line_rejects_invalid_time_range():
    start = datetime(2026, 10, 1, 10, 0)
    with pytest.raises(ValueError):
        make_line(start_time=start, end_time=start)


def test_claim_accepts_active_corrected_and_reversed_statuses():
    for status in ("active", "corrected", "reversed"):
        assert make_claim(status=status).status == status


def test_claim_rejects_unknown_status():
    with pytest.raises(ValueError):
        make_claim(status="unknown")


def test_claim_requires_at_least_one_line():
    with pytest.raises(ValueError):
        make_claim(lines=())


def test_provider_requires_id_and_specialty():
    assert Provider("provider-1", "cardiology").specialty == "cardiology"
    with pytest.raises(ValueError):
        Provider("provider-1", "")


def test_patient_supports_date_of_death():
    patient = Patient("patient-1", date(2026, 9, 30))
    assert patient.date_of_death == date(2026, 9, 30)
    assert Patient("patient-2").date_of_death is None


def test_procedure_time_estimate_requires_positive_duration():
    assert ProcedureTimeEstimate("PROC-1", 45).estimated_minutes == 45
    with pytest.raises(ValueError):
        ProcedureTimeEstimate("PROC-1", 0)


def test_peer_group_requires_providers():
    group = PeerGroup("cardiology", ("provider-1", "provider-2"))
    assert len(group.provider_ids) == 2
    with pytest.raises(ValueError):
        PeerGroup("cardiology", ())


def test_anomaly_flag_requires_reason_code_and_valid_score():
    flag = AnomalyFlag(
        reason_code="DUPLICATE_BILLING",
        description="Same service appears more than once.",
        severity="high",
        score=0.95,
        claim_line_ids=("line-1", "line-2"),
        evidence={"procedure_code": "99213"},
    )
    assert flag.reason_code == "DUPLICATE_BILLING"
    assert flag.evidence["procedure_code"] == "99213"
    with pytest.raises(ValueError):
        AnomalyFlag("X", "Invalid score", "high", 1.5)


def test_case_file_preserves_flags_and_evidence():
    flag = AnomalyFlag(
        "IMPOSSIBLE_SCHEDULE",
        "Procedure schedule exceeds daily limit.",
        "high",
        0.99,
        ("line-1",),
    )
    case = CaseFile(
        "case-1",
        "provider-1",
        (flag,),
        ("line-1",),
        {"total_procedure_hours": 42, "locations": ["Clinic A", "Clinic B"]},
    )
    assert case.flags[0].reason_code == "IMPOSSIBLE_SCHEDULE"
    assert case.evidence["total_procedure_hours"] == 42
    assert case.claim_line_ids == ("line-1",)


def test_case_file_requires_at_least_one_flag():
    with pytest.raises(ValueError):
        CaseFile("case-1", "provider-1", ())