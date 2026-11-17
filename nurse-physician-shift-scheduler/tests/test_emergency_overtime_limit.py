from datetime import datetime, timedelta

from nurse_scheduler.models import (
    CoverageRequirement,
    Shift,
    Staff,
    StaffRole,
    Ward,
)
from nurse_scheduler.scheduler import ShiftScheduler


def test_emergency_mode_does_not_allow_unlimited_weekly_overtime():
    staff = Staff(
        id="nurse-1",
        name="Nurse One",
        role=StaffRole.NURSE,
        max_weekly_hours=40,
    )
    ward = Ward(id="ward-1", name="Ward 1", patient_count=1)
    monday = datetime(2026, 1, 5, 8, 0)

    # Six 10-hour shifts total 60 hours in one week.
    # Five consecutive shifts are permitted, but the sixth is after a rest day.
    shift_days = [0, 1, 2, 3, 4, 6]
    shifts = [
        Shift(
            id=f"shift-{day}",
            shift_type="day",
            start=monday + timedelta(days=day),
            end=monday + timedelta(days=day, hours=10),
        )
        for day in shift_days
    ]
    requirements = [
        CoverageRequirement(
            ward_id=ward.id,
            shift_id=shift.id,
            minimum_staff=1,
            required_role=StaffRole.NURSE,
        )
        for shift in shifts
    ]

    result = ShiftScheduler().solve(
        staff=[staff],
        wards=[ward],
        shifts=shifts,
        requirements=requirements,
        emergency=True,
    )

    assert not result.is_feasible
