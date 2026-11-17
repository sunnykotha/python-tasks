import pytest

from claims_fraud.case_builder import build_case_files
from claims_fraud.models import AnomalyFlag


def make_flag(
    provider_id,
    reason_code,
    severity="high",
    score=0.8,
    line_ids=(),
):
    return AnomalyFlag(
        reason_code=reason_code,
        description=f"Evidence for {reason_code}",
        severity=severity,
        score=score,
        claim_line_ids=tuple(line_ids),
        evidence={"provider_id": provider_id, "source": reason_code},
    )


def test_groups_multiple_flags_for_same_provider():
    flags = [
        make_flag("provider-1", "DUPLICATE_BILLING", line_ids=["line-1"]),
        make_flag(
            "provider-1",
            "UPCODING",
            severity="medium",
            score=0.7,
            line_ids=["line-2"],
        ),
    ]

    cases = build_case_files(flags)

    assert len(cases) == 1
    assert cases[0].provider_id == "provider-1"
    assert len(cases[0].flags) == 2
    assert cases[0].evidence["flag_count"] == 2
    assert cases[0].evidence["reason_codes"] == (
        "DUPLICATE_BILLING",
        "UPCODING",
    )


def test_case_line_ids_are_combined_without_duplicates():
    flags = [
        make_flag("provider-1", "RULE_A", line_ids=["line-1", "line-2"]),
        make_flag("provider-1", "RULE_B", line_ids=["line-2", "line-3"]),
    ]

    case = build_case_files(flags)[0]

    assert case.claim_line_ids == ("line-1", "line-2", "line-3")


def test_critical_case_ranks_before_high_case():
    flags = [
        make_flag("provider-a", "HIGH_RULE", "high", 0.99),
        make_flag("provider-b", "CRITICAL_RULE", "critical", 0.5),
    ]

    cases = build_case_files(flags)

    assert [case.provider_id for case in cases] == [
        "provider-b",
        "provider-a",
    ]


def test_higher_score_ranks_first_within_same_severity():
    flags = [
        make_flag("provider-a", "RULE_A", "high", 0.75),
        make_flag("provider-b", "RULE_B", "high", 0.95),
    ]

    cases = build_case_files(flags)

    assert [case.provider_id for case in cases] == [
        "provider-b",
        "provider-a",
    ]


def test_tie_breaking_is_deterministic_by_provider_id():
    flags = [
        make_flag("provider-z", "RULE_Z", "high", 0.8),
        make_flag("provider-a", "RULE_A", "high", 0.8),
    ]

    cases = build_case_files(flags)

    assert [case.provider_id for case in cases] == [
        "provider-a",
        "provider-z",
    ]


def test_case_preserves_flag_evidence_and_rank_metadata():
    flag = AnomalyFlag(
        reason_code="SERVICE_AFTER_DATE_OF_DEATH",
        description="Service after recorded death date.",
        severity="critical",
        score=1.0,
        claim_line_ids=("line-1",),
        evidence={
            "provider_id": "provider-1",
            "patient_id": "patient-1",
            "service_date": "2026-10-01",
        },
    )

    case = build_case_files([flag])[0]

    assert case.flags[0].evidence["patient_id"] == "patient-1"
    assert case.evidence["highest_severity"] == "critical"
    assert case.evidence["highest_flag_score"] == 1.0
    assert case.id == "CASE-provider-1"


def test_empty_flags_return_no_cases():
    assert build_case_files([]) == []


def test_flag_without_provider_evidence_is_rejected():
    flag = AnomalyFlag(
        reason_code="UNKNOWN_PROVIDER",
        description="Provider evidence is missing.",
        severity="low",
        score=0.1,
    )

    with pytest.raises(ValueError, match="provider_id"):
        build_case_files([flag])


def test_different_providers_receive_separate_cases():
    flags = [
        make_flag("provider-1", "RULE_A"),
        make_flag("provider-2", "RULE_B"),
    ]

    cases = build_case_files(flags)

    assert len(cases) == 2
    assert {case.provider_id for case in cases} == {
        "provider-1",
        "provider-2",
    }