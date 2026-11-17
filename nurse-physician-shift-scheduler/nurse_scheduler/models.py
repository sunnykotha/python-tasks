from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class StaffRole(str, Enum):
    NURSE = "nurse"
    PHYSICIAN = "physician"


@dataclass(frozen=True)
class Skill:
    name: str

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValueError("Skill name cannot be empty.")


@dataclass(frozen=True)
class Staff:
    id: str
    name: str
    role: StaffRole
    skills: frozenset[Skill] = frozenset()
    max_weekly_hours: float = 40
    is_part_time: bool = False
    fixed_days: frozenset[int] = frozenset()
    preferred_shift_types: frozenset[str] = frozenset()
    preferred_wards: frozenset[str] = frozenset()

    def __post_init__(self):
        if not self.id.strip() or not self.name.strip():
            raise ValueError("Staff ID and name cannot be empty.")
        if self.max_weekly_hours <= 0:
            raise ValueError("Maximum weekly hours must be positive.")
        if any(day < 0 or day > 6 for day in self.fixed_days):
            raise ValueError("Fixed days must use weekday numbers 0 through 6.")
        if not isinstance(self.role, StaffRole):
            raise ValueError("Role must be a StaffRole value.")


@dataclass(frozen=True)
class Ward:
    id: str
    name: str
    patient_count: int

    def __post_init__(self):
        if not self.id.strip() or not self.name.strip():
            raise ValueError("Ward ID and name cannot be empty.")
        if self.patient_count < 0:
            raise ValueError("Patient count cannot be negative.")


@dataclass(frozen=True)
class Shift:
    id: str
    shift_type: str
    start: datetime
    end: datetime

    def __post_init__(self):
        if not self.id.strip() or not self.shift_type.strip():
            raise ValueError("Shift ID and type cannot be empty.")
        if self.end <= self.start:
            raise ValueError("Shift end must be after shift start.")

    @property
    def duration_hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600

    @property
    def shift_date(self) -> date:
        return self.start.date()


@dataclass(frozen=True)
class Leave:
    staff_id: str
    start: datetime
    end: datetime
    approved: bool = True

    def __post_init__(self):
        if not self.staff_id.strip():
            raise ValueError("Leave must identify a staff member.")
        if self.end <= self.start:
            raise ValueError("Leave end must be after leave start.")


@dataclass(frozen=True)
class CoverageRequirement:
    ward_id: str
    shift_id: str
    minimum_staff: int
    required_skill_counts: dict[str, int] = field(default_factory=dict)
    required_role: StaffRole | None = None
    skill_patient_ratios: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        if not self.ward_id.strip() or not self.shift_id.strip():
            raise ValueError("Ward ID and shift ID cannot be empty.")
        if self.minimum_staff < 0:
            raise ValueError("Minimum staff cannot be negative.")
        if any(
            not skill.strip() or count < 0
            for skill, count in self.required_skill_counts.items()
        ):
            raise ValueError("Required skill names and counts must be valid.")
        if self.required_role is not None and not isinstance(
            self.required_role, StaffRole
        ):
            raise ValueError("Required role must be a StaffRole value.")
        if any(
            not skill.strip() or ratio <= 0
            for skill, ratio in self.skill_patient_ratios.items()
        ):
            raise ValueError(
                "Skill patient ratios require valid skill names and positive ratios."
            )


@dataclass(frozen=True)
class Assignment:
    staff_id: str
    ward_id: str
    shift_id: str

    def __post_init__(self):
        if not self.staff_id.strip():
            raise ValueError("Assignment must identify a staff member.")
        if not self.ward_id.strip() or not self.shift_id.strip():
            raise ValueError("Assignment must identify a ward and shift.")


@dataclass(frozen=True)
class PenaltyScore:
    night_shift_penalty: int = 0
    weekend_penalty: int = 0
    preference_penalty: int = 0
    ward_continuity_penalty: int = 0

    def __post_init__(self):
        if any(
            value < 0
            for value in (
                self.night_shift_penalty,
                self.weekend_penalty,
                self.preference_penalty,
                self.ward_continuity_penalty,
            )
        ):
            raise ValueError("Penalty values cannot be negative.")

    @property
    def total(self) -> int:
        return (
            self.night_shift_penalty
            + self.weekend_penalty
            + self.preference_penalty
            + self.ward_continuity_penalty
        )
