"""Specialty-peer-based upcoding detection."""

from collections import defaultdict
from datetime import date
from statistics import mean, pstdev

from claims_fraud.models import AnomalyFlag, Claim, Provider


def detect_upcoding(
    claims: list[Claim],
    providers: list[Provider],
    visit_code_levels: dict[str, int],
    threshold: float = 3.0,
) -> list[AnomalyFlag]:
    """Flag providers whose highest-level visit-code rate is a peer outlier.

    visit_code_levels maps visit procedure codes to ordered numeric levels.
    Only active claims and codes present in that mapping are considered.
    Each provider is compared against other providers of the same specialty.
    Providers with insufficient peer variation are not flagged by this rule.
    """
    if threshold <= 0:
        raise ValueError("Threshold must be positive.")

    if not visit_code_levels:
        return []

    if any(level < 1 for level in visit_code_levels.values()):
        raise ValueError("Visit code levels must be positive integers.")

    provider_by_id = {provider.id: provider for provider in providers}
    highest_level = max(visit_code_levels.values())

    total_visits = defaultdict(int)
    highest_level_visits = defaultdict(int)

    for claim in claims:
        if claim.status != "active":
            continue

        if claim.provider_id not in provider_by_id:
            continue

        for line in claim.lines:
            level = visit_code_levels.get(line.procedure_code)
            if level is None:
                continue

            total_visits[claim.provider_id] += 1
            if level == highest_level:
                highest_level_visits[claim.provider_id] += 1

    rates_by_specialty = defaultdict(dict)

    for provider_id, total in total_visits.items():
        provider = provider_by_id[provider_id]
        rates_by_specialty[provider.specialty][provider_id] = (
            highest_level_visits[provider_id] / total
        )

    flags = []

    for specialty, provider_rates in rates_by_specialty.items():
        for provider_id, rate in provider_rates.items():
            peer_rates = [
                peer_rate
                for peer_id, peer_rate in provider_rates.items()
                if peer_id != provider_id
            ]

            # Require at least three peers for a meaningful comparison.
            if len(peer_rates) < 3:
                continue

            peer_mean = mean(peer_rates)
            peer_std = pstdev(peer_rates)

            # A zero-variance peer group cannot establish a meaningful z-score.
            if peer_std == 0:
                continue

            z_score = (rate - peer_mean) / peer_std

            if z_score <= threshold:
                continue

            flags.append(
                AnomalyFlag(
                    reason_code="UPCODING",
                    description=(
                        "Highest-level visit-code billing rate is unusually "
                        "high compared with providers in the same specialty."
                    ),
                    severity="high",
                    score=min(z_score / (z_score + threshold), 1.0),
                    evidence={
                        "provider_id": provider_id,
                        "specialty": specialty,
                        "highest_level": highest_level,
                        "highest_level_visit_count": highest_level_visits[
                            provider_id
                        ],
                        "total_visit_count": total_visits[provider_id],
                        "provider_rate": rate,
                        "peer_mean_rate": peer_mean,
                        "peer_standard_deviation": peer_std,
                        "z_score": z_score,
                        "threshold": threshold,
                        "peer_count": len(peer_rates),
                    },
                )
            )

    return sorted(
        flags,
        key=lambda flag: flag.evidence["z_score"],
        reverse=True,
    )