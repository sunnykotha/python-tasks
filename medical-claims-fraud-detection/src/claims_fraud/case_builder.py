"""Build and rank investigator case files from anomaly flags."""

from collections import defaultdict

from claims_fraud.models import AnomalyFlag, CaseFile


_SEVERITY_RANK = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


def build_case_files(flags: list[AnomalyFlag]) -> list[CaseFile]:
    """Group anomaly flags by provider and rank the resulting cases.

    Cases are ordered by highest severity first, then highest flag score,
    then provider ID for deterministic results. Every flag must identify
    its provider in its evidence.
    """
    flags_by_provider = defaultdict(list)

    for flag in flags:
        provider_id = flag.evidence.get("provider_id")
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise ValueError(
                "Every anomaly flag must include provider_id in its evidence."
            )
        flags_by_provider[provider_id].append(flag)

    ranked = []

    for provider_id, provider_flags in flags_by_provider.items():
        line_ids = tuple(dict.fromkeys(
            line_id
            for flag in provider_flags
            for line_id in flag.claim_line_ids
        ))

        highest_severity = max(
            provider_flags,
            key=lambda flag: _SEVERITY_RANK[flag.severity],
        ).severity
        highest_score = max(flag.score for flag in provider_flags)

        case = CaseFile(
            id=f"CASE-{provider_id}",
            provider_id=provider_id,
            flags=tuple(provider_flags),
            claim_line_ids=line_ids,
            evidence={
                "provider_id": provider_id,
                "flag_count": len(provider_flags),
                "reason_codes": tuple(
                    dict.fromkeys(flag.reason_code for flag in provider_flags)
                ),
                "highest_severity": highest_severity,
                "highest_flag_score": highest_score,
            },
        )

        ranked.append(
            (
                _SEVERITY_RANK[highest_severity],
                highest_score,
                provider_id,
                case,
            )
        )

    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [item[3] for item in ranked]