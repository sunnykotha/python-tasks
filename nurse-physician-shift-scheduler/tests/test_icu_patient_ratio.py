from datetime import datetime, timedelta

import pytest

from nurse_scheduler.models import (
    CoverageRequirement,
    Shift,
    Skill,
    Staff,
    StaffRole,
    Ward,
)
from nurse_scheduler.scheduler import ShiftScheduler


@pytest.mark.parametrize(
    ("patient_count", "required_nurses"),
    [(1, 1), (2, 1), (3, 2), (5, 3)],
)
def test_icu_nurse_ratio_rounds_up(patient_count, required_nurses):
    ward = Ward("icu", "ICU Ward", patient_count)
    shift = Shift(
        "night",
        "night",
        datetime(2026, 1, 5, 20),
        datetime(2026, 1, 6, 4),
    )
    staff = [
        Staff(
            id=f"nurse-{index}",
            name=f"Nurse {index}",
            role=StaffRole.NURSE,
            skills=frozenset({Skill("ICU-certified")}),
        )
        for index in range(required_nurses)
    ]
    requirement = CoverageRequirement(
        ward_id=ward.id,
        shift_id=shift.id,
        minimum_staff=0,
        required_role=StaffRole.NURSE,
        skill_patient_ratios={"ICU-certified": 2},
    )

    result = ShiftScheduler().solve(
        staff=staff,
        wards=[ward],
        shifts=[shift],
        requirements=[requirement],
    )

    assert result.is_feasible
    assert len(result.assignments) == required_nurses


@pytest.mark.parametrize(
    ("patient_count", "available_nurses"),
    [(1, 0), (2, 0), (3, 1), (5, 2)],
)
def test_icu_ratio_rejects_insufficient_certified_nurses(
    patient_count, available_nurses
):
    ward = Ward("icu", "ICU Ward", patient_count)
    shift = Shift(
        "night",
        "night",
        datetime(2026, 1, 5, 20),
        datetime(2026, 1, 6, 4),
    )
    staff = [
        Staff(
            id=f"nurse-{index}",
            name=f"Nurse {index}",
            role=StaffRole.NURSE,
            skills=frozenset({Skill("ICU-certified")}),
        )
        for index in range(available_nurses)
    ]
    requirement = CoverageRequirement(
        ward_id=ward.id,
        shift_id=shift.id,
        minimum_staff=0,
        required_role=StaffRole.NURSE,
        skill_patient_ratios={"ICU-certified": 2},
    )

    result = ShiftScheduler().solve(
        staff=staff,
        wards=[ward],
        shifts=[shift],
        requirements=[requirement],
    )

    assert not result.is_feasible
