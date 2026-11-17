"""Configurable unbundling detection."""

from collections import defaultdict

from claims_fraud.models import AnomalyFlag, Claim


def detect_unbundling(
    claims: list[Claim],
    comprehensive_code_components: dict[str, set[str]],
) -> list[AnomalyFlag]:
    """Flag complete configured component sets billed without their bundle.

    Mapping format:
        comprehensive code -> set of required component codes

    Matching is limited to the same patient, provider, and service date.
    Only active claims are considered.
    """
    if not comprehensive_code_components:
        return []

    for comprehensive_code, components in comprehensive_code_components.items():
        if not comprehensive_code.strip():
            raise ValueError("Comprehensive procedure code is required.")
        if not components:
            raise ValueError("Each comprehensive code needs components.")
        if any(not component.strip() for component in components):
            raise ValueError("Component codes cannot be empty.")
        if comprehensive_code in components:
            raise ValueError(
                "A comprehensive code cannot also be its own component."
            )

    groups = defaultdict(list)

    for claim in claims:
        if claim.status != "active":
            continue

        for line in claim.lines:
            key = (
                claim.patient_id,
                claim.provider_id,
                line.service_date,
            )
            groups[key].append((claim, line))

    flags = []

    for (patient_id, provider_id, service_date), entries in groups.items():
        billed_codes = {line.procedure_code for _, line in entries}

        for comprehensive_code, components in comprehensive_code_components.items():
            if not components.issubset(billed_codes):
                continue

            if comprehensive_code in billed_codes:
                continue

            matching_lines = [
                line
                for _, line in entries
                if line.procedure_code in components
            ]

            flags.append(
                AnomalyFlag(
                    reason_code="UNBUNDLING",
                    description=(
                        "All configured component codes were billed for "
                        "the same patient, provider, and service date "
                        "without the configured comprehensive code."
                    ),
                    severity="high",
                    score=0.9,
                    claim_line_ids=tuple(
                        line.id for line in matching_lines
                    ),
                    evidence={
                        "patient_id": patient_id,
                        "provider_id": provider_id,
                        "service_date": service_date.isoformat(),
                        "comprehensive_code": comprehensive_code,
                        "component_codes": sorted(components),
                        "billed_component_codes": sorted(
                            {line.procedure_code for line in matching_lines}
                        ),
                        "claim_ids": tuple(
                            claim.id
                            for claim, line in entries
                            if line.procedure_code in components
                        ),
                    },
                )
            )

    return sorted(
        flags,
        key=lambda flag: (
            flag.evidence["service_date"],
            flag.evidence["provider_id"],
            flag.evidence["comprehensive_code"],
        ),
    )