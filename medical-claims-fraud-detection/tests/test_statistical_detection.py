from datetime import date

from claims_fraud.models import Claim, ClaimLine, Provider
from claims_fraud.statistical_detection import detect_statistical_anomalies


def make_providers(count=8, specialty="general"):
    return [
        Provider(f"provider-{index}", specialty)
        for index in range(count)
    ]


def make_claim(claim_id, provider_id, patient_id, amount, status="active"):
    line = ClaimLine(
        id=f"{claim_id}-line",
        procedure_code="VISIT-1",
        service_date=date(2026, 10, 1),
        billed_amount=amount,
    )
    return Claim(
        id=claim_id,
        patient_id=patient_id,
        provider_id=provider_id,
        lines=(line,),
        status=status,
    )


def normal_claims(providers, amount=100.0):
    claims = []
    for provider in providers:
        for index in range(5):
            claims.append(
                make_claim(
                    f"{provider.id}-claim-{index}",
                    provider.id,
                    f"{provider.id}-patient-{index}",
                    amount,
                )
            )
    return claims


def test_flags_extreme_billing_amount_against_specialty_peers():
    providers = make_providers(8)
    claims = normal_claims(providers[:7])
    claims.extend(normal_claims([providers[7]], amount=10000.0))

    flags = detect_statistical_anomalies(claims, providers)

    assert any(
        flag.evidence["provider_id"] == "provider-7"
        and flag.reason_code == "STATISTICAL_BILLING_ANOMALY"
        for flag in flags
    )


def test_statistical_flag_includes_reason_score_and_feature_evidence():
    providers = make_providers(8)
    claims = normal_claims(providers[:7])
    claims.extend(normal_claims([providers[7]], amount=10000.0))

    flags = detect_statistical_anomalies(claims, providers)
    flag = next(
        flag for flag in flags
        if flag.evidence["provider_id"] == "provider-7"
    )

    assert flag.reason_code == "STATISTICAL_BILLING_ANOMALY"
    assert 0.0 <= flag.score <= 1.0
    assert flag.evidence["model"] == "IsolationForest"
    assert "average_billed_amount" in flag.evidence["features"]
    assert flag.evidence["peer_provider_count"] == 7


def test_does_not_score_specialty_with_too_few_providers():
    providers = make_providers(4)
    claims = normal_claims(providers)

    assert detect_statistical_anomalies(claims, providers) == []


def test_corrected_and_reversed_claims_do_not_affect_features():
    providers = make_providers(8)
    claims = normal_claims(providers)

    claims.append(
        make_claim(
            "corrected-extreme",
            "provider-0",
            "patient-corrected",
            1000000.0,
            status="corrected",
        )
    )
    claims.append(
        make_claim(
            "reversed-extreme",
            "provider-1",
            "patient-reversed",
            1000000.0,
            status="reversed",
        )
    )

    flags = detect_statistical_anomalies(claims, providers)

    assert all(
        flag.evidence["provider_id"] not in {"provider-0", "provider-1"}
        for flag in flags
    )


def test_unknown_provider_claims_are_ignored():
    providers = make_providers(4)
    claims = normal_claims(providers)
    claims.append(
        make_claim("unknown-claim", "unknown-provider", "patient-x", 999999.0)
    )

    assert detect_statistical_anomalies(claims, providers) == []


def test_high_claim_volume_alone_is_not_a_model_feature():
    providers = make_providers(6)
    claims = normal_claims(providers[:5])

    # This provider has more claims, but the same billing pattern.
    claims.extend(normal_claims([providers[5]] * 1))

    for index in range(45):
        claims.append(
            make_claim(
                f"high-volume-{index}",
                "provider-5",
                f"extra-patient-{index}",
                100.0,
            )
        )

    flags = detect_statistical_anomalies(claims, providers)

    assert all(
        flag.evidence["provider_id"] != "provider-5"
        for flag in flags
    )


def test_specialties_are_scored_separately():
    general = make_providers(4, specialty="general")
    cardiology = make_providers(4, specialty="cardiology")
    providers = general + cardiology
    claims = normal_claims(general) + normal_claims(cardiology)

    assert detect_statistical_anomalies(claims, providers) == []


def test_results_are_deterministic_for_same_input():
    providers = make_providers(8)
    claims = normal_claims(providers[:7])
    claims.extend(normal_claims([providers[7]], amount=10000.0))

    first = detect_statistical_anomalies(claims, providers)
    second = detect_statistical_anomalies(claims, providers)

    assert [
        (flag.reason_code, flag.evidence["provider_id"], flag.score)
        for flag in first
    ] == [
        (flag.reason_code, flag.evidence["provider_id"], flag.score)
        for flag in second
    ]

def test_month_end_batch_submission_timing_does_not_change_flags():
    from dataclasses import replace
    from datetime import datetime, timedelta

    providers = make_providers(8)
    claims = normal_claims(providers[:7])
    claims.extend(normal_claims([providers[7]], amount=10000.0))

    batch_time = datetime(2026, 10, 31, 23, 59)
    batch_claims = [
        replace(claim, submitted_at=batch_time)
        for claim in claims
    ]
    staggered_claims = [
        replace(
            claim,
            submitted_at=batch_time - timedelta(days=index),
        )
        for index, claim in enumerate(claims)
    ]

    batch_flags = detect_statistical_anomalies(batch_claims, providers)
    staggered_flags = detect_statistical_anomalies(
        staggered_claims, providers
    )

    def signature(flags):
        return [
            (
                flag.reason_code,
                flag.evidence["provider_id"],
                flag.score,
            )
            for flag in flags
        ]

    assert signature(batch_flags) == signature(staggered_flags)
