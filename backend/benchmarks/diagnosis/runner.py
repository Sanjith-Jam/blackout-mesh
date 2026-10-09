"""Observation-only runner with a leakage guard (#18).

Detectors receive envelopes in arrival order and are asked for a diagnosis every step. While a
detector runs, an audit hook raises LeakageError if anything opens a truth file.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

from benchmarks.diagnosis.fixtures import DATA_DIR, envelopes

BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


class LeakageError(RuntimeError):
    pass


_guard = {"active": False, "protected": set()}


def _audit(event, args):
    if _guard["active"] and event == "open" and args:
        path = args[0]
        if isinstance(path, (str, bytes, os.PathLike)):
            resolved = os.path.normcase(os.path.abspath(os.fsdecode(path)))
            if resolved in _guard["protected"]:
                raise LeakageError(f"detector opened truth file {resolved}")


sys.addaudithook(_audit)


def truth_paths():
    return {os.path.normcase(os.path.abspath(p)) for p in DATA_DIR.glob("*/truth.json")}


class guarded:
    """Context in which truth files cannot be opened."""

    def __enter__(self):
        _guard["protected"] = truth_paths()
        _guard["active"] = True

    def __exit__(self, *exc):
        _guard["active"] = False


class TelemetryDetector:
    """Adapter for app.diagnosis (#4): validated envelopes -> rolling window -> per-asset diagnosis."""

    name = "app.diagnosis (telemetry-only, #4)"

    def reset(self, bundle):
        from app.diagnosis.infer import ObservationWindow, TransformerRating
        self.assets = bundle["assets"]
        self.window = ObservationWindow()
        self.rating = TransformerRating(rated_current_a=bundle["rated_current_a"])

    def observe(self, envelope, now):
        from app.diagnosis.observations import ObservationError, validate
        raw = {k: envelope[k] for k in ("asset_id", "quantity", "value", "unit", "sequence", "quality")}
        raw["observed_at"] = BASE_TIME + timedelta(seconds=envelope["t"])
        raw["received_at"] = now
        try:
            self.window.add(validate(raw, set(self.assets), now))
        except ObservationError:
            pass  # malformed envelopes are dropped, as in production

    def diagnose(self, now):
        from app.diagnosis.infer import diagnose_transformer
        low = {}
        for a in self.assets:
            ins, outs = self.window.series(a, "input_voltage_v"), self.window.series(a, "output_voltage_v")
            low[a] = bool(ins and outs and ins[-1].value is not None and outs[-1].value is not None
                          and ins[-1].value < self.rating.low_input_v and outs[-1].value < self.rating.dead_output_v)
        out = {}
        for a in self.assets:
            d = diagnose_transformer(self.window, a, self.rating, now, low)
            out[a] = {"code": d["code"], "status": d["status"]}
        return out


def run_detector(detector, bundles) -> dict:
    """Return predictions[scenario_id][asset] = list of {"code", "status"} per step."""
    predictions = {}
    with guarded():
        for bundle in bundles:
            detector.reset(bundle)
            by_step = {}
            for env in envelopes(bundle):
                by_step.setdefault(env["arrival_step"], []).append(env)
            per_asset = {a: [] for a in bundle["assets"]}
            for k in range(bundle["steps"]):
                now = BASE_TIME + timedelta(seconds=k * bundle["step_s"])
                for env in by_step.get(k, []):
                    detector.observe(env, now)
                result = detector.diagnose(now)
                for a in bundle["assets"]:
                    per_asset[a].append(result[a])
            predictions[bundle["id"]] = per_asset
    return predictions
