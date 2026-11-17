from datetime import datetime

from nurse_scheduler.models import (
    CoverageRequirement,
    Shift,
    Staff,
    StaffRole,
    Ward,
)
from nurse_scheduler.scheduler import ShiftScheduler


def make_staff(staff_id, role):
    return Staff(id=staff_id, name=staff_id, role=role)


def test_physician_cannot_fill_nurse_coverage_requirement():
    shift = Shift(
        "N1", "night",
        datetime(2026, 11, 2, 20),
        datetime(2026, 11, 3, 6),
    )
    requirement = CoverageRequirement(
        "W1", "N1", 1, required_role=StaffRole.NURSE
    )

    result = ShiftScheduler().solve(
        [make_staff("P1", StaffRole.PHYSICIAN)],
        [Ward("W1", "Ward 1", 2)],
        [shift],
        [requirement],
    )

    assert not result.is_feasible
    assert any("only 0 are eligible" in item for item in result.diagnostics)


def test_nurse_cannot_fill_physician_coverage_requirement():
    shift = Shift(
        "D1", "day",
        datetime(2026, 11, 2, 8),
        datetime(2026, 11, 2, 16),
    )
    requirement = CoverageRequirement(
        "W1", "D1", 1, required_role=StaffRole.PHYSICIAN
    )

    result = ShiftScheduler().solve(
        [make_staff("N1", StaffRole.NURSE)],
        [Ward("W1", "Ward 1", 1)],
        [shift],
        [requirement],
    )

    assert not result.is_feasible
    assert any("only 0 are eligible" in item for item in result.diagnostics)


def test_correct_role_can_fill_coverage_requirement():
    shift = Shift(
        "D1", "day",
        datetime(2026, 11, 2, 8),
        datetime(2026, 11, 2, 16),
    )
    requirement = CoverageRequirement(
        "W1", "D1", 1, required_role=StaffRole.NURSE
    )

    result = ShiftScheduler().solve(
        [make_staff("N1", StaffRole.NURSE)],
        [Ward("W1", "Ward 1", 1)],
        [shift],
        [requirement],
    )

    assert result.is_feasible
    assert len(result.assignments) == 1
    assert result.assignments[0].staff_id == "N1"