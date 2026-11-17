from datetime import datetime

from nurse_scheduler.models import (
    Assignment,
    CoverageRequirement,
    Shift,
    Staff,
    StaffRole,
    Ward,
)
from nurse_scheduler.scheduler import ShiftScheduler


def make_staff(staff_id, preferred_shifts=(), preferred_wards=()):
    return Staff(
        id=staff_id,
        name=f"Staff {staff_id}",
        role=StaffRole.NURSE,
        preferred_shift_types=frozenset(preferred_shifts),
        preferred_wards=frozenset(preferred_wards),
    )


def test_optimizer_prefers_staff_with_matching_shift_preference():
    staff = [
        make_staff("A", preferred_shifts={"day"}),
        make_staff("B", preferred_shifts={"night"}),
    ]
    ward = Ward("W1", "Ward 1", 1)
    shift = Shift(
        "D1",
        "day",
        datetime(2026, 11, 2, 8),
        datetime(2026, 11, 2, 16),
    )
    requirement = CoverageRequirement("W1", "D1", 1)

    result = ShiftScheduler().solve(staff, [ward], [shift], [requirement])

    assert result.is_feasible
    assert len(result.assignments) == 1
    assert result.assignments[0].staff_id == "A"


def test_optimizer_prefers_staff_with_matching_ward_preference():
    staff = [
        make_staff("A", preferred_wards={"W1"}),
        make_staff("B", preferred_wards={"W2"}),
    ]
    ward = Ward("W1", "Ward 1", 1)
    shift = Shift(
        "D1",
        "day",
        datetime(2026, 11, 2, 8),
        datetime(2026, 11, 2, 16),
    )
    requirement = CoverageRequirement("W1", "D1", 1)

    result = ShiftScheduler().solve(staff, [ward], [shift], [requirement])

    assert result.is_feasible
    assert len(result.assignments) == 1
    assert result.assignments[0].staff_id == "A"


def test_optimizer_uses_existing_roster_for_ward_continuity():
    staff = [make_staff("A"), make_staff("B")]
    wards = [
        Ward("W1", "Ward 1", 1),
        Ward("W2", "Ward 2", 1),
    ]
    shift = Shift(
        "D1",
        "day",
        datetime(2026, 11, 2, 8),
        datetime(2026, 11, 2, 16),
    )
    requirement = CoverageRequirement("W1", "D1", 1)
    existing = [
        Assignment("A", "W1", "OLD_SHIFT"),
        Assignment("B", "W2", "OLD_SHIFT"),
    ]

    result = ShiftScheduler().solve(
        staff,
        wards,
        [shift],
        [requirement],
        existing_assignments=existing,
    )

    assert result.is_feasible
    assert len(result.assignments) == 1
    assert result.assignments[0].staff_id == "A"


def test_optimizer_does_not_assign_extra_staff_without_need():
    staff = [make_staff("A"), make_staff("B"), make_staff("C")]
    ward = Ward("W1", "Ward 1", 1)
    shift = Shift(
        "D1",
        "day",
        datetime(2026, 11, 2, 8),
        datetime(2026, 11, 2, 16),
    )
    requirement = CoverageRequirement("W1", "D1", 1)

    result = ShiftScheduler().solve(staff, [ward], [shift], [requirement])

    assert result.is_feasible
    assert len(result.assignments) == 1


def test_optimizer_distributes_night_shifts_fairly():
    staff = [make_staff("A"), make_staff("B")]
    ward = Ward("W1", "Ward 1", 1)
    shifts = [
        Shift(
            f"N{day}",
            "night",
            datetime(2026, 11, day, 20),
            datetime(2026, 11, day + 1, 6),
        )
        for day in (2, 4)
    ]
    requirements = [
        CoverageRequirement("W1", shift.id, 1) for shift in shifts
    ]

    result = ShiftScheduler().solve(staff, [ward], shifts, requirements)

    assert result.is_feasible
    assert len(result.assignments) == 2
    assert {a.staff_id for a in result.assignments} == {"A", "B"}


def test_optimizer_preserves_existing_assignment_when_replanning():
    staff = [make_staff("A"), make_staff("B")]
    ward = Ward("W1", "Ward 1", 1)
    shift = Shift(
        "D1",
        "day",
        datetime(2026, 11, 2, 8),
        datetime(2026, 11, 2, 16),
    )
    requirement = CoverageRequirement("W1", "D1", 1)
    existing = [Assignment("A", "W1", "D1")]

    result = ShiftScheduler().solve(
        staff,
        [ward],
        [shift],
        [requirement],
        existing_assignments=existing,
    )

    assert result.is_feasible
    assert len(result.assignments) == 1
    assert result.assignments[0].staff_id == "A"


def test_sick_call_replanning_replaces_unavailable_staff():
    from nurse_scheduler.models import Leave

    staff = [make_staff("A"), make_staff("B")]
    ward = Ward("W1", "Ward 1", 1)
    shift = Shift(
        "D1",
        "day",
        datetime(2026, 11, 2, 8),
        datetime(2026, 11, 2, 16),
    )
    requirement = CoverageRequirement("W1", "D1", 1)
    existing = [Assignment("A", "W1", "D1")]
    sick_call = Leave(
        staff_id="A",
        start=datetime(2026, 11, 2, 0),
        end=datetime(2026, 11, 3, 0),
        approved=True,
    )

    result = ShiftScheduler().solve(
        staff,
        [ward],
        [shift],
        [requirement],
        leaves=[sick_call],
        existing_assignments=existing,
    )

    assert result.is_feasible
    assert len(result.assignments) == 1
    assert result.assignments[0].staff_id == "B"