"""Rule-based duplicate billing detection."""

from collections import defaultdict

from claims_fraud.models import AnomalyFlag, Claim


def detect_duplicate_billing(claims: list[Claim]) -> list[AnomalyFlag]:
    """Flag repeated patient/provider/procedure/date combinations.

    Only active claims are considered. Corrected and reversed claims are
    excluded so they do not inflate duplicate counts.
    """
    groups = defaultdict(list)

    for claim in claims:
        if claim.status != "active":
            continue

        for line in claim.lines:
            key = (
                claim.patient_id,
                claim.provider_id,
                line.procedure_code,
                line.service_date,
            )
            groups[key].append((claim, line))

    flags = []

    for key, entries in groups.items():
        if len(entries) < 2:
            continue

        patient_id, provider_id, procedure_code, service_date = key
        line_ids = tuple(line.id for _, line in entries)
        claim_ids = tuple(claim.id for claim, _ in entries)

        flags.append(
            AnomalyFlag(
                reason_code="DUPLICATE_BILLING",
                description=(
                    "The same patient, provider, procedure code, and "
                    "service date appear on multiple active claim lines."
                ),
                severity="high",
                score=0.9,
                claim_line_ids=line_ids,
                evidence={
                    "patient_id": patient_id,
                    "provider_id": provider_id,
                    "procedure_code": procedure_code,
                    "service_date": service_date.isoformat(),
                    "claim_ids": claim_ids,
                    "occurrences": len(entries),
                },
            )
        )

    return sorted(
        flags,
        key=lambda flag: (
            flag.evidence["service_date"],
            flag.evidence["provider_id"],
            flag.evidence["procedure_code"],
        ),
    )