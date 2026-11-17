"""Format ranked case files as JSON-compatible investigator reports."""

from datetime import date, datetime

from claims_fraud.models import CaseFile


def _json_safe(value):
    """Convert common Python containers and dates into JSON-compatible values."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def build_investigator_report(case_files: list[CaseFile]) -> dict:
    """Format ranked cases with their flags and supporting evidence."""
    cases = []

    for case in case_files:
        cases.append({
            "case_id": case.id,
            "provider_id": case.provider_id,
            "severity": case.evidence["highest_severity"],
            "score": case.evidence["highest_flag_score"],
            "reason_codes": _json_safe(case.evidence["reason_codes"]),
            "claim_line_ids": _json_safe(case.claim_line_ids),
            "evidence": _json_safe(case.evidence),
            "flags": [
                {
                    "reason_code": flag.reason_code,
                    "description": flag.description,
                    "severity": flag.severity,
                    "score": flag.score,
                    "claim_line_ids": _json_safe(flag.claim_line_ids),
                    "evidence": _json_safe(flag.evidence),
                }
                for flag in case.flags
            ],
        })

    return {
        "total_cases": len(cases),
        "cases": cases,
    }
