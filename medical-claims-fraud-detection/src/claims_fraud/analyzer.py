"""Run all claim fraud detectors and return ranked investigator cases."""

from claims_fraud.case_builder import build_case_files
from claims_fraud.duplicate_detection import detect_duplicate_billing
from claims_fraud.upcoding_detection import detect_upcoding
from claims_fraud.unbundling_detection import detect_unbundling
from claims_fraud.impossible_schedule_detection import detect_impossible_schedules
from claims_fraud.post_death_detection import detect_post_death_services
from claims_fraud.statistical_detection import detect_statistical_anomalies


def analyze_claims(
    claims,
    providers,
    patients,
    procedure_time_estimates,
    visit_code_levels,
    comprehensive_code_components,
    threshold=3.0,
):
    """Run every detector and return ranked cases for investigators."""
    flags = []

    flags.extend(detect_duplicate_billing(claims))
    flags.extend(
        detect_upcoding(claims, providers, visit_code_levels, threshold)
    )
    flags.extend(
        detect_unbundling(claims, comprehensive_code_components)
    )
    flags.extend(
        detect_impossible_schedules(claims, procedure_time_estimates)
    )
    flags.extend(detect_post_death_services(claims, patients))
    flags.extend(detect_statistical_anomalies(claims, providers))

    return build_case_files(flags)
