from datetime import datetime, timedelta, timezone

from labvalidation.models import (
    LabResult,
    LabTestDefinition,
    ReferenceRange,
    ResultFlag,
    Unit,
)
from labvalidation.workflow import DeltaRule, LabResultWorkflow


NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def make_setup():
    unit = Unit("mmol/L", "millimoles per litre")
    test = LabTestDefinition("K", "Potassium", unit)
    reference = ReferenceRange(
        test_code="K",
        low=3.5,
        high=5.1,
        unit=unit,
        min_age_days=18 * 365,
    )

    def result(result_id, value, collected_at=NOW, hemolyzed=False):
        return LabResult(
            result_id=result_id,
            patient_id="P-INTEGRATION",
            test=test,
            value=value,
            unit=unit,
            collected_at=collected_at,
            patient_age_days=40 * 365,
            specimen_hemolyzed=hemolyzed,
        )

    return result, reference


def test_integration_numeric_result_with_delta_check():
    result, reference = make_setup()
    previous = result("INT-OLD", "4.0", NOW - timedelta(hours=1))
    current = result("INT-CURRENT", "5.0")

    workflow = LabResultWorkflow(
        [reference],
        delta_rules={"K": DeltaRule(0.5, timedelta(hours=2))},
    )

    outcome = workflow.process(current, previous)

    assert outcome.result_id == "INT-CURRENT"
    assert outcome.flag == ResultFlag.NORMAL
    assert outcome.reference_range is not None
    assert outcome.delta_check is not None
    assert outcome.delta_check.significant_change
    assert outcome.alert is None


def test_integration_critical_result_produces_alert():
    result, reference = make_setup()
    workflow = LabResultWorkflow(
        [reference],
        critical_thresholds={"K": (2.5, 6.5)},
    )

    outcome = workflow.process(result("INT-CRITICAL", "7.0"))

    assert outcome.flag == ResultFlag.CRITICAL_HIGH
    assert outcome.alert is not None
    assert outcome.alert.result_id == "INT-CRITICAL"


def test_integration_hemolyzed_specimen_is_held_without_alert():
    result, reference = make_setup()
    workflow = LabResultWorkflow(
        [reference],
        critical_thresholds={"K": (2.5, 6.5)},
        sensitive_tests={"K"},
    )

    outcome = workflow.process(
        result("INT-HEMOLYZED", "7.0", hemolyzed=True)
    )

    assert outcome.flag == ResultFlag.UNINTERPRETED
    assert outcome.specimen_assessment.requires_recollection_review
    assert outcome.reference_range is None
    assert outcome.alert is None

def test_integration_potassium_6_9_notifies_and_escalates_on_schedule():
    result, reference = make_setup()
    workflow = LabResultWorkflow(
        [reference],
        critical_thresholds={"K": (2.8, 6.2)},
    )

    outcome = workflow.process(result("INT-K-69", "6.9"))

    assert outcome.flag == ResultFlag.CRITICAL_HIGH
    assert outcome.alert is not None
    assert outcome.alert.result_id == "INT-K-69"

    alert = workflow.registry.get_alert(outcome.alert.alert_id)
    assert len(alert.notifications) == 1
    assert alert.notifications[0].recipient_role == "ORDERING_PHYSICIAN"

    at_30_minutes = workflow.escalate_due(NOW + timedelta(minutes=30))
    assert [event.recipient_role for event in at_30_minutes] == [
        "CHARGE_NURSE"
    ]

    at_60_minutes = workflow.escalate_due(NOW + timedelta(minutes=60))
    assert [event.recipient_role for event in at_60_minutes] == [
        "SUPERVISOR"
    ]

    assert workflow.escalate_due(NOW + timedelta(minutes=90)) == ()
