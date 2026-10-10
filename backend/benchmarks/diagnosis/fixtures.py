"""Fixture generation for the diagnosis benchmark (#18). See PROTOCOL.md.

Observation bundles and truth are written to separate files; bundles carry no labels.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

PROTOCOL = "diag-bench-protocol-2"
STEPS = 32
STEP_S = 0.25
ASSETS = ("TX1", "TX2", "TX3")
RATED_A = 100.0
FIELDS = ("current_a", "temperature_c", "input_voltage_v", "output_voltage_v", "cooling_ok")
UNITS = {"current_a": "A", "temperature_c": "degC", "input_voltage_v": "V", "output_voltage_v": "V", "cooling_ok": "bool"}
DATA_DIR = Path(__file__).resolve().parent / "data"
RANKED_PROTOCOL = "diag-bench-ranked-v2"
RANKED_DATA_DIR = Path(__file__).resolve().parent / "ranked-v2"
RANKED_REGIME = {"overload": [(1.41, 1.70)], "hot": [(95.1, 110.0)],
                 "noise": (5.0, 2.5), "delay": 3, "seeds": range(4000, 4008)}

FAMILIES = ("normal", "demand_change", "hot_ambient", "overload", "cooling_failure", "overload_and_cooling",
            "upstream_loss", "branch_interruption", "sensor_dropout", "stuck_sensor", "delay_reorder", "recovery_chatter")

REGIMES = {
    # Disjoint parameter regimes: no overload level, hot temperature, noise or delay value is shared across splits.
    "dev": {"overload": [(1.25, 1.40)], "hot": [(86.0, 95.0)], "noise": (1.0, 0.5), "delay": 1, "seeds": range(0, 4)},
    "calibration": {"overload": [(1.16, 1.24)], "hot": [(82.0, 85.9)], "noise": (3.0, 1.5), "delay": 2, "seeds": range(100, 104)},
    "heldout": {"overload": [(1.105, 1.155), (1.41, 1.70)], "hot": [(80.0, 81.9), (95.1, 110.0)], "noise": (5.0, 2.5),
                "delay": 3, "seeds": range(1000, 1004)},
}

# What a correct detector should say on a faulty asset, per family (any member of the set is accepted).
EXPECTED = {
    "demand_change": {"NORMAL"}, "hot_ambient": {"HIGH_TEMPERATURE"}, "overload": {"OVERLOAD"},
    "cooling_failure": {"COOLING_FAILURE"}, "overload_and_cooling": {"OVERLOAD", "COOLING_FAILURE"},
    "upstream_loss": {"UPSTREAM_LOSS"}, "branch_interruption": {"LOCAL_SUPPLY_LOSS"},
    "sensor_dropout": {"ABSTAINED"}, "stuck_sensor": {"OVERLOAD", "HIGH_TEMPERATURE", "ABSTAINED"},
    "delay_reorder": {"OVERLOAD"}, "recovery_chatter": {"OVERLOAD"},
}
FAULT_FAMILIES = {f for f, codes in EXPECTED.items() if codes != {"NORMAL"}}


def _pick(rng, ranges):
    lo, hi = rng.choice(ranges)
    return rng.uniform(lo, hi)


def scenario(split: str, family: str, seed: int, protocol: str = PROTOCOL,
             regime_override: dict | None = None) -> tuple[dict, dict]:
    regime = regime_override or REGIMES[split]
    rng = random.Random(f"{protocol}:{split}:{family}:{seed}")
    sigma_i, sigma_t = regime["noise"]
    target = rng.choice(ASSETS)
    onset = rng.randint(6, 14)
    level = _pick(rng, regime["overload"]) * RATED_A
    hot = _pick(rng, regime["hot"])
    dropout_field = rng.choice(("current_a", "temperature_c", "output_voltage_v"))
    chatter_period = rng.randint(3, 5)

    values = {a: [] for a in ASSETS}
    truth_steps = {a: [] for a in ASSETS}
    for k in range(STEPS):
        after = k >= onset
        for a in ASSETS:
            v = {"current_a": 45.0 + rng.gauss(0, sigma_i), "temperature_c": 58.0 + rng.gauss(0, sigma_t),
                 "input_voltage_v": 230.0 + rng.gauss(0, 1.0), "output_voltage_v": 220.0 + rng.gauss(0, 1.0),
                 "cooling_ok": True}
            faulty = False
            on_target = a == target
            ramp = min(1.0, (k - onset + 1) / 4) if after else 0.0
            if after and family == "demand_change" and on_target:
                v["current_a"] = 45.0 + ramp * rng.uniform(30, 55)
            elif after and family == "hot_ambient" and on_target:
                v["temperature_c"] = 58.0 + ramp * (hot - 58.0) + rng.gauss(0, sigma_t); faulty = ramp >= 1
            elif after and family in ("overload", "delay_reorder", "stuck_sensor") and on_target:
                v["current_a"] = level + rng.gauss(0, sigma_i)
                v["temperature_c"] = 58.0 + ramp * 20.0 + rng.gauss(0, sigma_t); faulty = True
            elif after and family == "cooling_failure" and on_target:
                v["cooling_ok"] = False
                v["temperature_c"] = 58.0 + ramp * (hot - 58.0) + rng.gauss(0, sigma_t); faulty = ramp >= 1
            elif after and family == "overload_and_cooling" and on_target:
                v["cooling_ok"] = False
                v["current_a"] = level + rng.gauss(0, sigma_i)
                v["temperature_c"] = 58.0 + ramp * (hot - 58.0) + rng.gauss(0, sigma_t); faulty = True
            elif after and family == "upstream_loss":
                v.update(current_a=0.0, input_voltage_v=rng.uniform(60, 90), output_voltage_v=rng.uniform(0, 20)); faulty = True
            elif after and family == "branch_interruption" and on_target:
                v.update(current_a=0.0, input_voltage_v=rng.uniform(60, 90), output_voltage_v=rng.uniform(0, 20)); faulty = True
            elif after and family == "sensor_dropout" and on_target:
                v[dropout_field] = None; faulty = True
            elif after and family == "recovery_chatter" and on_target and ((k - onset) // chatter_period) % 2 == 0:
                v["current_a"] = level + rng.gauss(0, sigma_i); faulty = True
            for q in ("current_a", "temperature_c", "input_voltage_v", "output_voltage_v"):
                if v[q] is not None:
                    v[q] = round(max(0.0, v[q]), 2)
            values[a].append(v)
            truth_steps[a].append(faulty)
        if family == "stuck_sensor" and after:
            values[target][k]["current_a"] = values[target][onset - 1]["current_a"]  # sensor frozen

    # Compact columnar bundle: per asset and quantity one value per step, plus per-step arrival delay.
    # delay_reorder delays some of the target's samples by up to `delay` steps; others arrive on time.
    delays = {a: [rng.randint(1, regime["delay"]) if family == "delay_reorder" and a == target and rng.random() < 0.4 else 0
                  for _ in range(STEPS)] for a in ASSETS}
    sid = hashlib.sha256(f"{protocol}:{split}:{family}:{seed}".encode()).hexdigest()[:16]
    bundle = {"id": sid, "step_s": STEP_S, "steps": STEPS, "assets": list(ASSETS), "rated_current_a": RATED_A,
              "series": {a: {q: [values[a][k][q] for k in range(STEPS)] for q in FIELDS} for a in ASSETS},
              "arrival_delay": delays}
    faulty_assets = list(ASSETS) if family == "upstream_loss" else ([] if family in ("normal",) else [target])
    truth = {"id": sid, "family": family, "seed": seed, "onset_step": None if family == "normal" else onset,
             "faulty_assets": faulty_assets if family in FAULT_FAMILIES else [],
             "expected": sorted(EXPECTED.get(family, {"NORMAL"})), "fault_steps": truth_steps}
    return bundle, truth


def envelopes(bundle: dict) -> list[dict]:
    """Expand a compact bundle into observation envelopes in arrival order."""
    out = []
    for k in range(bundle["steps"]):
        for a in bundle["assets"]:
            delay = bundle["arrival_delay"][a][k]
            for q in FIELDS:
                value = bundle["series"][a][q][k]
                out.append({"asset_id": a, "quantity": q, "value": value, "unit": UNITS[q],
                            "t": round(k * bundle["step_s"], 3), "sequence": k + 1, "arrival_step": k + delay,
                            "quality": "GOOD" if value is not None else "MISSING"})
    out.sort(key=lambda e: (e["arrival_step"], e["sequence"]))
    return out


def generate(split: str):
    bundles, truths = [], []
    for family in FAMILIES:
        for seed in REGIMES[split]["seeds"]:
            b, t = scenario(split, family, seed)
            bundles.append(b)
            truths.append(t)
    return bundles, truths


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_all(data_dir: Path = DATA_DIR) -> dict:
    manifest = {"protocol": PROTOCOL, "process": "developer-held-out (no independent custodian)", "splits": {}}
    for split in REGIMES:
        out = data_dir / split
        out.mkdir(parents=True, exist_ok=True)
        bundles, truths = generate(split)
        (out / "observations.json").write_text(json.dumps(bundles, separators=(",", ":")), encoding="utf-8")
        (out / "truth.json").write_text(json.dumps(truths, separators=(",", ":")), encoding="utf-8")
        manifest["splits"][split] = {
            "scenarios": len(bundles), "families": {f: len(REGIMES[split]["seeds"]) for f in FAMILIES},
            "seeds": [REGIMES[split]["seeds"].start, REGIMES[split]["seeds"].stop - 1],
            "regime": {k: v for k, v in REGIMES[split].items() if k != "seeds"},
            "observations_sha256": _sha(out / "observations.json"), "truth_sha256": _sha(out / "truth.json")}
    (data_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def write_ranked_heldout(data_dir: Path = RANKED_DATA_DIR) -> dict:
    out = data_dir / "heldout"
    out.mkdir(parents=True, exist_ok=True)
    bundles, truths = [], []
    for family in FAMILIES:
        for seed in RANKED_REGIME["seeds"]:
            bundle, truth = scenario("heldout", family, seed, RANKED_PROTOCOL, RANKED_REGIME)
            bundles.append(bundle)
            truths.append(truth)
    observations_path, truth_path = out / "observations.json", out / "truth.json"
    observations_path.write_text(json.dumps(bundles, separators=(",", ":")), encoding="utf-8")
    truth_path.write_text(json.dumps(truths, separators=(",", ":")), encoding="utf-8")
    source_files = (Path(__file__).resolve().parents[2] / "app" / "diagnosis" / "infer.py",
                    Path(__file__).resolve().parents[2] / "app" / "diagnostics" / "engine.py",
                    Path(__file__).resolve().parents[2] / "app" / "diagnostics" / "rules.py")
    manifest = {"protocol": RANKED_PROTOCOL,
                "process": "developer-held-out frozen before first ranked-metric run; no independent custodian",
                "detector_sha256": hashlib.sha256(b"".join(path.read_bytes() for path in source_files)).hexdigest(),
                "scenarios": len(bundles), "families": {family: len(RANKED_REGIME["seeds"]) for family in FAMILIES},
                "seeds": [RANKED_REGIME["seeds"].start, RANKED_REGIME["seeds"].stop - 1],
                "regime": {key: value for key, value in RANKED_REGIME.items() if key != "seeds"},
                "observations_sha256": _sha(observations_path), "truth_sha256": _sha(truth_path)}
    (data_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(write_all(), indent=1))
