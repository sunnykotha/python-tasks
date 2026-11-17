from datetime import date, timedelta

import pytest

from claims_fraud.models import Claim, ClaimLine, Provider
from claims_fraud.upcoding_detection import detect_upcoding


CODE_LEVELS = {
    "99213": 1,
    "99214": 2,
    "99215": 3,
}


def make_provider_claims(provider_id, high_level_count, total=10):
    claims = []

    for index in range(total):
        code = "99215" if index < high_level_count else "99213"
        line = ClaimLine(
            id=f"{provider_id}-line-{index}",
            procedure_code=code,
            service_date=date(2026, 1, 1) + timedelta(days=index),
            billed_amount=125.0,
        )
        claims.append(
            Claim(
                id=f"{provider_id}-claim-{index}",
                patient_id=f"patient-{provider_id}-{index}",
                provider_id=provider_id,
                lines=(line,),
            )
        )

    return claims


def test_flags_high_level_visit_rate_against_specialty_peers():
    providers = [
        Provider(f"peer-{i}", "family medicine") for i in range(9)
    ] + [Provider("outlier", "family medicine")]

    claims = []
    for i in range(9):
        claims.extend(make_provider_claims(f"peer-{i}", 1 if i % 2 == 0 else 2))
    claims.extend(make_provider_claims("outlier", 9))

    flags = detect_upcoding(claims, providers, CODE_LEVELS)

    assert len(flags) == 1
    flag = flags[0]
    assert flag.reason_code == "UPCODING"
    assert flag.evidence["provider_id"] == "outlier"
    assert flag.evidence["specialty"] == "family medicine"
    assert flag.evidence["z_score"] > 3.0
    assert flag.evidence["peer_count"] == 9


def test_does_not_compare_different_specialties():
    providers = [
        Provider("high", "cardiology"),
        Provider("peer-1", "family medicine"),
        Provider("peer-2", "family medicine"),
        Provider("peer-3", "family medicine"),
        Provider("peer-4", "family medicine"),
    ]

    claims = []
    claims.extend(make_provider_claims("high", 10))
    for provider in providers[1:]:
        claims.extend(make_provider_claims(provider.id, 1))

    assert detect_upcoding(claims, providers, CODE_LEVELS) == []


def test_ignores_corrected_and_reversed_claims():
    providers = [
        Provider(f"peer-{i}", "family medicine") for i in range(4)
    ] + [Provider("outlier", "family medicine")]

    claims = []
    for i in range(4):
        claims.extend(make_provider_claims(f"peer-{i}", 1))

    claims.extend(
        make_provider_claims("outlier", 10)
    )
    claims = [
        Claim(
            id=claim.id,
            patient_id=claim.patient_id,
            provider_id=claim.provider_id,
            lines=claim.lines,
            status="reversed" if claim.provider_id == "outlier" else "active",
        )
        for claim in claims
    ]

    assert detect_upcoding(claims, providers, CODE_LEVELS) == []


def test_ignores_non_visit_codes():
    providers = [
        Provider(f"peer-{i}", "family medicine") for i in range(4)
    ]
    claims = []
    for i in range(4):
        line = ClaimLine(
            id=f"line-{i}",
            procedure_code="XRAY",
            service_date=date(2026, 1, 1),
            billed_amount=100.0,
        )
        claims.append(
            Claim(
                id=f"claim-{i}",
                patient_id=f"patient-{i}",
                provider_id=f"peer-{i}",
                lines=(line,),
            )
        )

    assert detect_upcoding(claims, providers, CODE_LEVELS) == []


def test_does_not_flag_when_peer_group_has_zero_variance():
    providers = [
        Provider(f"peer-{i}", "family medicine") for i in range(4)
    ]
    claims = []
    for i in range(4):
        claims.extend(make_provider_claims(f"peer-{i}", 1))

    assert detect_upcoding(claims, providers, CODE_LEVELS) == []


def test_requires_positive_threshold():
    with pytest.raises(ValueError):
        detect_upcoding([], [], CODE_LEVELS, threshold=0)


def test_requires_positive_code_levels():
    with pytest.raises(ValueError):
        detect_upcoding([], [], {"99213": 0})


def test_requires_at_least_three_peers():
    providers = [
        Provider("peer-1", "family medicine"),
        Provider("peer-2", "family medicine"),
        Provider("outlier", "family medicine"),
    ]
    claims = []
    claims.extend(make_provider_claims("peer-1", 1))
    claims.extend(make_provider_claims("peer-2", 2))
    claims.extend(make_provider_claims("outlier", 10))

    assert detect_upcoding(claims, providers, CODE_LEVELS) == []