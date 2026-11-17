"""Tests for the integrated claims analysis workflow."""

from claims_fraud import analyzer


def test_analyze_claims_returns_empty_list_when_no_flags(monkeypatch):
    monkeypatch.setattr(analyzer, "detect_duplicate_billing", lambda claims: [])
    monkeypatch.setattr(
        analyzer, "detect_upcoding", lambda *args: []
    )
    monkeypatch.setattr(
        analyzer, "detect_unbundling", lambda *args: []
    )
    monkeypatch.setattr(
        analyzer, "detect_impossible_schedules", lambda *args: []
    )
    monkeypatch.setattr(
        analyzer, "detect_post_death_services", lambda *args: []
    )
    monkeypatch.setattr(
        analyzer, "detect_statistical_anomalies", lambda *args: []
    )

    result = analyzer.analyze_claims(
        claims=[],
        providers=[],
        patients=[],
        procedure_time_estimates=[],
        visit_code_levels={},
        comprehensive_code_components={},
    )

    assert result == []


def test_analyze_claims_runs_every_detector(monkeypatch):
    calls = []

    def detector(name):
        def run(*args):
            calls.append(name)
            return []
        return run

    monkeypatch.setattr(
        analyzer, "detect_duplicate_billing", detector("duplicate")
    )
    monkeypatch.setattr(
        analyzer, "detect_upcoding", detector("upcoding")
    )
    monkeypatch.setattr(
        analyzer, "detect_unbundling", detector("unbundling")
    )
    monkeypatch.setattr(
        analyzer, "detect_impossible_schedules", detector("schedule")
    )
    monkeypatch.setattr(
        analyzer, "detect_post_death_services", detector("post_death")
    )
    monkeypatch.setattr(
        analyzer, "detect_statistical_anomalies", detector("statistical")
    )
    monkeypatch.setattr(
        analyzer, "build_case_files", lambda flags: []
    )

    result = analyzer.analyze_claims(
        claims=[],
        providers=[],
        patients=[],
        procedure_time_estimates=[],
        visit_code_levels={},
        comprehensive_code_components={},
    )

    assert calls == [
        "duplicate",
        "upcoding",
        "unbundling",
        "schedule",
        "post_death",
        "statistical",
    ]
    assert result == []
