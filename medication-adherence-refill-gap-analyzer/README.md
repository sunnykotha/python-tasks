# Medication Adherence and Refill-Gap Analyzer

Python application for calculating medication adherence using Proportion of Days Covered (PDC).

## Features
- Early-refill carry-forward
- No double-counting of covered days
- 80% PDC adherence threshold
- Hospitalization-related supply extension
- Dose-based supply duration
- Class-level adherence across drugs
- Death and disenrollment period truncation

## Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run Tests
```powershell
$env:PYTHONPATH = Join-Path (Get-Location) "src"
& ".\.venv\Scripts\python.exe" -m pytest -v
```

## Run Example
```powershell
& ".\.venv\Scripts\python.exe" ".\examples\run_example.py"
```

## PDC Formula
PDC = covered days / measurement-period days. A patient is adherent at PDC >= 0.80.
