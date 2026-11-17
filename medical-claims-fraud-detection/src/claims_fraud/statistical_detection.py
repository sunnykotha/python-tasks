"""Specialty-peer statistical anomaly detection for provider billing."""

from collections import Counter, defaultdict
from math import exp

import numpy as np
from sklearn.ensemble import IsolationForest

from claims_fraud.models import AnomalyFlag, Claim, Provider


MIN_SPECIALTY_PROVIDERS = 5


def detect_statistical_anomalies(
    claims: list[Claim],
    providers: list[Provider],
    random_state: int = 42,
) -> list[AnomalyFlag]:
    """Flag unusual provider billing patterns within the same specialty.

    Features describe billing patterns rather than raw claim volume.
    Corrected and reversed claims are excluded. Specialty groups with
    fewer than five active providers, or no feature variation, are skipped.
    """
    provider_by_id = {provider.id: provider for provider in providers}
    lines_by_provider = defaultdict(list)
    patients_by_provider = defaultdict(set)

    for claim in claims:
        if claim.status != "active":
            continue
        if claim.provider_id not in provider_by_id:
            continue

        for line in claim.lines:
            lines_by_provider[claim.provider_id].append(line)
            patients_by_provider[claim.provider_id].add(claim.patient_id)

    providers_by_specialty = defaultdict(list)

    for provider_id, lines in lines_by_provider.items():
        provider = provider_by_id[provider_id]
        line_count = len(lines)
        code_counts = Counter(line.procedure_code for line in lines)
        code_proportions = [
            count / line_count for count in code_counts.values()
        ]

        # Concentration is stable when the same billing pattern is repeated;
        # unlike unique-code-count / line-count, it does not fall with volume.
        code_concentration = sum(
            proportion * proportion for proportion in code_proportions
        )

        features = {
            "average_billed_amount": float(
                np.mean([line.billed_amount for line in lines])
            ),
            "average_units": float(
                np.mean([line.units for line in lines])
            ),
            "procedure_code_concentration": float(code_concentration),
            "patient_diversity": (
                len(patients_by_provider[provider_id]) / line_count
            ),
        }

        providers_by_specialty[provider.specialty].append(
            (provider_id, features, line_count)
        )

    flags = []

    for specialty, entries in providers_by_specialty.items():
        if len(entries) < MIN_SPECIALTY_PROVIDERS:
            continue

        feature_names = (
            "average_billed_amount",
            "average_units",
            "procedure_code_concentration",
            "patient_diversity",
        )
        matrix = np.array(
            [
                [features[name] for name in feature_names]
                for _, features, _ in entries
            ],
            dtype=float,
        )

        # No meaningful variation means no statistical basis for an anomaly.
        if not np.isfinite(matrix).all():
            continue
        if not np.any(np.ptp(matrix, axis=0) > 1e-12):
            continue

        model = IsolationForest(
            n_estimators=200,
            contamination="auto",
            random_state=random_state,
        )
        model.fit(matrix)

        decision_scores = model.decision_function(matrix)
        predictions = model.predict(matrix)

        for index, (provider_id, features, line_count) in enumerate(entries):
            if predictions[index] != -1:
                continue

            decision_score = float(decision_scores[index])
            anomaly_score = 1.0 / (1.0 + exp(decision_score * 5.0))

            flags.append(
                AnomalyFlag(
                    reason_code="STATISTICAL_BILLING_ANOMALY",
                    description=(
                        "Provider billing features are statistically unusual "
                        "compared with providers in the same specialty."
                    ),
                    severity="high" if anomaly_score >= 0.75 else "medium",
                    score=max(0.0, min(1.0, anomaly_score)),
                    evidence={
                        "provider_id": provider_id,
                        "specialty": specialty,
                        "active_claim_line_count": line_count,
                        "features": features,
                        "isolation_forest_decision_score": decision_score,
                        "model": "IsolationForest",
                        "random_state": random_state,
                        "peer_provider_count": len(entries) - 1,
                    },
                )
            )

    return sorted(flags, key=lambda flag: flag.score, reverse=True)