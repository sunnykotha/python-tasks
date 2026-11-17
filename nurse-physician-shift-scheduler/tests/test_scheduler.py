from datetime import datetime

from nurse_scheduler.models import (
    CoverageRequirement,
    Leave,
    Shift,
    Skill,
    Staff,
    StaffRole,
    Ward,
)
from nurse_scheduler.scheduler import ShiftScheduler


def make_shift(shift_id, start_hour, end_hour, day=29):
    start = datetime(2026, 10, day, start_hour)
    end_day = day + (1 if end_hour <= start_hour else 0)
    end = datetime(2026, 10, end_day, end_hour)
    return Shift(shift_id, "night", start, end)


def make_nurse(staff_id, skills=()):
    return Staff(
        staff_id,
        f"Staff {staff_id}",
        StaffRole.NURSE,
        skills=frozenset(skills),
    )


def test_scheduler_fills_minimum_coverage():
    staff = [make_nurse("A"), make_nurse("B")]
    ward = Ward("W1", "Ward 1", 4)
    shift = make_shift("N1", 20, 8)
    requirement = CoverageRequirement("W1", "N1", 2)

    result = ShiftScheduler().solve(
        staff, [ward], [shift], [requirement]
    )

    assert result.is_feasible
    assert len(result.assignments) == 2
    assert {a.staff_id for a in result.assignments} == {"A", "B"}


def test_scheduler_requires_qualified_staff_for_specialist_coverage():
    icu = Skill("ICU")
    staff = [make_nurse("A"), make_nurse("B", [icu])]
    ward = Ward("W3", "Ward 3", 4)
    shift = make_shift("N1", 20, 8)
    requirement = CoverageRequirement(
        "W3", "N1", 2, {"ICU": 1}
    )

    result = ShiftScheduler().solve(
        staff, [ward], [shift], [requirement]
    )

    assert result.is_feasible
    assigned_ids = {a.staff_id for a in result.assignments}
    assert assigned_ids == {"A", "B"}
    assert any(
        a.staff_id == "B" and a.ward_id == "W3"
        for a in result.assignments
    )


def test_scheduler_respects_approved_leave():
    staff = [make_nurse("A"), make_nurse("B")]
    ward = Ward("W1", "Ward 1", 1)
    shift = make_shift("N1", 20, 8)
    requirement = CoverageRequirement("W1", "N1", 1)
    leave = Leave(
        "A",
        datetime(2026, 10, 29, 19),
        datetime(2026, 10, 30, 9),
        approved=True,
    )

    result = ShiftScheduler().solve(
        staff, [ward], [shift], [requirement], [leave]
    )

    assert result.is_feasible
    assert {a.staff_id for a in result.assignments} == {"B"}


def test_scheduler_prevents_overlapping_shift_assignments():
    staff = [make_nurse("A"), make_nurse("B")]
    wards = [Ward("W1", "Ward 1", 1), Ward("W2", "Ward 2", 1)]
    shifts = [
        make_shift("N1", 20, 8),
        make_shift("N2", 22, 6),
    ]
    requirements = [
        CoverageRequirement("W1", "N1", 1),
        CoverageRequirement("W2", "N2", 1),
    ]

    result = ShiftScheduler().solve(staff, wards, shifts, requirements)

    assert result.is_feasible
    assert len(result.assignments) == 2
    assert len({a.staff_id for a in result.assignments}) == 2


def test_scheduler_reports_infeasible_when_coverage_is_impossible():
    staff = [make_nurse("A")]
    ward = Ward("W1", "Ward 1", 2)
    shift = make_shift("N1", 20, 8)
    requirement = CoverageRequirement("W1", "N1", 2)

    result = ShiftScheduler().solve(
        staff, [ward], [shift], [requirement]
    )

    assert not result.is_feasible
    assert result.status == "INFEASIBLE"
    assert result.assignments == ()

def test_infeasible_schedule_returns_diagnostic():
    from datetime import datetime, timedelta

    from nurse_scheduler.models import CoverageRequirement, Shift, Ward
    from nurse_scheduler.scheduler import ShiftScheduler

    shift = Shift(
        id="shift-diagnostic",
        shift_type="day",
        start=datetime(2026, 11, 2, 8, 0),
        end=datetime(2026, 11, 2, 16, 0),
    )
    ward = Ward(id="ward-diagnostic", name="Diagnostic Ward", patient_count=1)
    requirement = CoverageRequirement(
        ward_id=ward.id,
        shift_id=shift.id,
        minimum_staff=1,
    )

    result = ShiftScheduler().solve(
        staff=[],
        wards=[ward],
        shifts=[shift],
        requirements=[requirement],
    )

    assert result.status == "INFEASIBLE"
    assert result.assignments == ()
    assert result.diagnostics
    assert "only 0 are eligible" in result.diagnostics[0]

def test_infeasible_required_skill_returns_diagnostic():
    from datetime import datetime

    from nurse_scheduler.models import (
        CoverageRequirement,
        Shift,
        Staff,
        StaffRole,
        Ward,
    )
    from nurse_scheduler.scheduler import ShiftScheduler

    shift = Shift(
        id="shift-skill-diagnostic",
        shift_type="day",
        start=datetime(2026, 11, 3, 8, 0),
        end=datetime(2026, 11, 3, 16, 0),
    )
    ward = Ward(id="ward-skill-diagnostic", name="Skill Ward", patient_count=1)
    staff = Staff(
        id="staff-general",
        name="General Staff",
        role=StaffRole.NURSE,
    )
    requirement = CoverageRequirement(
        ward_id=ward.id,
        shift_id=shift.id,
        minimum_staff=1,
        required_skill_counts={"critical-care": 1},
    )

    result = ShiftScheduler().solve(
        staff=[staff],
        wards=[ward],
        shifts=[shift],
        requirements=[requirement],
    )

    assert result.status == "INFEASIBLE"
    assert result.assignments == ()
    assert result.diagnostics
    assert "critical-care" in result.diagnostics[0]

def test_approved_leave_causing_infeasibility_is_explained():
    from datetime import datetime, timedelta

    from nurse_scheduler.models import (
        CoverageRequirement,
        Leave,
        Shift,
        Staff,
        StaffRole,
        Ward,
    )
    from nurse_scheduler.scheduler import ShiftScheduler

    shift = Shift(
        id="shift-leave-diagnostic",
        shift_type="day",
        start=datetime(2026, 11, 4, 8, 0),
        end=datetime(2026, 11, 4, 16, 0),
    )
    ward = Ward(id="ward-leave-diagnostic", name="Leave Ward", patient_count=1)
    staff = Staff(
        id="staff-on-leave",
        name="Staff On Leave",
        role=StaffRole.NURSE,
    )
    leave = Leave(
        staff_id=staff.id,
        start=shift.start - timedelta(hours=1),
        end=shift.end + timedelta(hours=1),
        approved=True,
    )
    requirement = CoverageRequirement(
        ward_id=ward.id,
        shift_id=shift.id,
        minimum_staff=1,
    )

    result = ShiftScheduler().solve(
        staff=[staff],
        wards=[ward],
        shifts=[shift],
        requirements=[requirement],
        leaves=[leave],
    )

    assert result.status == "INFEASIBLE"
    assert result.assignments == ()
    assert result.diagnostics
    assert "only 0 are eligible" in result.diagnostics[0]

def test_part_time_fixed_day_causing_infeasibility_is_explained():
    from datetime import datetime

    from nurse_scheduler.models import (
        CoverageRequirement,
        Shift,
        Staff,
        StaffRole,
        Ward,
    )
    from nurse_scheduler.scheduler import ShiftScheduler

    # 2026-11-05 is Thursday (weekday 3); this staff member only works Mondays.
    shift = Shift(
        id="shift-fixed-day-diagnostic",
        shift_type="day",
        start=datetime(2026, 11, 5, 8, 0),
        end=datetime(2026, 11, 5, 16, 0),
    )
    ward = Ward(
        id="ward-fixed-day-diagnostic",
        name="Fixed Day Ward",
        patient_count=1,
    )
    staff = Staff(
        id="staff-part-time",
        name="Part-Time Staff",
        role=StaffRole.NURSE,
        is_part_time=True,
        fixed_days=frozenset({0}),
    )
    requirement = CoverageRequirement(
        ward_id=ward.id,
        shift_id=shift.id,
        minimum_staff=1,
    )

    result = ShiftScheduler().solve(
        staff=[staff],
        wards=[ward],
        shifts=[shift],
        requirements=[requirement],
    )

    assert result.status == "INFEASIBLE"
    assert result.assignments == ()
    assert result.diagnostics
    assert "only 0 are eligible" in result.diagnostics[0]
