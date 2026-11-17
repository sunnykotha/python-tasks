"""Detection of impossible provider schedules."""

from collections import defaultdict
from datetime import date, datetime

from claims_fraud.models import (
    AnomalyFlag,
    Claim,
    ProcedureTimeEstimate,
)


def detect_impossible_schedules(
    claims: list[Claim],
    procedure_time_estimates: list[ProcedureTimeEstimate],
) -> list[AnomalyFlag]:
    """Flag excessive daily procedure time and overlapping locations.

    Daily duration uses the configured estimate for each procedure code.
    If any active line lacks an estimate, the daily total for that
    provider/date is not evaluated because it would be incomplete.

    Location overlaps use actual start/end timestamps on claim lines.
    Corrected and reversed claims are excluded.
    """
    estimates = {
        estimate.procedure_code: estimate.estimated_minutes
        for estimate in procedure_time_estimates
    }

    daily_lines = defaultdict(list)
    flags = []

    for claim in claims:
        if claim.status != "active":
            continue

        for line in claim.lines:
            daily_lines[(claim.provider_id, line.service_date)].append(
                (claim, line)
            )

    for (provider_id, service_date), entries in daily_lines.items():
        missing_codes = sorted({
            line.procedure_code
            for _, line in entries
            if line.procedure_code not in estimates
        })

        if not missing_codes:
            total_minutes = sum(
                estimates[line.procedure_code] * line.units
                for _, line in entries
            )

            if total_minutes > 24 * 60:
                flags.append(
                    AnomalyFlag(
                        reason_code="IMPOSSIBLE_DAILY_SCHEDULE",
                        description=(
                            "Estimated procedure time exceeds 24 hours "
                            "for one provider on one service date."
                        ),
                        severity="high",
                        score=1.0,
                        claim_line_ids=tuple(
                            line.id for _, line in entries
                        ),
                        evidence={
                            "provider_id": provider_id,
                            "service_date": service_date.isoformat(),
                            "total_procedure_minutes": total_minutes,
                            "total_procedure_hours": total_minutes / 60,
                            "daily_limit_hours": 24,
                            "claim_ids": tuple(
                                claim.id for claim, _ in entries
                            ),
                        },
                    )
                )

        # Compare line intervals only when actual timestamps are available.
        timed_lines = [
            (claim, line)
            for claim, line in entries
            if line.start_time is not None
            and line.end_time is not None
            and line.location is not None
        ]

        overlaps = []
        for index, (claim_a, line_a) in enumerate(timed_lines):
            for claim_b, line_b in timed_lines[index + 1:]:
                if line_a.location == line_b.location:
                    continue

                # Intervals are half-open: touching endpoints do not overlap.
                if (
                    line_a.start_time < line_b.end_time
                    and line_b.start_time < line_a.end_time
                ):
                    overlaps.append((claim_a, line_a, claim_b, line_b))

        if overlaps:
            evidence_overlaps = [
                {
                    "first_line_id": line_a.id,
                    "first_start": line_a.start_time.isoformat(),
                    "first_end": line_a.end_time.isoformat(),
                    "first_location": line_a.location,
                    "second_line_id": line_b.id,
                    "second_start": line_b.start_time.isoformat(),
                    "second_end": line_b.end_time.isoformat(),
                    "second_location": line_b.location,
                }
                for _, line_a, _, line_b in overlaps
            ]

            line_ids = tuple(dict.fromkeys(
                line.id
                for _, line_a, _, line_b in overlaps
                for line in (line_a, line_b)
            ))

            flags.append(
                AnomalyFlag(
                    reason_code="OVERLAPPING_SERVICE_LOCATIONS",
                    description=(
                        "A provider has overlapping service times at "
                        "different locations on the same service date."
                    ),
                    severity="high",
                    score=0.99,
                    claim_line_ids=line_ids,
                    evidence={
                        "provider_id": provider_id,
                        "service_date": service_date.isoformat(),
                        "overlaps": evidence_overlaps,
                    },
                )
            )

    return sorted(
        flags,
        key=lambda flag: (
            flag.evidence["service_date"],
            flag.evidence["provider_id"],
            flag.reason_code,
        ),
    )