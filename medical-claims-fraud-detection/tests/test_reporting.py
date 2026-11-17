"""Tests for investigator report formatting."""

import json
from types import SimpleNamespace
from datetime import date

from claims_fraud.reporting import build_investigator_report


def make_flag():
    return SimpleNamespace(
        reason_code="DUPLICATE_BILLING",
        description="Repeated billing for the same service.",
        severity="high",
        score=0.9,
        claim_line_ids=("LINE-1", "LINE-2"),
        evidence={
            "provider_id": "PROVIDER-1",
            "service_date": date(2026, 10, 1),
        },
    )


def make_case():
    flag = make_flag()
    return SimpleNamespace(
        id="CASE-PROVIDER-1",
        provider_id="PROVIDER-1",
        flags=(flag,),
        claim_line_ids=("LINE-1", "LINE-2"),
        evidence={
            "provider_id": "PROVIDER-1",
            "flag_count": 1,
            "reason_codes": ("DUPLICATE_BILLING",),
            "highest_severity": "high",
            "highest_flag_score": 0.9,
        },
    )


def test_report_includes_case_summary():
    report = build_investigator_report([make_case()])

    assert report["total_cases"] == 1
    assert report["cases"][0]["case_id"] == "CASE-PROVIDER-1"
    assert report["cases"][0]["provider_id"] == "PROVIDER-1"
    assert report["cases"][0]["severity"] == "high"
    assert report["cases"][0]["score"] == 0.9


def test_report_includes_reason_codes_and_claim_lines():
    report = build_investigator_report([make_case()])
    case = report["cases"][0]

    assert case["reason_codes"] == ["DUPLICATE_BILLING"]
    assert case["claim_line_ids"] == ["LINE-1", "LINE-2"]


def test_report_preserves_flag_details_and_evidence():
    report = build_investigator_report([make_case()])
    flag = report["cases"][0]["flags"][0]

    assert flag["reason_code"] == "DUPLICATE_BILLING"
    assert flag["description"] == "Repeated billing for the same service."
    assert flag["severity"] == "high"
    assert flag["score"] == 0.9
    assert flag["evidence"]["provider_id"] == "PROVIDER-1"


def test_report_converts_dates_to_iso_strings():
    report = build_investigator_report([make_case()])

    assert (
        report["cases"][0]["flags"][0]["evidence"]["service_date"]
        == "2026-10-01"
    )


def test_report_is_json_serializable():
    report = build_investigator_report([make_case()])

    serialized = json.dumps(report)
    restored = json.loads(serialized)

    assert restored["total_cases"] == 1
    assert restored["cases"][0]["case_id"] == "CASE-PROVIDER-1"


def test_empty_report_has_no_cases():
    assert build_investigator_report([]) == {
        "total_cases": 0,
        "cases": [],
    }


def test_report_preserves_case_order():
    first = make_case()
    second = SimpleNamespace(
        id="CASE-PROVIDER-2",
        provider_id="PROVIDER-2",
        flags=(make_flag(),),
        claim_line_ids=("LINE-3",),
        evidence={
            "provider_id": "PROVIDER-2",
            "flag_count": 1,
            "reason_codes": ("DUPLICATE_BILLING",),
            "highest_severity": "critical",
            "highest_flag_score": 1.0,
        },
    )

    report = build_investigator_report([second, first])

    assert [case["case_id"] for case in report["cases"]] == [
        "CASE-PROVIDER-2",
        "CASE-PROVIDER-1",
    ]
