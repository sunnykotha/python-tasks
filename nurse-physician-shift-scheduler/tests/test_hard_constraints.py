from datetime import datetime, timedelta

from nurse_scheduler.models import (
    CoverageRequirement,
    Shift,
    Staff,
    StaffRole,
    Ward,
)
from nurse_scheduler.scheduler import ShiftScheduler


def make_day_shift(shift_id, day, start_hour, end_hour, duration_day=0):
    start = datetime(2026, 10, day, start_hour)
    end_date = start.date() + timedelta(days=duration_day)
    end = datetime.combine(end_date, datetime.min.time()).replace(
        hour=end_hour
    )
    return Shift(shift_id, "day", start, end)


def make_nurse(staff_id, max_hours=40, part_time=False, fixed_days=()):
    return Staff(
        id=staff_id,
        name=f"Staff {staff_id}",
        role=StaffRole.NURSE,
        max_weekly_hours=max_hours,
        is_part_time=part_time,
        fixed_days=frozenset(fixed_days),
    )


def test_eleven_hour_rest_blocks_early_shift_after_night_shift():
    staff = [make_nurse("A"), make_nurse("B")]
    wards = [Ward("W1", "Ward 1", 1), Ward("W2", "Ward 2", 1)]
    shifts = [
        Shift(
            "N1", "night",
            datetime(2026, 10, 29, 20),
            datetime(2026, 10, 30, 6),
        ),
        Shift(
            "E1", "early",
            datetime(2026, 10, 30, 10),
            datetime(2026, 10, 30, 14),
        ),
    ]
    requirements = [
        CoverageRequirement("W1", "N1", 1),
        CoverageRequirement("W2", "E1", 1),
    ]

    result = ShiftScheduler().solve(staff, wards, shifts, requirements)

    assert result.is_feasible
    assigned = {
        a.shift_id: a.staff_id for a in result.assignments
    }
    assert assigned["N1"] != assigned["E1"]


def test_six_consecutive_daily_shifts_are_not_allowed():
    staff = [make_nurse("A"), make_nurse("B")]
    wards = [Ward("W1", "Ward 1", 1)]
    shifts = [
        Shift(
            f"S{day}", "day",
            datetime(2026, 10, day, 8),
            datetime(2026, 10, day, 12),
        )
        for day in range(26, 32)
    ]
    requirements = [
        CoverageRequirement("W1", shift.id, 1) for shift in shifts
    ]

    result = ShiftScheduler().solve(staff, wards, shifts, requirements)

    assert result.is_feasible
    staff_by_day = {
        int(a.shift_id[1:]): a.staff_id for a in result.assignments
    }
    assert len(staff_by_day) == 6
    assert len(set(staff_by_day.values())) >= 2


def test_weekly_hour_cap_is_enforced():
    staff = [make_nurse("A", max_hours=8)]
    ward = Ward("W1", "Ward 1", 1)
    shifts = [
        Shift(
            "S1", "day",
            datetime(2026, 10, 26, 8),
            datetime(2026, 10, 26, 16),
        ),
        Shift(
            "S2", "day",
            datetime(2026, 10, 27, 8),
            datetime(2026, 10, 27, 16),
        ),
    ]
    requirements = [
        CoverageRequirement("W1", shift.id, 1) for shift in shifts
    ]

    result = ShiftScheduler().solve(
        staff, [ward], shifts, requirements
    )

    assert not result.is_feasible
    assert result.status == "INFEASIBLE"


def test_part_time_staff_is_not_assigned_outside_fixed_days():
    # Monday is 0 and Tuesday is 1.
    staff = [
        make_nurse("P1", part_time=True, fixed_days={0}),
        make_nurse("F1"),
    ]
    ward = Ward("W1", "Ward 1", 1)
    shift = Shift(
        "TUE", "day",
        datetime(2026, 10, 27, 8),
        datetime(2026, 10, 27, 12),
    )
    requirement = CoverageRequirement("W1", "TUE", 1)

    result = ShiftScheduler().solve(
        staff, [ward], [shift], [requirement]
    )

    assert result.is_feasible
    assert {a.staff_id for a in result.assignments} == {"F1"}


def test_five_consecutive_nights_cannot_be_extended_to_six_for_same_staff():
    staff = [make_nurse("A"), make_nurse("B")]
    ward = Ward("W3", "Ward 3", 2)
    shifts = [
        Shift(
            f"N{day}", "night",
            datetime(2026, 10, day, 20),
            datetime(2026, 10, day + 1, 6),
        )
        for day in range(24, 30)
    ]
    requirements = [
        CoverageRequirement("W3", shift.id, 1) for shift in shifts
    ]

    result = ShiftScheduler().solve(staff, [ward], shifts, requirements)

    assert result.is_feasible
    assigned_staff = [a.staff_id for a in result.assignments]
    assert len(assigned_staff) == 6
    assert len(set(assigned_staff)) >= 2


def test_emergency_schedule_allows_weekly_overtime():
    staff = [make_nurse("A", max_hours=8)]
    ward = Ward("W1", "Ward 1", 1)
    shifts = [
        Shift(
            "S1", "day",
            datetime(2026, 10, 26, 8),
            datetime(2026, 10, 26, 16),
        ),
        Shift(
            "S2", "day",
            datetime(2026, 10, 27, 8),
            datetime(2026, 10, 27, 16),
        ),
    ]
    requirements = [
        CoverageRequirement("W1", shift.id, 1) for shift in shifts
    ]

    result = ShiftScheduler().solve(
        staff, [ward], shifts, requirements, emergency=True
    )

    assert result.is_feasible
    assert {a.shift_id for a in result.assignments} == {"S1", "S2"}


def test_normal_schedule_does_not_allow_weekly_overtime():
    staff = [make_nurse("A", max_hours=8)]
    ward = Ward("W1", "Ward 1", 1)
    shifts = [
        Shift(
            "S1", "day",
            datetime(2026, 10, 26, 8),
            datetime(2026, 10, 26, 16),
        ),
        Shift(
            "S2", "day",
            datetime(2026, 10, 27, 8),
            datetime(2026, 10, 27, 16),
        ),
    ]
    requirements = [
        CoverageRequirement("W1", shift.id, 1) for shift in shifts
    ]

    result = ShiftScheduler().solve(
        staff, [ward], shifts, requirements
    )

    assert not result.is_feasible
    assert result.status == "INFEASIBLE"