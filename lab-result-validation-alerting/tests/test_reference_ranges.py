from datetime import datetime, timezone
import pytest

from labvalidation.models import (
    Unit, LabTestDefinition, LabResult, ReferenceRange, Sex
)
from labvalidation.reference_ranges import (
    select_reference_range, ReferenceRangeError
)


@pytest.fixture
def setup_data():
    unit = Unit("mmol/L", "millimoles per litre")
    test = LabTestDefinition("K", "Potassium", unit)

    def result(age, sex=Sex.UNKNOWN, pregnant=None, condition=None):
        return LabResult(
            result_id="R1",
            patient_id="P1",
            test=test,
            value="4.0",
            unit=unit,
            collected_at=datetime.now(timezone.utc),
            patient_age_days=age,
            sex=sex,
            is_pregnant=pregnant,
            condition=condition,
        )

    def reference(low, high, min_age=None, max_age=None,
                  sex=None, pregnancy=None, condition=None):
        return ReferenceRange(
            test_code="K",
            low=low,
            high=high,
            unit=unit,
            min_age_days=min_age,
            max_age_days=max_age,
            sex=sex,
            pregnancy_required=pregnancy,
            condition=condition,
        )

    return result, reference


def test_newborn_age_is_measured_in_days(setup_data):
    result, reference = setup_data
    newborn = reference(3.0, 6.0, min_age=0, max_age=2)
    adult = reference(3.5, 5.1, min_age=6570)
    assert select_reference_range(result(1), [newborn, adult]) == newborn


def test_adult_range_selected_by_age(setup_data):
    result, reference = setup_data
    child = reference(3.0, 6.0, min_age=0, max_age=6574)
    adult = reference(3.5, 5.1, min_age=6575)
    assert select_reference_range(result(30 * 365), [child, adult]) == adult


def test_sex_specific_range_preferred(setup_data):
    result, reference = setup_data
    general = reference(3.5, 5.1, min_age=18 * 365)
    male = reference(3.6, 5.2, min_age=18 * 365, sex=Sex.MALE)
    selected = select_reference_range(
        result(40 * 365, Sex.MALE), [general, male]
    )
    assert selected == male


def test_pregnancy_specific_range_preferred(setup_data):
    result, reference = setup_data
    general = reference(3.5, 5.1, min_age=18 * 365)
    pregnant = reference(
        3.4, 5.0, min_age=18 * 365,
        sex=Sex.FEMALE, pregnancy=True
    )
    selected = select_reference_range(
        result(30 * 365, Sex.FEMALE, True), [general, pregnant]
    )
    assert selected == pregnant


def test_condition_specific_range_preferred(setup_data):
    result, reference = setup_data
    general = reference(3.5, 5.1, min_age=18 * 365)
    condition_range = reference(
        3.4, 5.0, min_age=18 * 365, condition="condition_x"
    )
    selected = select_reference_range(
        result(40 * 365, condition="condition_x"),
        [general, condition_range],
    )
    assert selected == condition_range


def test_no_matching_range_raises_error(setup_data):
    result, reference = setup_data
    infant = reference(3.0, 6.0, min_age=0, max_age=30)
    with pytest.raises(ReferenceRangeError):
        select_reference_range(result(40 * 365), [infant])


def test_overlapping_equally_specific_ranges_are_rejected(setup_data):
    result, reference = setup_data
    first = reference(3.0, 5.0, min_age=0, max_age=1000)
    second = reference(3.5, 5.5, min_age=0, max_age=1000)
    with pytest.raises(ReferenceRangeError, match="Ambiguous"):
        select_reference_range(result(100), [first, second])


def test_missing_age_does_not_match_age_restricted_range(setup_data):
    result, reference = setup_data
    age_range = reference(3.5, 5.1, min_age=18 * 365)
    with pytest.raises(ReferenceRangeError):
        select_reference_range(result(None), [age_range])


def test_missing_pregnancy_status_does_not_match_pregnancy_range(setup_data):
    result, reference = setup_data
    pregnancy_range = reference(
        3.5, 5.1, min_age=18 * 365,
        sex=Sex.FEMALE, pregnancy=True
    )
    with pytest.raises(ReferenceRangeError):
        select_reference_range(
            result(30 * 365, Sex.FEMALE, None), [pregnancy_range]
        )
