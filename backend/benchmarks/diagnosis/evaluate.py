"""Join predictions to truth after detection and compute the protocol metrics (#18)."""
from __future__ import annotations

import statistics

from benchmarks.diagnosis.fixtures import FAMILIES, FAULT_FAMILIES

FAULT_CODES = {"OVERLOAD", "COOLING_FAILURE", "HIGH_TEMPERATURE", "UPSTREAM_LOSS", "LOCAL_SUPPLY_LOSS", "BRANCH_INTERRUPTED"}
CONFIRM_STEPS = 2


def evaluate(predictions: dict, truths: list[dict]) -> dict:
    per_family = {f: {"scenarios": 0, "fault_scenarios": 0, "detected": 0, "claims": 0, "correct_claims": 0,
                      "false_alarm_steps": 0, "normal_asset_steps": 0, "detect_steps": [], "location_errors": 0,
                      "abstained_steps": 0, "asset_steps": 0, "correct_abstentions": 0, "safety_violations": 0,
                      "missed": []} for f in FAMILIES}
    for truth in truths:
        f = per_family[truth["family"]]
        preds = predictions[truth["id"]]
        expected = set(truth["expected"])
        onset = truth["onset_step"]
        faulty = set(truth["faulty_assets"])
        f["scenarios"] += 1
        detected_at = None
        for asset, series in preds.items():
            claimed_codes = set()
            for k, p in enumerate(series):
                f["asset_steps"] += 1
                fault_now = truth["fault_steps"][asset][k]
                if p["status"] == "ABSTAINED":
                    f["abstained_steps"] += 1
                    if "ABSTAINED" in expected and asset in faulty and fault_now:
                        f["correct_abstentions"] += 1
                inferred_fault = p["status"] == "FAULT_DETECTED" and p["code"] in FAULT_CODES
                if not fault_now:
                    f["normal_asset_steps"] += 1
                    if inferred_fault and not (asset in faulty and onset is not None and k >= onset):
                        f["false_alarm_steps"] += 1
                if inferred_fault:
                    claimed_codes.add(p["code"])
                hit = (asset in faulty and onset is not None and k >= onset
                       and ((p["status"] == "FAULT_DETECTED" and p["code"] in expected)
                            or (p["status"] == "ABSTAINED" and "ABSTAINED" in expected)))
                if hit and (detected_at is None or k - onset < detected_at):
                    detected_at = k - onset
                if (asset in faulty and fault_now and onset is not None and k >= onset + CONFIRM_STEPS
                        and p["status"] == "NORMAL"):
                    f["safety_violations"] += 1
            for code in claimed_codes:
                f["claims"] += 1
                if asset in faulty and code in expected:
                    f["correct_claims"] += 1
                elif asset not in faulty and truth["family"] in FAULT_FAMILIES:
                    f["location_errors"] += 1
        if truth["family"] in FAULT_FAMILIES:
            f["fault_scenarios"] += 1
            if detected_at is not None:
                f["detected"] += 1
                f["detect_steps"].append(detected_at)
            else:
                f["missed"].append(truth["id"])
    report = {}
    for family, f in per_family.items():
        steps = f.pop("detect_steps")
        report[family] = {
            **{k: v for k, v in f.items()},
            "recall": round(f["detected"] / f["fault_scenarios"], 3) if f["fault_scenarios"] else None,
            "precision": round(f["correct_claims"] / f["claims"], 3) if f["claims"] else None,
            "false_alarm_rate": round(f["false_alarm_steps"] / f["normal_asset_steps"], 4) if f["normal_asset_steps"] else None,
            "time_to_detect_steps_median": statistics.median(steps) if steps else None,
            "time_to_detect_steps_max": max(steps) if steps else None,
            "coverage": round(1 - f["abstained_steps"] / f["asset_steps"], 4) if f["asset_steps"] else None,
        }
    return report
