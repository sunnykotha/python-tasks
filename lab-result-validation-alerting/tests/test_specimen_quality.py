import pytest

from labvalidation.specimen_quality import (
    assess_specimen, SpecimenAssessment
)


def test_hemolyzed_potassium_is_held_for_review():
    result = assess_specimen("POTASSIUM", True)
    assert result.interpretation_allowed is False
    assert result.requires_recollection_review is True
    assert "Hemolyzed" in result.reason


def test_non_hemolyzed_potassium_can_be_interpreted():
    result = assess_specimen("POTASSIUM", False)
    assert result.interpretation_allowed is True
    assert result.requires_recollection_review is False


def test_unaffected_test_is_not_blocked_by_default():
    result = assess_specimen("HEMOGLOBIN", True)
    assert result.interpretation_allowed is True
    assert result.requires_recollection_review is False


def test_configured_sensitive_test_is_blocked():
    result = assess_specimen(
        "SODIUM", True, sensitive_tests={"SODIUM", "POTASSIUM"}
    )
    assert result.interpretation_allowed is False
    assert result.requires_recollection_review is True


def test_custom_configuration_can_leave_potassium_unblocked():
    result = assess_specimen(
        "POTASSIUM", True, sensitive_tests={"SODIUM"}
    )
    assert result.interpretation_allowed is True


def test_test_code_matching_ignores_case_and_surrounding_spaces():
    result = assess_specimen(" potassium ", True)
    assert result.interpretation_allowed is False


def test_empty_test_code_is_rejected():
    with pytest.raises(ValueError, match="non-empty"):
        assess_specimen(" ", True)


def test_hemolysis_flag_must_be_boolean():
    with pytest.raises(ValueError, match="boolean"):
        assess_specimen("POTASSIUM", "yes")


def test_assessment_is_immutable():
    result = assess_specimen("POTASSIUM", True)
    with pytest.raises(AttributeError):
        result.interpretation_allowed = True
