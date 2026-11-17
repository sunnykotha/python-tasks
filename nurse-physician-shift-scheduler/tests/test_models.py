from datetime import datetime

import pytest

from nurse_scheduler.models import (
    Assignment,
    CoverageRequirement,
    Leave,
    PenaltyScore,
    Shift,
    Skill,
    Staff,
    StaffRole,
    Ward,
)


def test_skill_requires_a_name():
    with pytest.raises(ValueError):
        Skill("")


def test_staff_can_have_icu_certification():
    icu = Skill("ICU")
    staff = Staff(
        id="A",
        name="Staff A",
        role=StaffRole.NURSE,
        skills=frozenset({icu}),
    )
    assert icu in staff.skills


def test_staff_rejects_invalid_weekly_hours():
    with pytest.raises(ValueError):
        Staff("A", "Staff A", StaffRole.NURSE, max_weekly_hours=0)


def test_staff_rejects_invalid_fixed_day():
    with pytest.raises(ValueError):
        Staff(
            "A", "Staff A", StaffRole.NURSE,
            fixed_days=frozenset({7}),
        )


def test_staff_requires_valid_role():
    with pytest.raises(ValueError):
        Staff("A", "Staff A", "nurse")


def test_ward_rejects_negative_patient_count():
    with pytest.raises(ValueError):
        Ward("W1", "Ward 1", -1)


def test_shift_calculates_overnight_duration():
    shift = Shift(
        "N1",
        "night",
        datetime(2026, 10, 29, 20, 0),
        datetime(2026, 10, 30, 8, 0),
    )
    assert shift.duration_hours == 12
    assert shift.shift_date.isoformat() == "2026-10-29"


def test_shift_rejects_invalid_time_range():
    with pytest.raises(ValueError):
        Shift(
            "S1", "day",
            datetime(2026, 10, 29, 10, 0),
            datetime(2026, 10, 29, 9, 0),
        )


def test_leave_rejects_invalid_time_range():
    with pytest.raises(ValueError):
        Leave(
            "A",
            datetime(2026, 10, 29, 12, 0),
            datetime(2026, 10, 29, 11, 0),
        )


def test_coverage_requirement_stores_skill_counts():
    requirement = CoverageRequirement(
        "W3", "N1", 2, {"ICU": 1}
    )
    assert requirement.minimum_staff == 2
    assert requirement.required_skill_counts["ICU"] == 1


def test_coverage_rejects_negative_skill_count():
    with pytest.raises(ValueError):
        CoverageRequirement("W3", "N1", 2, {"ICU": -1})


def test_assignment_identifies_staff_ward_and_shift():
    assignment = Assignment("B", "W3", "N1")
    assert (assignment.staff_id, assignment.ward_id, assignment.shift_id) == (
        "B", "W3", "N1"
    )


def test_penalty_score_calculates_total():
    score = PenaltyScore(
        night_shift_penalty=3,
        weekend_penalty=2,
        preference_penalty=4,
        ward_continuity_penalty=1,
    )
    assert score.total == 10


def test_penalty_score_rejects_negative_values():
    with pytest.raises(ValueError):
        PenaltyScore(night_shift_penalty=-1)


def test_part_time_staff_can_have_fixed_days():
    staff = Staff(
        "P1",
        "Part-time Nurse",
        StaffRole.NURSE,
        is_part_time=True,
        fixed_days=frozenset({0, 2, 4}),
    )
    assert staff.is_part_time
    assert staff.fixed_days == frozenset({0, 2, 4})


def test_unapproved_leave_is_represented():
    leave = Leave(
        "A",
        datetime(2026, 10, 29, 8, 0),
        datetime(2026, 10, 29, 17, 0),
        approved=False,
    )
    assert not leave.approved
