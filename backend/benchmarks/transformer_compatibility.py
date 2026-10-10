"""Offline synthetic interface check; stdout only, never model accuracy."""
import json
from datetime import datetime, timedelta, timezone
from app.diagnosis.transformer_advisory import advise
from app.district.authority import diagnose_transformer


def run():
    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    cases = []
    for name, temp, current, cooling in (("normal", 60, 20, True),
            ("overload", 105, 60, True), ("cooling_failure", 105, 60, False)):
        rows = [dict(transformer_id="SYNTHETIC", recorded_at=now-timedelta(hours=719-i),
            status="SIMULATED", load_percentage=60, oil_temperature_c=temp,
            ambient_temp_c=25, power_factor=.9, harmonic_distortion=2,
            age_years=5, capacity_kva=100, is_fault_event=False,
            fault_event_provenance="OBSERVED_TRIP") for i in range(720)]
        advisory = advise(rows, "SYNTHETIC", now)
        baseline = diagnose_transformer(dict(status="SIMULATED", oil_temperature_c=temp,
                                             voltage_v=380, current_a=current, cooling_ok=cooling))
        cases.append(dict(case=name, advisory=advisory["status"],
                          feature_compatible=advisory["features"] is not None,
                          baseline=baseline["status"]))
    return dict(evaluation="SYNTHETIC_INTERFACE_ONLY", cases=cases,
                denominator=len(cases), feature_compatible=3, advisory_abstentions=3,
                failures=sum(not c["feature_compatible"] or c["advisory"] != "UNKNOWN" for c in cases),
                real_transformers=0, real_readings=0, train=0, validation=0, test=0,
                calibration=None, model_accuracy=None, baseline_accuracy=None)


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, indent=2))
    raise SystemExit(bool(report["failures"]))
