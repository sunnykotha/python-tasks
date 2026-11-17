from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Patient:
    patient_id: str
    death_date: date | None = None
    disenrollment_date: date | None = None

    def __post_init__(self):
        if not self.patient_id or not self.patient_id.strip():
            raise ValueError("Patient ID must not be empty.")


@dataclass(frozen=True)
class Drug:
    drug_id: str
    drug_class: str

    def __post_init__(self):
        if not self.drug_id or not self.drug_id.strip():
            raise ValueError("Drug ID must not be empty.")
        if not self.drug_class or not self.drug_class.strip():
            raise ValueError("Drug class must not be empty.")


@dataclass(frozen=True)
class FillEvent:
    patient_id: str
    drug_id: str
    fill_date: date
    days_supply: int | None
    quantity: float | None = None
    daily_dose: float | None = None

    def __post_init__(self):
        if not self.patient_id or not self.patient_id.strip():
            raise ValueError("Fill patient ID must not be empty.")
        if not self.drug_id or not self.drug_id.strip():
            raise ValueError("Fill drug ID must not be empty.")
        if not isinstance(self.fill_date, date):
            raise ValueError("Fill date must be a date.")
        if self.days_supply is not None:
            if isinstance(self.days_supply, bool) or not isinstance(self.days_supply, int):
                raise ValueError("Days supply must be an integer or None.")
            if self.days_supply < 0:
                raise ValueError("Days supply must not be negative.")

        if (self.quantity is None) != (self.daily_dose is None):
            raise ValueError("Quantity and daily dose must be supplied together.")

        if self.quantity is not None:
            if self.quantity <= 0 or self.daily_dose <= 0:
                raise ValueError("Quantity and daily dose must be positive.")

    @property
    def effective_days_supply(self) -> int:
        if self.quantity is not None and self.daily_dose is not None:
            return int(self.quantity / self.daily_dose)
        return self.days_supply or 0

    @property
    def has_valid_supply(self) -> bool:
        return self.effective_days_supply > 0


@dataclass(frozen=True)
class Hospitalization:
    patient_id: str
    start_date: date
    end_date: date

    def __post_init__(self):
        if not self.patient_id or not self.patient_id.strip():
            raise ValueError("Hospitalization patient ID must not be empty.")
        if not isinstance(self.start_date, date) or not isinstance(self.end_date, date):
            raise ValueError("Hospitalization dates must be dates.")
        if self.end_date < self.start_date:
            raise ValueError("Hospitalization end date must not precede start date.")

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1


@dataclass(frozen=True)
class MeasurementPeriod:
    start_date: date
    end_date: date

    def __post_init__(self):
        if not isinstance(self.start_date, date) or not isinstance(self.end_date, date):
            raise ValueError("Measurement period boundaries must be dates.")
        if self.end_date < self.start_date:
            raise ValueError("Measurement period end must not precede start.")

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1


@dataclass(frozen=True)
class PDCResult:
    covered_days: int
    period_days: int

    def __post_init__(self):
        if isinstance(self.covered_days, bool) or not isinstance(self.covered_days, int):
            raise ValueError("Covered days must be an integer.")
        if isinstance(self.period_days, bool) or not isinstance(self.period_days, int):
            raise ValueError("Period days must be an integer.")
        if self.period_days <= 0:
            raise ValueError("Period days must be positive.")
        if self.covered_days < 0 or self.covered_days > self.period_days:
            raise ValueError("Covered days must be between zero and period days.")

    @property
    def pdc(self) -> float:
        return self.covered_days / self.period_days

    @property
    def adherent(self) -> bool:
        return self.pdc >= 0.80