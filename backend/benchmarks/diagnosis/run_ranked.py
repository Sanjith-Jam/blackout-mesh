"""One-shot ranked hypothesis evaluation on a newly frozen developer-held-out split."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone

from benchmarks.diagnosis.evaluate import evaluate
from benchmarks.diagnosis.fixtures import RANKED_DATA_DIR, RANKED_PROTOCOL
from benchmarks.diagnosis.run import markdown
from benchmarks.diagnosis.runner import TelemetryDetector, run_detector

RESULTS = RANKED_DATA_DIR.parent / "results"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--unseal", action="store_true")
    args = parser.parse_args(argv)
    if not args.unseal:
        raise SystemExit("ranked held-out results are sealed; pass --unseal for the one-time final evaluation")
    manifest = json.loads((RANKED_DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("protocol") != RANKED_PROTOCOL:
        raise SystemExit("ranked held-out protocol mismatch")
    source_files = (RANKED_DATA_DIR.parents[2] / "app" / "diagnosis" / "infer.py",
                    RANKED_DATA_DIR.parents[2] / "app" / "diagnostics" / "engine.py",
                    RANKED_DATA_DIR.parents[2] / "app" / "diagnostics" / "rules.py")
    detector_hash = hashlib.sha256(b"".join(path.read_bytes() for path in source_files)).hexdigest()
    if detector_hash != manifest.get("detector_sha256"):
        raise SystemExit("diagnostic rules changed after the ranked held-out set was frozen")
    data = RANKED_DATA_DIR / "heldout"
    for kind in ("observations", "truth"):
        digest = hashlib.sha256((data / f"{kind}.json").read_bytes()).hexdigest()
        if digest != manifest[f"{kind}_sha256"]:
            raise SystemExit(f"ranked held-out {kind} do not match the frozen manifest")
    bundles = json.loads((data / "observations.json").read_text(encoding="utf-8"))
    detector = TelemetryDetector()
    predictions = run_detector(detector, bundles)
    with open(RANKED_DATA_DIR / "UNSEALED.log", "a", encoding="utf-8") as log:
        log.write(f"{datetime.now(timezone.utc).isoformat()} evaluated {RANKED_PROTOCOL} with {detector.name}\n")
    truths = json.loads((data / "truth.json").read_text(encoding="utf-8"))
    report = evaluate(predictions, truths)
    RESULTS.mkdir(exist_ok=True)
    result = {"protocol": RANKED_PROTOCOL, "split": "heldout", "detector": detector.name,
              "manifest": manifest, "families": report}
    (RESULTS / "diagnosis_ranked_heldout.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    rendered = markdown("ranked heldout", detector.name, report, manifest)
    (RESULTS / "diagnosis_ranked_heldout.md").write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
