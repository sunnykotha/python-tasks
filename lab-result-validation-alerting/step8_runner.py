from pathlib import Path
import subprocess

project = Path(r"C:\Users\GK\lab-result-validation-alerting")
python = project / ".venv" / "Scripts" / "python.exe"

service = r'''
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
'''

tests = r'''
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
'''

(project / "src/labvalidation/specimen_quality.py").write_text(
    service.lstrip(), encoding="utf-8"
)
(project / "tests/test_specimen_quality.py").write_text(
    tests.lstrip(), encoding="utf-8"
)

result = subprocess.run(
    [str(python), "-m", "pytest", "-v"],
    cwd=project,
)

if result.returncode == 0:
    print("\nSTEP 8 PASSED: Specimen quality tests passed.")
if result.returncode != 0:
    print(f"\nSTEP 8 FAILED: pytest returned {result.returncode}.")