from dataclasses import dataclass


@dataclass(frozen=True)
class SpecimenAssessment:
    interpretation_allowed: bool
    requires_recollection_review: bool
    reason: str


DEFAULT_HEMOLYSIS_SENSITIVE_TESTS = frozenset({
    "POTASSIUM",
})


def assess_specimen(test_code: str, specimen_hemolyzed: bool,
                    sensitive_tests=None) -> SpecimenAssessment:
    if not isinstance(test_code, str) or not test_code.strip():
        raise ValueError("Test code must be a non-empty string.")

    if not isinstance(specimen_hemolyzed, bool):
        raise ValueError("specimen_hemolyzed must be a boolean.")

    configured = DEFAULT_HEMOLYSIS_SENSITIVE_TESTS
    if sensitive_tests is not None:
        configured = frozenset(code.strip().upper() for code in sensitive_tests)

    normalized_code = test_code.strip().upper()

    if not specimen_hemolyzed:
        return SpecimenAssessment(
            True, False, "Specimen is not marked hemolyzed."
        )

    if normalized_code in configured:
        return SpecimenAssessment(
            False,
            True,
            "Hemolyzed specimen may affect this result; review and consider recollection."
        )

    return SpecimenAssessment(
        True,
        False,
        "Hemolysis is not configured to block interpretation for this test."
    )
