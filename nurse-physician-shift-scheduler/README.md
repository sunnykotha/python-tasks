# Nurse and Physician Shift Scheduler

A Python staff-scheduling project using Google OR-Tools CP-SAT to assign qualified nurses and physicians to ward shifts while respecting staffing, availability, qualification, and scheduling constraints.

## Requirements

- Python 3.13 or a compatible Python version
- pip
- Google OR-Tools
- pytest

## Setup

Open PowerShell and navigate to the project:

```powershell
Set-Location "C:\Users\GK\nurse-physician-shift-scheduler"
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run the tests

Run the complete test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Run a specific test module:

```powershell
.\.venv\Scripts\python.exe -m pytest -v tests\test_hard_constraints.py
```

## Scheduling capabilities

### Hard constraints

- Meet minimum staffing requirements for each configured ward and shift.
- Enforce required staff roles, so a physician cannot fill a nurse-only requirement and vice versa.
- Meet required skill and certification counts.
- Respect approved leave and part-time staff fixed weekdays.
- Prevent overlapping assignments for the same staff member.
- Enforce at least 11 hours of rest between shifts.
- Limit staff to at most five shifts in any six consecutive calendar days.
- Enforce weekly working-hour caps, including portions of overnight shifts that fall in each week.
- In emergency mode, permit up to eight additional hours above an individual's configured weekly cap.
- Keep other hard constraints in force during emergency scheduling.

### Skill and patient-ratio coverage

Coverage requirements are configured explicitly using `CoverageRequirement`.

- `minimum_staff` specifies the minimum number of assigned staff.
- `required_role` restricts the role eligible to fill a requirement.
- `required_skill_counts` specifies minimum counts for staff with particular skills.
- `skill_patient_ratios` can derive the required number of qualified staff from `Ward.patient_count`.

For example, `skill_patient_ratios={"ICU-certified": 2}` requires at least one ICU-certified staff member per two patients, rounded up. A ward with five patients therefore requires three staff members with that skill when this ratio is configured.

The skill name must match the name stored in each staff member's `Skill` object.

### Soft constraints and optimization

When a feasible schedule exists, the scheduler considers:

- Fair distribution of night and weekend assignments among staff with the same role.
- Staff shift-type preferences.
- Staff ward preferences.
- Continuity of ward assignments.
- Retention of existing assignments during replanning.

The solver first minimizes the number of assignments needed to meet coverage. When the minimum is proven optimal, it fixes that assignment count and optimizes the soft penalties and roster changes.

### Infeasible schedules and diagnostics

The scheduler returns its solver status, assignments when feasible, and diagnostic messages when a feasible schedule cannot be found.

Diagnostics can identify:
- Insufficient eligible staffing.
- Insufficient qualified staff for a required skill.
- Conflicting groups involving minimum staffing, skill coverage, rest periods, consecutive-shift limits, and weekly-hour limits.

The CP-SAT assumption core identifies a sufficient conflicting subset of the modeled constraint groups. It does not necessarily establish one unique root cause. Leave and fixed-day restrictions are also checked by the scheduler, but are not all represented as separate assumption groups.

### Emergency overtime

Emergency scheduling is enabled explicitly with `emergency=True`.

The weekly limit becomes the staff member's configured `max_weekly_hours` plus eight hours. Emergency mode does not remove the weekly cap entirely, and it does not relax role, skill, approved-leave, rest, or consecutive-shift restrictions.

Use emergency mode only when the situation calls for it.

## Project structure

```text
nurse-physician-shift-scheduler/
|-- nurse_scheduler/
|   |-- __init__.py
|   |-- models.py
|   `-- scheduler.py
|-- tests/
|   |-- test_constraint_diagnostics.py
|   |-- test_emergency_overtime_limit.py
|   |-- test_five_night_example.py
|   |-- test_hard_constraints.py
|   |-- test_icu_patient_ratio.py
|   |-- test_models.py
|   |-- test_optimization.py
|   |-- test_project_setup.py
|   |-- test_role_coverage.py
|   `-- test_scheduler.py
|-- requirements.txt
|-- test_ortools.py
|-- .gitignore
`-- README.md
```

## Verification status

The latest reported full test run completed with **59 passing tests**.

Re-run the complete test suite before publishing changes:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The final requirements audit and verification must be completed before treating the project as finished.