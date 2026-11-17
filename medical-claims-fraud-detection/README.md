# Medical Claims Fraud and Anomaly Detection

A Python project that detects suspicious medical billing patterns and generates ranked investigator case files with reason-coded flags and supporting evidence.

## Detection Rules

- Duplicate billing
- Upcoding compared with specialty peers
- Unbundling of procedure components
- Impossible schedules and overlapping services at different locations
- Services billed after a patient's recorded date of death
- Statistical anomaly detection using Isolation Forest

Corrected and reversed claims are excluded from applicable detection checks.

## Requirements

- Python 3.10 or later
- Dependencies in requirements.txt

## Setup

Create a virtual environment and install dependencies:

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt

## Run Tests

    .\.venv\Scripts\python.exe -m pytest -v

## Project Structure

- src/claims_fraud/ — detection and reporting modules
- tests/ — automated tests
- data/ — input data directory
- reports/ — report output directory
- pyproject.toml — project configuration
- requirements.txt — Python dependencies

## Investigator Reports

The analyzer combines rule-based and statistical detection results into ranked case files. Reports contain severity, scores, reason codes, claim-line identifiers, and supporting evidence.

## Validation Note

The automated test suite covers implemented rules and selected edge cases. A labeled dataset is still needed to measure real-world false-positive rates and calibrate thresholds.

An anomaly flag indicates a potential issue for investigation; it is not, by itself, proof of fraud.
