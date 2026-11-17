from datetime import datetime, timedelta

from nurse_scheduler.models import (
    CoverageRequirement,
    Shift,
    Staff,
    StaffRole,
    Ward,
)
from nurse_scheduler.scheduler import ShiftScheduler


def make_staff(max_weekly_hours=40):
    return Staff(
        id="nurse-1",
        name="Nurse One",
        role=StaffRole.NURSE,
        max_weekly_hours=max_weekly_hours,
    )


def make_requirement(shift_id):
    return CoverageRequirement(
        ward_id="ward-1",
        shift_id=shift_id,
        minimum_staff=1,
        required_role=StaffRole.NURSE,
    )


def test_infeasible_schedule_due_to_insufficient_rest_is_reported():
    ward = Ward("ward-1", "Ward 1", 1)
    first = Shift(
        "night",
        "night",
        datetime(2026, 1, 5, 20),
        datetime(2026, 1, 6, 8),
    )
    second = Shift(
        "early",
        "early",
        datetime(2026, 1, 6, 16),
        datetime(2026, 1, 7, 0),
    )

    result = ShiftScheduler().solve(
        staff=[make_staff()],
        wards=[ward],
        shifts=[first, second],
        requirements=[make_requirement("night"), make_requirement("early")],
    )

    assert not result.is_feasible
    assert result.diagnostics
    assert any(
        "minimum 11-hour rest" in message.lower()
        for message in result.diagnostics
    )


def test_infeasible_schedule_due_to_consecutive_shift_limit_is_reported():
    ward = Ward("ward-1", "Ward 1", 1)
    monday = datetime(2026, 1, 5, 8)
    shifts = [
        Shift(
            f"shift-{day}",
            "day",
            monday + timedelta(days=day),
            monday + timedelta(days=day, hours=8),
        )
        for day in range(6)
    ]

    result = ShiftScheduler().solve(
        staff=[make_staff()],
        wards=[ward],
        shifts=shifts,
        requirements=[
            make_requirement(shift.id) for shift in shifts
        ],
    )

    assert not result.is_feasible
    assert result.diagnostics
    assert any(
        "five shifts in six consecutive days" in message.lower()
        for message in result.diagnostics
    )


def test_infeasible_schedule_due_to_weekly_hours_is_reported():
    ward = Ward("ward-1", "Ward 1", 1)
    monday = datetime(2026, 1, 5, 8)
    shift_days = [0, 1, 2, 3, 4, 6]
    shifts = [
        Shift(
            f"shift-{day}",
            "day",
            monday + timedelta(days=day),
            monday + timedelta(days=day, hours=10),
        )
        for day in shift_days
    ]

    result = ShiftScheduler().solve(
        staff=[make_staff(max_weekly_hours=40)],
        wards=[ward],
        shifts=shifts,
        requirements=[
            make_requirement(shift.id) for shift in shifts
        ],
    )

    assert not result.is_feasible
    assert result.diagnostics
    assert any(
        "weekly working-hour cap" in message.lower()
        for message in result.diagnostics
    )
