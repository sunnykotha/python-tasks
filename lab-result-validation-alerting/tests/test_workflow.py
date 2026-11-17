from datetime import datetime, timedelta, timezone
from dataclasses import replace
from decimal import Decimal

import pytest

from labvalidation.models import AlertStatus, LabResult, LabTestDefinition, ReferenceRange, ResultFlag, Unit
from labvalidation.workflow import DeltaRule, LabResultWorkflow

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def setup():
    unit = Unit("mmol/L", "millimoles per litre")
    test = LabTestDefinition("K", "Potassium", unit)

    def result(result_id, value, hemolyzed=False, collected_at=NOW, result_unit=None):
        return LabResult(
            result_id=result_id,
            patient_id="P-1",
            test=test,
            value=value,
            unit=result_unit or unit,
            collected_at=collected_at,
            patient_age_days=40 * 365,
            specimen_hemolyzed=hemolyzed,
        )

    reference = ReferenceRange(
        test_code="K", low=3.5, high=5.1, unit=unit, min_age_days=18 * 365
    )
    return result, reference, unit


def test_numeric_normal_result_runs_end_to_end(setup):
    result, reference, unit = setup
    outcome = LabResultWorkflow([reference]).process(result("R1", "4.2"))
    assert outcome.flag == ResultFlag.NORMAL
    assert outcome.reference_range == reference
    assert outcome.alert is None
    assert outcome.parsed_result.numeric_value == Decimal("4.2")


def test_critical_high_creates_alert(setup):
    result, reference, unit = setup
    workflow = LabResultWorkflow([reference], critical_thresholds={"K": (2.5, 6.5)})
    outcome = workflow.process(result("R2", "7.0"))
    assert outcome.flag == ResultFlag.CRITICAL_HIGH
    assert outcome.alert is not None
    assert outcome.alert.result_id == "R2"


def test_critical_low_creates_alert(setup):
    result, reference, unit = setup
    workflow = LabResultWorkflow([reference], critical_thresholds={"K": (2.5, 6.5)})
    outcome = workflow.process(result("R3", "2.0"))
    assert outcome.flag == ResultFlag.CRITICAL_LOW
    assert outcome.alert is not None


def test_hemolyzed_potassium_is_held(setup):
    result, reference, unit = setup
    outcome = LabResultWorkflow([reference], sensitive_tests={"K"}).process(
        result("R4", "8.0", hemolyzed=True)
    )
    assert outcome.flag == ResultFlag.UNINTERPRETED
    assert outcome.reference_range is None
    assert outcome.alert is None
    assert outcome.specimen_assessment.requires_recollection_review


@pytest.mark.parametrize("value", ["positive", "<2.0"])
def test_non_numeric_results_are_not_misclassified(setup, value):
    result, reference, unit = setup
    outcome = LabResultWorkflow([reference]).process(result("R5", value))
    assert outcome.flag == ResultFlag.UNINTERPRETED
    assert outcome.alert is None


def test_unit_mismatch_is_not_interpreted(setup):
    result, reference, unit = setup
    different_unit = Unit("mg/dL", "milligrams per decilitre")
    outcome = LabResultWorkflow([reference]).process(
        result("R6", "4.2", result_unit=different_unit)
    )
    assert outcome.flag == ResultFlag.UNINTERPRETED
    assert "units differ" in outcome.reason


def test_delta_rule_is_integrated(setup):
    result, reference, unit = setup
    previous = result("R7-old", "4.0", collected_at=NOW - timedelta(hours=1))
    current = result("R7", "5.0")
    workflow = LabResultWorkflow(
        [reference],
        delta_rules={"K": DeltaRule(0.5, timedelta(hours=2))},
    )
    outcome = workflow.process(current, previous)
    assert outcome.flag == ResultFlag.NORMAL
    assert outcome.delta_check is not None
    assert outcome.delta_check.significant_change


def test_delta_error_is_reported(setup):
    result, reference, unit = setup
    previous = result("R8-old", "not-a-number", collected_at=NOW - timedelta(hours=1))
    current = result("R8", "4.0")
    workflow = LabResultWorkflow(
        [reference],
        delta_rules={"K": DeltaRule(0.5, timedelta(hours=2))},
    )
    outcome = workflow.process(current, previous)
    assert outcome.flag == ResultFlag.UNINTERPRETED
    assert "Delta check could not be completed" in outcome.reason


def test_amended_normal_result_supersedes_prior_critical_alert(setup):
    result, reference, unit = setup
    workflow = LabResultWorkflow(
        [reference], critical_thresholds={"K": (2.5, 6.5)}
    )
    original = workflow.process(result("R-AMEND", "7.0"))
    assert original.alert is not None
    original_alert_id = original.alert.alert_id

    amended_result = replace(result("R-AMEND", "4.2"), amended=True)
    amended = workflow.process(amended_result)

    assert amended.flag == ResultFlag.NORMAL
    assert amended.alert is None
    historical_alert = workflow.registry.get_alert(original_alert_id)
    assert historical_alert is not None
    assert historical_alert.status == AlertStatus.SUPERSEDED
    assert historical_alert.notifications


def test_qualitative_result_uses_explicit_test_rule(setup):
    result, reference, unit = setup
    workflow = LabResultWorkflow(
        [reference],
        qualitative_rules={"K": {"POSITIVE": ResultFlag.HIGH}},
    )

    outcome = workflow.process(result("R-QUAL", "positive"))

    assert outcome.flag == ResultFlag.HIGH
    assert outcome.alert is None


def test_comparator_interpretation_requires_explicit_opt_in(setup):
    result, reference, unit = setup
    workflow = LabResultWorkflow(
        [reference],
        critical_thresholds={"K": (2.5, 6.5)},
        interpret_comparators=True,
    )

    outcome = workflow.process(result("R-COMP", "<2.0"))

    assert outcome.flag == ResultFlag.CRITICAL_LOW
    assert outcome.alert is not None

def test_superseded_critical_alert_does_not_escalate(setup):
    from dataclasses import replace
    from labvalidation.models import AlertStatus

    result, reference, _ = setup
    workflow = LabResultWorkflow(
        [reference],
        critical_thresholds={"K": (2.5, 6.5)},
    )

    original = result("R-ESCALATION", "7.0")
    original_outcome = workflow.process(original)
    assert original_outcome.alert is not None
    old_alert_id = original_outcome.alert.alert_id

    amended = replace(result("R-ESCALATION", "4.2"), amended=True)
    amended_outcome = workflow.process(amended)
    assert amended_outcome.flag == ResultFlag.NORMAL
    assert amended_outcome.alert is None

    assert workflow.escalate_due(NOW + timedelta(hours=2)) == ()
    assert workflow.registry.get_alert(old_alert_id).status == AlertStatus.SUPERSEDED

def test_amended_uninterpretable_result_preserves_prior_critical_alert(setup):
    result, reference, unit = setup
    workflow = LabResultWorkflow(
        [reference],
        critical_thresholds={"K": (2.5, 6.5)},
        sensitive_tests={"K"},
    )

    original = workflow.process(result("R-AMEND-UNSAFE", "7.0"))
    assert original.alert is not None
    old_alert_id = original.alert.alert_id

    hemolyzed_amendment = replace(
        result("R-AMEND-UNSAFE", "7.0", hemolyzed=True),
        amended=True,
    )
    amended = workflow.process(hemolyzed_amendment)

    assert amended.flag == ResultFlag.UNINTERPRETED
    historical_alert = workflow.registry.get_alert(old_alert_id)
    assert historical_alert is not None
    assert historical_alert.status == AlertStatus.OPEN
    assert historical_alert.notifications

def test_comparator_result_does_not_run_delta_check(setup):
    result, reference, unit = setup
    previous = result(
        "R-COMP-DELTA-OLD", "4.0",
        collected_at=NOW - timedelta(hours=1),
    )
    current = result("R-COMP-DELTA", "<7.0")
    workflow = LabResultWorkflow(
        [reference],
        delta_rules={"K": DeltaRule(0.5, timedelta(hours=2))},
        interpret_comparators=True,
    )

    outcome = workflow.process(current, previous)

    assert outcome.delta_check is None
