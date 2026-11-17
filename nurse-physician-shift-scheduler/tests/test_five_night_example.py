from datetime import datetime, timedelta

from nurse_scheduler.models import (
    Assignment,
    CoverageRequirement,
    Shift,
    Skill,
    Staff,
    StaffRole,
    Ward,
)
from nurse_scheduler.scheduler import ShiftScheduler


def test_five_consecutive_nights_override_stronger_shift_preference():
    monday = datetime(2026, 1, 5, 20)
    ward = Ward("ward-3", "Ward 3", 2)

    shifts = [
        Shift(
            id=f"night-{day}",
            shift_type="night",
            start=monday + timedelta(days=day),
            end=monday + timedelta(days=day, hours=8),
        )
        for day in range(7)
    ]

    icu_skill = Skill("ICU-certified")

    nurse_a = Staff(
        id="nurse-a",
        name="Nurse A",
        role=StaffRole.NURSE,
        skills=frozenset({icu_skill}),
        preferred_shift_types=frozenset({"night"}),
    )
    nurse_b = Staff(
        id="nurse-b",
        name="Nurse B",
        role=StaffRole.NURSE,
        skills=frozenset({icu_skill}),
    )
    nurse_c = Staff(
        id="nurse-c",
        name="Nurse C",
        role=StaffRole.NURSE,
    )

    requirements = [
        CoverageRequirement(
            ward_id=ward.id,
            shift_id=shift.id,
            minimum_staff=2,
            required_skill_counts={"ICU-certified": 1},
            required_role=StaffRole.NURSE,
        )
        for shift in shifts
    ]

    existing = [
        Assignment(
            staff_id=nurse_a.id,
            ward_id=ward.id,
            shift_id=f"night-{day}",
        )
        for day in range(5)
    ]

    result = ShiftScheduler().solve(
        staff=[nurse_a, nurse_b, nurse_c],
        wards=[ward],
        shifts=shifts,
        requirements=requirements,
        existing_assignments=existing,
    )

    assert result.is_feasible

    assignments_by_shift = {
        shift.id: [
            assignment
            for assignment in result.assignments
            if assignment.shift_id == shift.id
        ]
        for shift in shifts
    }

    for shift in shifts:
        assigned = assignments_by_shift[shift.id]
        assert len(assigned) == 2
        assert any(
            staff_id in {nurse_a.id, nurse_b.id}
            for staff_id in (assignment.staff_id for assignment in assigned)
        )

        assigned_staff = {
            assignment.staff_id for assignment in assigned
        }
        assert assigned_staff.intersection({nurse_a.id, nurse_b.id})

        if shift.id == "night-5":
            assert nurse_a.id not in assigned_staff
            assert nurse_b.id in assigned_staff
            assert nurse_c.id in assigned_staff

        assert any(
            assignment.staff_id in {nurse_a.id, nurse_b.id}
            for assignment in assigned
        )

    for shift in shifts:
        assigned_ids = {
            assignment.staff_id
            for assignment in assignments_by_shift[shift.id]
        }
        assigned_people = [
            person
            for person in [nurse_a, nurse_b, nurse_c]
            if person.id in assigned_ids
        ]
        assert any(
            any(skill.name == "ICU-certified" for skill in person.skills)
            for person in assigned_people
        )

    nurse_a_days = sorted(
        int(assignment.shift_id.split("-")[1])
        for assignment in result.assignments
        if assignment.staff_id == nurse_a.id
    )
    assert not any(
        all(day in nurse_a_days for day in range(start, start + 6))
        for start in range(2)
    )