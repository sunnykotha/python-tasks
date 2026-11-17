from dataclasses import dataclass
from datetime import datetime, time, timedelta
from itertools import combinations

from ortools.sat.python import cp_model

from nurse_scheduler.models import (
    Assignment,
    CoverageRequirement,
    Leave,
    Shift,
    Staff,
    Ward,
)


MINIMUM_REST_HOURS = 11
MAX_CONSECUTIVE_SHIFTS = 5
MAX_EMERGENCY_OVERTIME_HOURS = 8


@dataclass(frozen=True)
class ScheduleResult:
    status: str
    assignments: tuple[Assignment, ...]
    penalty_score: int = 0
    diagnostics: tuple[str, ...] = ()

    @property
    def is_feasible(self) -> bool:
        return self.status in ("OPTIMAL", "FEASIBLE")


class ShiftScheduler:
    def solve(
        self,
        staff: list[Staff],
        wards: list[Ward],
        shifts: list[Shift],
        requirements: list[CoverageRequirement],
        leaves: list[Leave] | None = None,
        existing_assignments: list[Assignment] | None = None,
        emergency: bool = False,
    ) -> ScheduleResult:
        leaves = leaves or []
        existing_assignments = existing_assignments or []

        staff_by_id = {person.id: person for person in staff}
        wards_by_id = {ward.id: ward for ward in wards}
        def required_skill_counts_for(requirement):
            counts = dict(requirement.required_skill_counts)
            ward = wards_by_id[requirement.ward_id]

            for skill_name, patients_per_staff in (
                requirement.skill_patient_ratios.items()
            ):
                required_count = (
                    ward.patient_count + patients_per_staff - 1
                ) // patients_per_staff
                counts[skill_name] = max(
                    counts.get(skill_name, 0), required_count
                )

            return counts
        shifts_by_id = {shift.id: shift for shift in shifts}

        if len(staff_by_id) != len(staff):
            raise ValueError("Staff IDs must be unique.")
        if len(wards_by_id) != len(wards):
            raise ValueError("Ward IDs must be unique.")
        if len(shifts_by_id) != len(shifts):
            raise ValueError("Shift IDs must be unique.")

        for requirement in requirements:
            if requirement.ward_id not in wards_by_id:
                raise ValueError(f"Unknown ward ID: {requirement.ward_id}")
            if requirement.shift_id not in shifts_by_id:
                raise ValueError(f"Unknown shift ID: {requirement.shift_id}")

        model = cp_model.CpModel()
        diagnostic_assumptions = {
            "staffing": model.NewBoolVar("diagnose_staffing"),
            "skills": model.NewBoolVar("diagnose_skills"),
            "rest": model.NewBoolVar("diagnose_rest"),
            "consecutive": model.NewBoolVar("diagnose_consecutive_shifts"),
            "weekly_hours": model.NewBoolVar("diagnose_weekly_hours"),
        }
        model.AddAssumptions(list(diagnostic_assumptions.values()))
        variables = {}

        # Hard rule: exclude staff on approved leave and disallowed
        # part-time days.
        for person in staff:
            for index, requirement in enumerate(requirements):
                shift = shifts_by_id[requirement.shift_id]

                on_approved_leave = any(
                    leave.approved
                    and leave.staff_id == person.id
                    and leave.start < shift.end
                    and shift.start < leave.end
                    for leave in leaves
                )

                violates_fixed_day = (
                    person.is_part_time
                    and bool(person.fixed_days)
                    and shift.shift_date.weekday() not in person.fixed_days
                )

                violates_role = (
                    requirement.required_role is not None
                    and person.role != requirement.required_role
                )

                if (
                    not on_approved_leave
                    and not violates_fixed_day
                    and not violates_role
                ):
                    variables[(person.id, index)] = model.NewBoolVar(
                        f"assign_{person.id}_{index}"
                    )

        # Hard rule: minimum staffing and required skill counts.
        for index, requirement in enumerate(requirements):
            eligible = [
                variables[(person.id, index)]
                for person in staff
                if (person.id, index) in variables
            ]
            model.Add(sum(eligible) >= requirement.minimum_staff).OnlyEnforceIf(diagnostic_assumptions["staffing"])

            for skill_name, required_count in (
                required_skill_counts_for(requirement).items()
            ):
                qualified = [
                    variables[(person.id, index)]
                    for person in staff
                    if (person.id, index) in variables
                    and any(
                        skill.name == skill_name
                        for skill in person.skills
                    )
                ]
                model.Add(sum(qualified) >= required_count).OnlyEnforceIf(diagnostic_assumptions["skills"])

        # Hard rule: no overlapping shifts and at least 11 hours' rest.
        minimum_rest = timedelta(hours=MINIMUM_REST_HOURS)

        for person in staff:
            for first_index, second_index in combinations(
                range(len(requirements)), 2
            ):
                first_shift = shifts_by_id[
                    requirements[first_index].shift_id
                ]
                second_shift = shifts_by_id[
                    requirements[second_index].shift_id
                ]

                first_key = (person.id, first_index)
                second_key = (person.id, second_index)

                if (
                    first_key not in variables
                    or second_key not in variables
                ):
                    continue

                overlaps = (
                    first_shift.start < second_shift.end
                    and second_shift.start < first_shift.end
                )

                violates_rest = (
                    not overlaps
                    and (
                        (
                            first_shift.end <= second_shift.start
                            and second_shift.start - first_shift.end
                            < minimum_rest
                        )
                        or (
                            second_shift.end <= first_shift.start
                            and first_shift.start - second_shift.end
                            < minimum_rest
                        )
                    )
                )

                if overlaps or violates_rest:
                    model.Add(
                        variables[first_key] + variables[second_key] <= 1
                    ).OnlyEnforceIf(diagnostic_assumptions["rest"])

        # Hard rule: no more than five shifts in any six consecutive
        # calendar days.
        if shifts_by_id:
            first_date = min(s.shift_date for s in shifts_by_id.values())
            last_date = max(s.shift_date for s in shifts_by_id.values())
            current_date = first_date

            while current_date <= last_date - timedelta(
                days=MAX_CONSECUTIVE_SHIFTS
            ):
                window_end = current_date + timedelta(
                    days=MAX_CONSECUTIVE_SHIFTS + 1
                )

                for person in staff:
                    window_variables = [
                        variables[(person.id, index)]
                        for index, requirement in enumerate(requirements)
                        if (person.id, index) in variables
                        and current_date
                        <= shifts_by_id[requirement.shift_id].shift_date
                        < window_end
                    ]

                    if window_variables:
                        model.Add(
                            sum(window_variables)
                            <= MAX_CONSECUTIVE_SHIFTS
                        ).OnlyEnforceIf(diagnostic_assumptions["consecutive"])

                current_date += timedelta(days=1)

        # Hard rule: weekly hour caps, including overnight shift portions.
        if shifts_by_id:
            earliest = min(s.start for s in shifts_by_id.values())
            latest = max(s.end for s in shifts_by_id.values())
            week_start = earliest.date() - timedelta(days=earliest.weekday())
            final_week = latest.date() - timedelta(days=latest.weekday())

            while week_start <= final_week:
                week_begin = datetime.combine(week_start, time.min)
                week_end = week_begin + timedelta(days=7)

                for person in staff:
                    hour_terms = []

                    for index, requirement in enumerate(requirements):
                        key = (person.id, index)
                        if key not in variables:
                            continue

                        shift = shifts_by_id[requirement.shift_id]
                        overlap_start = max(shift.start, week_begin)
                        overlap_end = min(shift.end, week_end)
                        hours = (
                            overlap_end - overlap_start
                        ).total_seconds() / 3600

                        if hours > 0:
                            hour_terms.append(
                                round(hours * 4) * variables[key]
                            )

                    if hour_terms:
                        weekly_limit = person.max_weekly_hours
                        if emergency:
                            weekly_limit += MAX_EMERGENCY_OVERTIME_HOURS
                        model.Add(
                            sum(hour_terms) <= round(weekly_limit * 4)
                        ).OnlyEnforceIf(diagnostic_assumptions["weekly_hours"])

                week_start += timedelta(days=7)

        # Soft rules: distribute night and weekend shifts fairly.
        penalty_terms = []

        categories = (
            ("night", lambda s: s.shift_type.lower() == "night"),
            ("weekend", lambda s: s.shift_date.weekday() >= 5),
        )

        for category, predicate in categories:
            roles = sorted(
                {person.role.value for person in staff}
            )

            for role_value in roles:
                role_staff = [
                    person for person in staff
                    if person.role.value == role_value
                ]
                counts = []

                for person in role_staff:
                    count = model.NewIntVar(
                        0,
                        len(requirements),
                        f"{category}_{role_value}_count_{person.id}",
                    )
                    matching = [
                        variables[(person.id, index)]
                        for index, requirement in enumerate(requirements)
                        if (person.id, index) in variables
                        and predicate(shifts_by_id[requirement.shift_id])
                    ]
                    model.Add(count == sum(matching))
                    counts.append(count)

                for left, right in combinations(counts, 2):
                    difference = model.NewIntVar(
                        0,
                        len(requirements),
                        f"{category}_{role_value}_difference_{len(penalty_terms)}",
                    )
                    model.AddAbsEquality(difference, left - right)
                    penalty_terms.append(difference)
        # Soft rules: staff shift-type and ward preferences.
        for (staff_id, index), variable in variables.items():
            person = staff_by_id[staff_id]
            requirement = requirements[index]
            shift = shifts_by_id[requirement.shift_id]

            if (
                person.preferred_shift_types
                and shift.shift_type not in person.preferred_shift_types
            ):
                penalty_terms.append(variable)

            if (
                person.preferred_wards
                and requirement.ward_id not in person.preferred_wards
            ):
                penalty_terms.append(variable)

        # Soft rule: ward continuity from the existing roster.
        prior_wards = {}
        for assignment in existing_assignments:
            prior_wards.setdefault(assignment.staff_id, set()).add(
                assignment.ward_id
            )

        # Penalize dropping an existing assignment when its requirement
        # still exists in the roster being planned.
        change_terms = []
        for assignment in existing_assignments:
            matching_indices = [
                index
                for index, requirement in enumerate(requirements)
                if requirement.ward_id == assignment.ward_id
                and requirement.shift_id == assignment.shift_id
            ]

            for index in matching_indices:
                variable = variables.get((assignment.staff_id, index))
                if variable is None:
                    change_terms.append(100)
                else:
                    change_terms.append(100 * (1 - variable))

        continuity_terms = []
        for (staff_id, index), variable in variables.items():
            previous = prior_wards.get(staff_id, set())
            ward_id = requirements[index].ward_id

            if previous and ward_id not in previous:
                continuity_terms.append(10 * variable)

        # Stage 1: minimize assignments while satisfying all hard rules.
        assignment_count = sum(variables.values())
        model.Minimize(assignment_count)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10
        solver.parameters.num_search_workers = 1

        status_code = solver.Solve(model)
        status = solver.StatusName(status_code)

        if status not in ("OPTIMAL", "FEASIBLE"):
            diagnostics = []

            if status == "INFEASIBLE":
                for requirement in requirements:
                    eligible_staff = [
                        person
                        for person in staff
                        if not any(
                            leave.approved
                            and leave.staff_id == person.id
                            and leave.start < shifts_by_id[requirement.shift_id].end
                            and shifts_by_id[requirement.shift_id].start < leave.end
                            for leave in leaves
                        )
                        and not (
                            person.is_part_time
                            and bool(person.fixed_days)
                            and shifts_by_id[requirement.shift_id].shift_date.weekday()
                            not in person.fixed_days
                        )
                        and (
                            requirement.required_role is None
                            or person.role == requirement.required_role
                        )
                    ]

                    if len(eligible_staff) < requirement.minimum_staff:
                        diagnostics.append(
                            f"Ward '{requirement.ward_id}', shift "
                            f"'{requirement.shift_id}' requires "
                            f"{requirement.minimum_staff} staff, but only "
                            f"{len(eligible_staff)} are eligible after leave "
                            "and fixed-day restrictions."
                        )

                    for skill_name, required_count in (
                        required_skill_counts_for(requirement).items()
                    ):
                        qualified_count = sum(
                            any(skill.name == skill_name for skill in person.skills)
                            for person in eligible_staff
                        )
                        if qualified_count < required_count:
                            diagnostics.append(
                                f"Ward '{requirement.ward_id}', shift "
                                f"'{requirement.shift_id}' requires "
                                f"{required_count} staff with skill "
                                f"'{skill_name}', but only {qualified_count} "
                                "eligible staff have that skill."
                            )

                core_indices = {
                    abs(index)
                    for index in solver.SufficientAssumptionsForInfeasibility()
                }
                group_labels = {
                    diagnostic_assumptions["staffing"].Index():
                        "Minimum staffing coverage",
                    diagnostic_assumptions["skills"].Index():
                        "Required skill coverage",
                    diagnostic_assumptions["rest"].Index():
                        "Shift overlap or minimum 11-hour rest",
                    diagnostic_assumptions["consecutive"].Index():
                        "Maximum of five shifts in six consecutive days",
                    diagnostic_assumptions["weekly_hours"].Index():
                        "Weekly working-hour cap",
                }
                for index, label in group_labels.items():
                    if index in core_indices:
                        diagnostics.append(
                            f"CP-SAT identified a conflicting hard-rule group: {label}."
                        )
                if not diagnostics:
                    diagnostics.append(
                        "No feasible schedule was found under the configured "
                        "hard constraints. The basic per-shift staffing checks "
                        "did not identify a single shortage. Possible interacting "
                        "constraints include minimum rest between shifts, the "
                        "maximum of five consecutive shifts, weekly hour caps, "
                        "approved leave, part-time fixed days, role restrictions, "
                        "and required skills. This message identifies possible "
                        "conflicts, not a proven single cause."
                    )
            else:
                diagnostics.append(
                    f"Solver could not confirm a feasible schedule: {status}."
                )

            return ScheduleResult(
                status=status,
                assignments=(),
                diagnostics=tuple(diagnostics),
            )

        # Stage 2: when the minimum assignment count is proven, optimize
        # fairness, preferences, and continuity.
        if status == "OPTIMAL":
            minimum_assignments = round(solver.ObjectiveValue())
            model.Add(assignment_count == minimum_assignments)
            model.Minimize(sum(change_terms) + sum(penalty_terms) + sum(continuity_terms))

            status_code = solver.Solve(model)
            status = solver.StatusName(status_code)

        if status not in ("OPTIMAL", "FEASIBLE"):
            diagnostics = []

            if status == "INFEASIBLE":
                for requirement in requirements:
                    eligible_staff = [
                        person
                        for person in staff
                        if not any(
                            leave.approved
                            and leave.staff_id == person.id
                            and leave.start < shifts_by_id[requirement.shift_id].end
                            and shifts_by_id[requirement.shift_id].start < leave.end
                            for leave in leaves
                        )
                        and not (
                            person.is_part_time
                            and bool(person.fixed_days)
                            and shifts_by_id[requirement.shift_id].shift_date.weekday()
                            not in person.fixed_days
                        )
                        and (
                            requirement.required_role is None
                            or person.role == requirement.required_role
                        )
                    ]

                    if len(eligible_staff) < requirement.minimum_staff:
                        diagnostics.append(
                            f"Ward '{requirement.ward_id}', shift "
                            f"'{requirement.shift_id}' requires "
                            f"{requirement.minimum_staff} staff, but only "
                            f"{len(eligible_staff)} are eligible after leave "
                            "and fixed-day restrictions."
                        )

                    for skill_name, required_count in (
                        required_skill_counts_for(requirement).items()
                    ):
                        qualified_count = sum(
                            any(skill.name == skill_name for skill in person.skills)
                            for person in eligible_staff
                        )
                        if qualified_count < required_count:
                            diagnostics.append(
                                f"Ward '{requirement.ward_id}', shift "
                                f"'{requirement.shift_id}' requires "
                                f"{required_count} staff with skill "
                                f"'{skill_name}', but only {qualified_count} "
                                "eligible staff have that skill."
                            )

                core_indices = {
                    abs(index)
                    for index in solver.SufficientAssumptionsForInfeasibility()
                }
                group_labels = {
                    diagnostic_assumptions["staffing"].Index():
                        "Minimum staffing coverage",
                    diagnostic_assumptions["skills"].Index():
                        "Required skill coverage",
                    diagnostic_assumptions["rest"].Index():
                        "Shift overlap or minimum 11-hour rest",
                    diagnostic_assumptions["consecutive"].Index():
                        "Maximum of five shifts in six consecutive days",
                    diagnostic_assumptions["weekly_hours"].Index():
                        "Weekly working-hour cap",
                }
                for index, label in group_labels.items():
                    if index in core_indices:
                        diagnostics.append(
                            f"CP-SAT identified a conflicting hard-rule group: {label}."
                        )
                if not diagnostics:
                    diagnostics.append(
                        "No feasible schedule was found under the configured "
                        "hard constraints. The basic per-shift staffing checks "
                        "did not identify a single shortage. Possible interacting "
                        "constraints include minimum rest between shifts, the "
                        "maximum of five consecutive shifts, weekly hour caps, "
                        "approved leave, part-time fixed days, role restrictions, "
                        "and required skills. This message identifies possible "
                        "conflicts, not a proven single cause."
                    )
            else:
                diagnostics.append(
                    f"Solver could not confirm a feasible schedule: {status}."
                )

            return ScheduleResult(
                status=status,
                assignments=(),
                diagnostics=tuple(diagnostics),
            )

        assignments = tuple(
            Assignment(
                staff_id=staff_id,
                ward_id=requirements[index].ward_id,
                shift_id=requirements[index].shift_id,
            )
            for (staff_id, index), variable in variables.items()
            if solver.Value(variable)
        )

        return ScheduleResult(
            status=status,
            assignments=assignments,
            penalty_score=round(solver.ObjectiveValue()),
        )