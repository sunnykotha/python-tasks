from datetime import date

from adherence import Drug, FillEvent, Patient, analyze_adherence


def main():
    patient = Patient("P001")
    drugs = [Drug("DRUG-A", "blood-pressure")]
    fills = [
        FillEvent("P001", "DRUG-A", date(2026, 1, 1), 90),
        FillEvent("P001", "DRUG-A", date(2026, 3, 15), 90),
    ]

    report = analyze_adherence(
        patient=patient,
        fills=fills,
        drugs=drugs,
        drug_class="blood-pressure",
        period_days=180,
    )

    print("Medication Adherence Report")
    print("---------------------------")
    print(f"Patient: {patient.patient_id}")
    print(f"Drug class: blood-pressure")
    print(
        f"Measurement period: "
        f"{report.measurement_period.start_date} to "
        f"{report.measurement_period.end_date}"
    )
    print(f"Period days: {report.period_days}")
    print(f"Covered days: {report.covered_days}")
    print(f"Uncovered days: {len(report.uncovered_dates)}")
    print(f"PDC: {report.pdc:.2%}")
    print(f"Adherent (PDC >= 80%): {report.adherent}")


if __name__ == "__main__":
    main()