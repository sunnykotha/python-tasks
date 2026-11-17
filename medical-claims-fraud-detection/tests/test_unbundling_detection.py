from datetime import date

import pytest

from claims_fraud.models import Claim, ClaimLine
from claims_fraud.unbundling_detection import detect_unbundling


BUNDLES = {"BUNDLE-100": {"COMP-1", "COMP-2"}}


def make_claim(
    claim_id,
    code,
    patient="patient-1",
    provider="provider-1",
    day=date(2026, 10, 1),
    status="active",
):
    line = ClaimLine(
        id=f"{claim_id}-line",
        procedure_code=code,
        service_date=day,
        billed_amount=100.0,
    )
    return Claim(
        id=claim_id,
        patient_id=patient,
        provider_id=provider,
        lines=(line,),
        status=status,
    )


def test_flags_all_components_without_comprehensive_code():
    claims = [
        make_claim("claim-1", "COMP-1"),
        make_claim("claim-2", "COMP-2"),
    ]

    flags = detect_unbundling(claims, BUNDLES)

    assert len(flags) == 1
    assert flags[0].reason_code == "UNBUNDLING"
    assert set(flags[0].claim_line_ids) == {
        "claim-1-line",
        "claim-2-line",
    }
    assert flags[0].evidence["comprehensive_code"] == "BUNDLE-100"


def test_does_not_flag_when_comprehensive_code_is_billed():
    claims = [
        make_claim("claim-1", "COMP-1"),
        make_claim("claim-2", "COMP-2"),
        make_claim("claim-3", "BUNDLE-100"),
    ]
    assert detect_unbundling(claims, BUNDLES) == []


def test_does_not_flag_incomplete_component_set():
    claims = [make_claim("claim-1", "COMP-1")]
    assert detect_unbundling(claims, BUNDLES) == []


def test_components_must_match_same_patient():
    claims = [
        make_claim("claim-1", "COMP-1", patient="patient-1"),
        make_claim("claim-2", "COMP-2", patient="patient-2"),
    ]
    assert detect_unbundling(claims, BUNDLES) == []


def test_components_must_match_same_provider():
    claims = [
        make_claim("claim-1", "COMP-1", provider="provider-1"),
        make_claim("claim-2", "COMP-2", provider="provider-2"),
    ]
    assert detect_unbundling(claims, BUNDLES) == []


def test_components_must_match_same_service_date():
    claims = [
        make_claim("claim-1", "COMP-1", day=date(2026, 10, 1)),
        make_claim("claim-2", "COMP-2", day=date(2026, 10, 2)),
    ]
    assert detect_unbundling(claims, BUNDLES) == []


def test_ignores_corrected_and_reversed_claims():
    claims = [
        make_claim("claim-1", "COMP-1"),
        make_claim("claim-2", "COMP-2", status="reversed"),
    ]
    assert detect_unbundling(claims, BUNDLES) == []


def test_rejects_empty_component_mapping():
    with pytest.raises(ValueError):
        detect_unbundling([], {"BUNDLE-100": set()})


def test_empty_rules_return_no_flags():
    assert detect_unbundling([], {}) == []