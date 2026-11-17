from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Mapping

from labvalidation.alert_escalation import AlertEscalationScheduler, CriticalAlertEscalator, EscalationPolicy
from labvalidation.critical_alerts import (
    CriticalAlertRecord, CriticalAlertRegistry, NotificationStatus
)
from labvalidation.delta_check import DeltaCheck, DeltaCheckError, check_delta
from labvalidation.email_notifications import deliver_notification
from labvalidation.models import LabResult, ReferenceRange, ResultFlag
from labvalidation.reference_ranges import ReferenceRangeError, select_reference_range
from labvalidation.result_interpreter import InterpretationError, interpret_result
from labvalidation.result_parser import ParsedResult, ResultParseError, parse_result
from labvalidation.specimen_quality import assess_specimen
from labvalidation.unit_conversion import UnitConversionError, normalize_value


DEFAULT_CRITICAL_THRESHOLDS = {
    "K": (2.8, 6.2),
    "POTASSIUM": (2.8, 6.2),
}


@dataclass(frozen=True)
class DeltaRule:
    threshold: float
    window: timedelta
    direction: str = "any"


@dataclass(frozen=True)
class WorkflowOutcome:
    result_id: str
    parsed_result: ParsedResult | None
    specimen_assessment: object
    reference_range: ReferenceRange | None
    flag: ResultFlag
    reason: str
    delta_check: DeltaCheck | None = None
    alert: CriticalAlertRecord | None = None


class LabResultWorkflow:
    """Coordinates specimen checks, normalized interpretation, delta checks, and alerts."""

    def __init__(
        self,
        reference_ranges: list[ReferenceRange],
        registry: CriticalAlertRegistry | None = None,
        critical_thresholds: Mapping[str, tuple[float | None, float | None]] | None = None,
        delta_rules: Mapping[str, DeltaRule] | None = None,
        sensitive_tests=None,
        escalation_policy: tuple[EscalationPolicy, ...] | None = None,
        qualitative_rules: Mapping[str, Mapping[str, ResultFlag]] | None = None,
        interpret_comparators: bool = False,
        notification_sender=None,
    ):
        self._reference_ranges = tuple(reference_ranges)
        self.notification_sender = notification_sender
        self.registry = registry if registry is not None else CriticalAlertRegistry()
        self._critical_thresholds = {
            str(code).strip().upper(): limits
            for code, limits in (critical_thresholds or {}).items()
        }
        self._delta_rules = {
            str(code).strip().upper(): rule
            for code, rule in (delta_rules or {}).items()
        }
        self._sensitive_tests = sensitive_tests
        self._interpret_comparators = bool(interpret_comparators)
        self._qualitative_rules = {}
        for code, rules in (qualitative_rules or {}).items():
            normalized_rules = {}
            for value, flag in rules.items():
                if not isinstance(flag, ResultFlag):
                    raise ValueError("Qualitative rules must map to ResultFlag values.")
                if flag in (ResultFlag.CRITICAL_LOW, ResultFlag.CRITICAL_HIGH):
                    raise ValueError("Qualitative rules cannot set critical flags without numeric thresholds.")
                normalized_rules[str(value).strip().upper()] = flag
            self._qualitative_rules[str(code).strip().upper()] = normalized_rules
        if escalation_policy is None:
            escalation_policy = (
                EscalationPolicy("CHARGE_NURSE", 30),
                EscalationPolicy("SUPERVISOR", 60),
            )
        self.escalator = CriticalAlertEscalator(
            self.registry, escalation_policy, self.notification_sender
        )
        self.escalation_scheduler = None

    @staticmethod
    def _outcome(result, parsed, assessment, reference, flag, reason,
                 delta_check=None, alert=None):
        return WorkflowOutcome(
            result.result_id, parsed, assessment, reference,
            flag, reason, delta_check, alert
        )

    def _critical_limits(self, result, reference):
        code = result.test.code.strip().upper()
        if code in self._critical_thresholds:
            return self._critical_thresholds[code]
        if reference.unit.code == "mmol/L" and code in DEFAULT_CRITICAL_THRESHOLDS:
            return DEFAULT_CRITICAL_THRESHOLDS[code]
        return None, None

    def _interpret_comparison(self, parsed, low, high, critical_low, critical_high):
        from decimal import Decimal
        bound = Decimal(str(parsed.numeric_value))
        low = Decimal(str(low))
        high = Decimal(str(high))
        critical_low = None if critical_low is None else Decimal(str(critical_low))
        critical_high = None if critical_high is None else Decimal(str(critical_high))
        op = parsed.comparator
        if op == "<":
            if critical_low is not None and bound <= critical_low:
                return ResultFlag.CRITICAL_LOW
            if bound <= low and (critical_low is None or bound > critical_low):
                return ResultFlag.LOW
        if op == "<=":
            if critical_low is not None and bound < critical_low:
                return ResultFlag.CRITICAL_LOW
            if bound <= low and (critical_low is None or bound > critical_low):
                return ResultFlag.LOW
        if op == ">":
            if critical_high is not None and bound >= critical_high:
                return ResultFlag.CRITICAL_HIGH
            if bound >= high and (critical_high is None or bound < critical_high):
                return ResultFlag.HIGH
        if op == ">=":
            if critical_high is not None and bound > critical_high:
                return ResultFlag.CRITICAL_HIGH
            if bound >= high and (critical_high is None or bound < critical_high):
                return ResultFlag.HIGH
        return ResultFlag.UNINTERPRETED

    def process(self, result: LabResult, previous: LabResult | None = None) -> WorkflowOutcome:
        assessment = assess_specimen(
            result.test.code, result.specimen_hemolyzed, self._sensitive_tests
        )
        if not assessment.interpretation_allowed:
            return self._outcome(
                result, None, assessment, None,
                ResultFlag.UNINTERPRETED, assessment.reason
            )

        try:
            parsed = parse_result(result.value)
        except ResultParseError as exc:
            return self._outcome(
                result, None, assessment, None, ResultFlag.UNINTERPRETED, str(exc)
            )

        if parsed.kind == "COMPARISON" and not self._interpret_comparators:
            return self._outcome(
                result, parsed, assessment, None, ResultFlag.UNINTERPRETED,
                "Comparator-based interpretation is not enabled."
            )
        if parsed.kind == "QUALITATIVE":
            code = result.test.code.strip().upper()
            value = str(parsed.qualitative_value or "").strip().upper()
            flag = self._qualitative_rules.get(code, {}).get(value)
            if flag is None:
                return self._outcome(
                    result, parsed, assessment, None, ResultFlag.UNINTERPRETED,
                    "No test-specific qualitative interpretation rule is configured."
                )
            return self._outcome(
                result, parsed, assessment, None, flag,
                "Qualitative result interpreted using the configured test-specific rule."
            )
        if parsed.kind not in ("NUMERIC", "COMPARISON"):
            return self._outcome(
                result, parsed, assessment, None, ResultFlag.UNINTERPRETED,
                "Result type is not supported for interpretation."
            )

        try:
            reference = select_reference_range(result, list(self._reference_ranges))
        except ReferenceRangeError as exc:
            return self._outcome(
                result, parsed, assessment, None, ResultFlag.UNINTERPRETED, str(exc)
            )

        try:
            normalized_value = normalize_value(
                result.test.code, str(parsed.numeric_value),
                result.unit.code, reference.unit.code
            )
        except UnitConversionError as exc:
            reason = str(exc)
            if result.unit.code != reference.unit.code:
                reason = (
                    "Result and reference range units differ; conversion unavailable: "
                    + reason
                )
            return self._outcome(
                result, parsed, assessment, reference,
                ResultFlag.UNINTERPRETED, reason
            )

        parsed = ParsedResult(
            raw_value=parsed.raw_value,
            kind=parsed.kind,
            numeric_value=normalized_value,
            comparator=parsed.comparator,
            qualitative_value=parsed.qualitative_value,
        )

        critical_low, critical_high = self._critical_limits(result, reference)
        try:
            if parsed.kind == "COMPARISON":
                flag = self._interpret_comparison(
                    parsed, reference.low, reference.high,
                    critical_low, critical_high,
                )
            if parsed.kind == "NUMERIC":
                flag = interpret_result(
                    normalized_value, reference.low, reference.high,
                    critical_low, critical_high,
                )
        except (InterpretationError, ValueError, TypeError) as exc:
            return self._outcome(
                result, parsed, assessment, reference, ResultFlag.UNINTERPRETED, str(exc)
            )

        delta_result = None
        rule = self._delta_rules.get(result.test.code.strip().upper())
        if rule is not None and parsed.kind == "NUMERIC":
            try:
                normalized_current = replace(
                    result, value=str(normalized_value), unit=reference.unit
                )
                normalized_previous = previous
                if previous is not None:
                    previous_parsed = parse_result(previous.value)
                    if previous_parsed.kind != "NUMERIC":
                        raise DeltaCheckError("Both result values must be numeric.")
                    previous_value = normalize_value(
                        previous.test.code, str(previous_parsed.numeric_value),
                        previous.unit.code, reference.unit.code
                    )
                    normalized_previous = replace(
                        previous, value=str(previous_value), unit=reference.unit
                    )
                delta_result = check_delta(
                    normalized_current, normalized_previous,
                    rule.threshold, rule.window, rule.direction
                )
            except (DeltaCheckError, UnitConversionError, ResultParseError,
                    ValueError, TypeError) as exc:
                return self._outcome(
                    result, parsed, assessment, reference,
                    ResultFlag.UNINTERPRETED,
                    f"Delta check could not be completed: {exc}"
                )

        if result.amended and flag != ResultFlag.UNINTERPRETED:
            self.registry.supersede_result(result.result_id)

        alert = None
        if flag in (ResultFlag.CRITICAL_LOW, ResultFlag.CRITICAL_HIGH):
            try:
                alert = self.registry.create_alert(
                    result.result_id, flag, result.collected_at
                )
                if alert is not None and not alert.notifications:
                    deliver_notification(
                        self.registry,
                        alert,
                        "ORDERING_PHYSICIAN",
                        None,
                        self.notification_sender,
                    )
            except (ValueError, TypeError) as exc:
                return self._outcome(
                    result, parsed, assessment, reference,
                    ResultFlag.UNINTERPRETED,
                    f"Critical alert could not be created: {exc}"
                )

        reason = "Result interpreted successfully."
        if delta_result is not None and delta_result.significant_change:
            reason = "Result interpreted; significant delta change detected."

        return self._outcome(
            result, parsed, assessment, reference, flag,
            reason, delta_result, alert
        )

    def start_escalation_scheduler(self, poll_interval_seconds: float = 1.0):
        """Start periodic escalation checks; call stop when shutting down."""
        if self.escalator is None:
            raise RuntimeError("No escalation policy was configured.")
        if self.escalation_scheduler is None:
            self.escalation_scheduler = AlertEscalationScheduler(
                self.escalator, poll_interval_seconds
            )
        return self.escalation_scheduler.start()

    def stop_escalation_scheduler(self, timeout: float | None = None) -> bool:
        if self.escalation_scheduler is None:
            return True
        return self.escalation_scheduler.stop(timeout)
    def escalate_due(self, now):
        if self.escalator is None:
            raise RuntimeError("No escalation policy was configured.")
        return self.escalator.escalate_due(now)

    def acknowledge(self, alert_id, acknowledged_by, read_back, acknowledged_at=None):
        if self.escalator is None:
            raise RuntimeError("No escalation policy was configured.")
        return self.escalator.acknowledge(
            alert_id, acknowledged_by, read_back, acknowledged_at
        )

    def close_alert(self, alert_id, closed_by, reason, closed_at=None):
        if self.escalator is None:
            raise RuntimeError("No escalation policy was configured.")
        return self.escalator.close(alert_id, closed_by, reason, closed_at)