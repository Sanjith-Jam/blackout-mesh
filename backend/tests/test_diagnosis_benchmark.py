"""Diagnosis benchmark infrastructure (#18). Development data only; held-out stays sealed."""
import hashlib
import json

import pytest

from benchmarks.diagnosis import fixtures
from benchmarks.diagnosis.evaluate import evaluate
from benchmarks.diagnosis.run import main as run_main
from benchmarks.diagnosis.run_ranked import main as run_ranked_main
from benchmarks.diagnosis.runner import LeakageError, TelemetryDetector, run_detector

DATA = fixtures.DATA_DIR
LABEL_KEYS = {"family", "fault", "label", "scenario", "expected", "onset", "onset_step", "faulty_assets", "fault_steps", "seed"}


def load(split, kind):
    return json.loads((DATA / split / f"{kind}.json").read_text(encoding="utf-8"))


def test_committed_fixtures_match_manifest_and_regenerate_identically(tmp_path):
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["protocol"] == fixtures.PROTOCOL and "developer-held-out" in manifest["process"]
    regenerated = fixtures.write_all(tmp_path)
    for split, entry in manifest["splits"].items():
        for kind in ("observations", "truth"):
            digest = hashlib.sha256((DATA / split / f"{kind}.json").read_bytes()).hexdigest()
            assert digest == entry[f"{kind}_sha256"] == regenerated["splits"][split][f"{kind}_sha256"]
        assert entry["scenarios"] == len(fixtures.FAMILIES) * 4
        assert set(entry["families"]) == set(fixtures.FAMILIES)


def test_ranked_heldout_fixture_is_frozen_and_sealed(tmp_path):
    manifest_path = fixtures.RANKED_DATA_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["protocol"] == fixtures.RANKED_PROTOCOL
    assert "no independent custodian" in manifest["process"]
    regenerated = fixtures.write_ranked_heldout(tmp_path / "ranked")
    assert json.loads(json.dumps(regenerated)) == manifest
    for kind in ("observations", "truth"):
        path = fixtures.RANKED_DATA_DIR / "heldout" / f"{kind}.json"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest[f"{kind}_sha256"]
    log = fixtures.RANKED_DATA_DIR / "UNSEALED.log"
    before = log.read_bytes() if log.exists() else None
    with pytest.raises(SystemExit) as exc:
        run_ranked_main([])
    assert "sealed" in str(exc.value)
    assert (log.read_bytes() if log.exists() else None) == before


def test_observation_bundles_carry_no_labels():
    for split in fixtures.REGIMES:
        raw = (DATA / split / "observations.json").read_text(encoding="utf-8")
        for bundle in json.loads(raw):
            assert not LABEL_KEYS & set(bundle)
            assert all(not LABEL_KEYS & set(e) for e in fixtures.envelopes(bundle)[:20])
        for family in fixtures.FAMILIES:
            assert f'"{family}"' not in raw  # no family name anywhere in what detectors see


def test_parameter_regimes_and_seeds_are_disjoint_across_splits():
    regimes = fixtures.REGIMES
    names = list(regimes)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            for key in ("overload", "hot"):
                for lo1, hi1 in regimes[a][key]:
                    for lo2, hi2 in regimes[b][key]:
                        assert hi1 < lo2 or hi2 < lo1, (a, b, key)
            assert regimes[a]["noise"] != regimes[b]["noise"] and regimes[a]["delay"] != regimes[b]["delay"]
            assert not set(regimes[a]["seeds"]) & set(regimes[b]["seeds"])


class OracleContaminated(TelemetryDetector):
    """Cheats by reading the truth file: the guard must stop it."""

    def diagnose(self, now):
        (DATA / "dev" / "truth.json").read_text(encoding="utf-8")
        return super().diagnose(now)


class LabelSniffer(TelemetryDetector):
    def reset(self, bundle):
        super().reset(bundle)
        self.family = bundle["family"]  # no such field: labels are not in bundles


def test_leakage_guard_catches_an_oracle_contaminated_detector():
    bundles = load("dev", "observations")[:2]
    with pytest.raises(LeakageError):
        run_detector(OracleContaminated(), bundles)
    with pytest.raises(KeyError):
        run_detector(LabelSniffer(), bundles)
    assert run_detector(TelemetryDetector(), bundles)  # the honest detector still runs


def test_heldout_is_sealed_without_unseal():
    log = DATA / "UNSEALED.log"
    before = log.read_bytes() if log.exists() else None
    with pytest.raises(SystemExit) as exc:
        run_main(["--split", "heldout"])
    assert "sealed" in str(exc.value)
    assert (log.read_bytes() if log.exists() else None) == before


def test_evaluator_keeps_misses_and_counts_safety_violations():
    truths = load("dev", "truth")
    bundles = {b["id"]: b for b in load("dev", "observations")}
    always_normal = {t["id"]: {a: [{"code": "NORMAL", "status": "NORMAL"}] * bundles[t["id"]]["steps"]
                               for a in bundles[t["id"]]["assets"]} for t in truths}
    report = evaluate(always_normal, truths)
    assert report["overload"]["recall"] == 0.0 and len(report["overload"]["missed"]) == 4
    assert report["overload"]["safety_violations"] > 0 and report["upstream_loss"]["safety_violations"] > 0
    assert report["normal"]["false_alarm_steps"] == 0

    perfect = {}
    for t in truths:
        b = bundles[t["id"]]
        code = sorted(set(t["expected"]) - {"NORMAL"})
        perfect[t["id"]] = {a: [({"code": code[0], "status": "FAULT_DETECTED"} if code[0] != "ABSTAINED" else {"code": "UNKNOWN", "status": "ABSTAINED"})
                                if (a in t["faulty_assets"] and code and t["fault_steps"][a][k]) else {"code": "NORMAL", "status": "NORMAL"}
                                for k in range(b["steps"])] for a in b["assets"]}
    report = evaluate(perfect, truths)
    for family in fixtures.FAULT_FAMILIES:
        assert report[family]["recall"] == 1.0 and report[family]["false_alarm_steps"] == 0, family


def test_rank_metrics_use_ordered_hypotheses_and_report_denominators():
    truths = load("dev", "truth")
    bundles = {b["id"]: b for b in load("dev", "observations")}
    predictions = {t["id"]: {a: [{"code": "NORMAL", "status": "NORMAL", "hypotheses": []}
                                 for _ in range(bundles[t["id"]]["steps"])]
                              for a in bundles[t["id"]]["assets"]} for t in truths}
    truth = next(t for t in truths if t["family"] == "overload_and_cooling")
    asset = truth["faulty_assets"][0]
    step = truth["onset_step"] + 2
    predictions[truth["id"]][asset][step] = {
        "code": "HIGH_TEMPERATURE", "status": "FAULT_DETECTED",
        "hypotheses": [{"code": "HIGH_TEMPERATURE"}, {"code": "OVERLOAD"}],
    }
    report = evaluate(predictions, truths)["overload_and_cooling"]
    assert report["ranking_samples"] == 4
    assert report["top1_hits"] == 0 and report["top3_hits"] == 1
    assert report["mean_reciprocal_rank"] == 0.125
    assert report["ranked_hypothesis_precision"] == 0.5
