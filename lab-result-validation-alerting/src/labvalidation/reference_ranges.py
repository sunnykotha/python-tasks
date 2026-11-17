from labvalidation.models import LabResult, ReferenceRange


class ReferenceRangeError(ValueError):
    """Raised when no safe, unambiguous reference range can be selected."""


def select_reference_range(
    result: LabResult,
    ranges: list[ReferenceRange],
) -> ReferenceRange:
    candidates = []

    for reference in ranges:
        if reference.test_code != result.test.code:
            continue

        age = result.patient_age_days

        if reference.min_age_days is not None:
            if age is None or age < reference.min_age_days:
                continue

        if reference.max_age_days is not None:
            if age is None or age > reference.max_age_days:
                continue

        if reference.sex is not None and reference.sex != result.sex:
            continue

        if reference.pregnancy_required is not None:
            if result.is_pregnant is None:
                continue
            if reference.pregnancy_required != result.is_pregnant:
                continue

        if reference.condition is not None:
            if result.condition != reference.condition:
                continue

        candidates.append(reference)

    if not candidates:
        raise ReferenceRangeError(
            f"No matching reference range for test {result.test.code}."
        )

    def specificity(reference):
        return (
            reference.condition is not None,
            reference.pregnancy_required is not None,
            reference.sex is not None,
            reference.min_age_days is not None,
            reference.max_age_days is not None,
        )

    best_specificity = max(specificity(r) for r in candidates)
    best = [r for r in candidates if specificity(r) == best_specificity]

    if len(best) != 1:
        raise ReferenceRangeError(
            f"Ambiguous reference ranges for test {result.test.code}."
        )

    return best[0]
