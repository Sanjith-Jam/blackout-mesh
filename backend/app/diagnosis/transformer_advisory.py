"""Offline advisory compatibility only; see docs/TRANSFORMER_ADVISORY.md.
Feature vocabulary/window semantics adapted from roshini0108, revision
78aeea0381a066fd97d9e00cce5a176a7af6b0ed, ml/src/preprocessor.py.
User reports owner authorization for code reuse. No weights/data imported.
"""
from datetime import datetime, timedelta, timezone
from math import isfinite
from statistics import mean

BOUNDS = {
    "load_percentage": (0, 200), "oil_temperature_c": (-30, 250),
    "ambient_temp_c": (-50, 70), "power_factor": (0, 1),
    "harmonic_distortion": (0, 100), "age_years": (0, 100),
    "capacity_kva": (0.001, 100000),
}


def features_at(rows, transformer_id, as_of):
    """720 complete hourly UTC observations, inclusive of the decision hour.

    Both future training and serving must call this function. Extra fields are
    ignored. is_fault_event must be an observed trip, never a simulator label.
    Returns (features or None, abstention reason).
    """
    if not isinstance(as_of, datetime) or as_of.tzinfo is None:
        return None, "UNSUPPORTED_TIME"
    if not isinstance(transformer_id, str) or not transformer_id:
        return None, "UNSUPPORTED_ID"
    as_of = as_of.astimezone(timezone.utc)
    selected = []
    for row in rows:
        if row.get("transformer_id") != transformer_id:
            continue
        stamp = row.get("recorded_at")
        if not isinstance(stamp, datetime) or stamp.tzinfo is None:
            return None, "UNSUPPORTED_TIME"
        if as_of - timedelta(hours=720) < stamp <= as_of:
            selected.append(row)
    selected.sort(key=lambda r: r["recorded_at"])
    if len(selected) != 720:
        return None, "INCOMPLETE_HISTORY"
    latest = selected[-1]["recorded_at"]
    if not 0 <= (as_of - latest).total_seconds() < 3600:
        return None, "STALE"
    for i, row in enumerate(selected):
        if row.get("status") not in {"OBSERVED", "SIMULATED"}:
            return None, "UNSUPPORTED_STATUS"
        if i and row["recorded_at"] - selected[i-1]["recorded_at"] != timedelta(hours=1):
            return None, "UNSUPPORTED_CADENCE"
        for field, (low, high) in BOUNDS.items():
            value = row.get(field)
            if type(value) not in (int, float) or not isfinite(value) or not low <= value <= high:
                return None, "INVALID_" + field.upper()
        if type(row.get("is_fault_event")) is not bool or row.get("fault_event_provenance") != "OBSERVED_TRIP":
            return None, "UNSUPPORTED_TRIP_EVIDENCE"
    result = {field: selected[-1][field] for field in BOUNDS}
    for prefix, field in (("load", "load_percentage"), ("oil_temp", "oil_temperature_c")):
        values = [r[field] for r in selected]
        result[prefix + "_24h_mean"] = mean(values[-24:])
        result[prefix + "_7d_mean"] = mean(values[-168:])
        result[prefix + "_trend"] = mean(values[-168:]) - mean(values)
    result["oil_temp_24h_max"] = max(r["oil_temperature_c"] for r in selected[-24:])
    pf = [r["power_factor"] for r in selected]
    result["pf_trend"] = mean(pf[-168:]) - mean(pf)
    result["overload_events_7d"] = sum(r["load_percentage"] > 100 for r in selected[-168:])
    result["high_temp_events_7d"] = sum(r["oil_temperature_c"] > 80 for r in selected[-168:])
    result["fault_events_7d"] = sum(r["is_fault_event"] for r in selected[-168:])
    result.update(hour_of_day=latest.astimezone(timezone.utc).hour,
                  month=latest.astimezone(timezone.utc).month)
    return result, None


def advise(rows, transformer_id, as_of):
    features, reason = features_at(rows, transformer_id, as_of)
    return {"status": "UNKNOWN", "scope": "MAINTENANCE_INSPECTION_ONLY",
            "reason": reason or "NO_RIGHTS_CLEARED_EVALUATED_MODEL",
            "failure_probability": None, "features": features}
