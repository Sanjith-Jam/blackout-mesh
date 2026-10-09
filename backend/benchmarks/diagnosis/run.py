"""Diagnosis benchmark CLI (#18).

    PYTHONPATH=backend python -m benchmarks.diagnosis.run                 # dev split only
    PYTHONPATH=backend python -m benchmarks.diagnosis.run --split calibration
    PYTHONPATH=backend python -m benchmarks.diagnosis.run --split heldout --unseal   # final evaluation only

Held-out truth is not read without --unseal; unsealing is logged to data/UNSEALED.log.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone

from benchmarks.diagnosis.evaluate import evaluate
from benchmarks.diagnosis.fixtures import DATA_DIR, PROTOCOL
from benchmarks.diagnosis.runner import TelemetryDetector, run_detector

RESULTS = DATA_DIR.parent / "results"


def verify_manifest(split):
    manifest = json.loads((DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
    entry = manifest["splits"][split]
    for kind in ("observations", "truth"):
        digest = hashlib.sha256((DATA_DIR / split / f"{kind}.json").read_bytes()).hexdigest()
        if digest != entry[f"{kind}_sha256"]:
            raise SystemExit(f"{split}/{kind}.json does not match manifest; fixtures changed")
    return manifest


def markdown(split, detector, report, manifest):
    lines = [f"# Diagnosis benchmark: `{split}` split", "",
             f"Protocol `{PROTOCOL}` · {manifest['process']} · detector: {detector}. "
             f"{manifest['splits'][split]['scenarios']} scenarios (32 steps × 3 transformers each). "
             "Synthetic telemetry only; this does not establish field accuracy.", "",
             "| Family | Scenarios | Recall | Precision | False alarms (rate) | Time to detect (median / max steps) | "
             "Location errors | Coverage | Correct abstentions | Safety violations | Missed |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    fmt = lambda v: "—" if v is None else v
    for family, r in report.items():
        lines.append(f"| {family} | {r['scenarios']} | {fmt(r['recall'])} ({r['detected']}/{r['fault_scenarios']}) | "
                     f"{fmt(r['precision'])} ({r['correct_claims']}/{r['claims']}) | {r['false_alarm_steps']} ({fmt(r['false_alarm_rate'])}) | "
                     f"{fmt(r['time_to_detect_steps_median'])} / {fmt(r['time_to_detect_steps_max'])} | {r['location_errors']} | "
                     f"{fmt(r['coverage'])} | {r['correct_abstentions']} | {r['safety_violations']} | {len(r['missed'])} |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=("dev", "calibration", "heldout"))
    ap.add_argument("--unseal", action="store_true")
    args = ap.parse_args(argv)
    if args.split == "heldout" and not args.unseal:
        raise SystemExit("held-out results are sealed; pass --unseal only for the final, frozen evaluation")
    manifest = verify_manifest(args.split)
    bundles = json.loads((DATA_DIR / args.split / "observations.json").read_text(encoding="utf-8"))
    detector = TelemetryDetector()
    predictions = run_detector(detector, bundles)  # truth files cannot be opened in here
    if args.split == "heldout":
        with open(DATA_DIR / "UNSEALED.log", "a", encoding="utf-8") as log:
            log.write(f"{datetime.now(timezone.utc).isoformat()} unsealed heldout for {detector.name}\n")
    truths = json.loads((DATA_DIR / args.split / "truth.json").read_text(encoding="utf-8"))
    report = evaluate(predictions, truths)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"diagnosis_{args.split}.json").write_text(json.dumps({"protocol": PROTOCOL, "split": args.split,
                                                                       "detector": detector.name, "families": report}, indent=1), encoding="utf-8")
    (RESULTS / f"diagnosis_{args.split}.md").write_text(markdown(args.split, detector.name, report, manifest), encoding="utf-8")
    print(markdown(args.split, detector.name, report, manifest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
