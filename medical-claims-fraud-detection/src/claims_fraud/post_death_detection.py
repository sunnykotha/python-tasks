"""Detection of services billed after a patient's recorded date of death."""

from claims_fraud.models import AnomalyFlag, Claim, Patient


def detect_post_death_services(
    claims: list[Claim],
    patients: list[Patient],
) -> list[AnomalyFlag]:
    """Flag active claim lines with service dates after recorded death.

    A service on the recorded date of death is not flagged by this rule.
    Corrected and reversed claims are excluded.
    """
    patient_by_id = {patient.id: patient for patient in patients}
    flags = []

    for claim in claims:
        if claim.status != "active":
            continue

        patient = patient_by_id.get(claim.patient_id)
        if patient is None or patient.date_of_death is None:
            continue

        for line in claim.lines:
            if line.service_date <= patient.date_of_death:
                continue

            flags.append(
                AnomalyFlag(
                    reason_code="SERVICE_AFTER_DATE_OF_DEATH",
                    description=(
                        "The service date is after the patient's recorded "
                        "date of death."
                    ),
                    severity="critical",
                    score=1.0,
                    claim_line_ids=(line.id,),
                    evidence={
                        "claim_id": claim.id,
                        "patient_id": patient.id,
                        "provider_id": claim.provider_id,
                        "procedure_code": line.procedure_code,
                        "service_date": line.service_date.isoformat(),
                        "date_of_death": patient.date_of_death.isoformat(),
                    },
                )
            )

    return sorted(
        flags,
        key=lambda flag: (
            flag.evidence["service_date"],
            flag.evidence["patient_id"],
            flag.evidence["claim_id"],
        ),
    )