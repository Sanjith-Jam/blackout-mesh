"""Explainable fault hypotheses from observation windows and configured ratings only (#4).

Inputs: validated Observation envelopes, equipment ratings, topology (which assets share a supply).
Never: scenario names, fixture labels, simulator feeder/capacity flags.
A hypothesis is INFERRED when it holds on CONFIRM_SAMPLES consecutive samples; holding only on the
latest sample makes it an observation ALARM. Missing or stale data makes the result ABSTAINED.
Voltage/current/temperature cannot uniquely identify every fault; results are likely causes.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.diagnosis.observations import Observation

CONFIRM_SAMPLES = 2
WINDOW_SAMPLES = 4
STALE_AFTER = timedelta(seconds=3)


@dataclass(frozen=True)
class TransformerRating:
    rated_current_a: float = 100.0
    overload_factor: float = 1.1
    hot_c: float = 80.0
    low_input_v: float = 180.0
    dead_output_v: float = 100.0


@dataclass(frozen=True)
class FeederRating:
    nominal_v: float = 230.0
    dead_v: float = 50.0


TRANSFORMER_QUANTITIES = ("current_a", "temperature_c", "input_voltage_v", "output_voltage_v", "cooling_ok")


class ObservationWindow:
    """Last WINDOW_SAMPLES observations per (asset, quantity). Late/out-of-order samples are dropped."""

    def __init__(self, size: int = WINDOW_SAMPLES):
        self.size = size
        self._data: dict[tuple[str, str], deque] = {}
        self.dropped_out_of_order = 0

    def add(self, obs: Observation) -> bool:
        key = (obs.asset_id, obs.quantity)
        series = self._data.setdefault(key, deque(maxlen=self.size))
        if series and obs.sequence <= series[-1].sequence:
            self.dropped_out_of_order += 1
            return False
        series.append(obs)
        return True

    def series(self, asset: str, quantity: str) -> list[Observation]:
        return list(self._data.get((asset, quantity), ()))

    def clear(self):
        self._data.clear()


def _recent_values(window, asset, quantity, n):
    series = window.series(asset, quantity)[-n:]
    return [o.value for o in series], series


def _status(flags: list[bool]) -> str | None:
    if len(flags) >= CONFIRM_SAMPLES and all(flags[-CONFIRM_SAMPLES:]):
        return "INFERRED"
    if flags and flags[-1]:
        return "ALARM"
    return None


def diagnose_transformer(window: ObservationWindow, asset: str, rating: TransformerRating, now: datetime,
                         peers_input_low: dict[str, bool] | None = None) -> dict:
    latest = {}
    history = {}
    stale, missing = [], []
    for q in TRANSFORMER_QUANTITIES:
        values, series = _recent_values(window, asset, q, CONFIRM_SAMPLES)
        history[q] = values
        if not series:
            missing.append(q)
            continue
        last = series[-1]
        latest[q] = last.value
        if last.value is None:
            missing.append(q)
        if now - last.observed_at > STALE_AFTER:
            stale.append(q)

    evidence = []
    if latest.get("current_a") is not None:
        evidence.append(f"Current {latest['current_a']:.1f} A; overload above {rating.rated_current_a * rating.overload_factor:.1f} A "
                        f"({rating.overload_factor:.0%} of {rating.rated_current_a:.0f} A rating).")
    if latest.get("temperature_c") is not None:
        evidence.append(f"Temperature {latest['temperature_c']:.1f} °C; hot at {rating.hot_c:.0f} °C.")
    if latest.get("cooling_ok") is not None:
        evidence.append(f"Cooling reported {'operational' if latest['cooling_ok'] else 'failed'}.")
    if latest.get("input_voltage_v") is not None and latest.get("output_voltage_v") is not None:
        evidence.append(f"Input {latest['input_voltage_v']:.1f} V; output {latest['output_voltage_v']:.1f} V; "
                        f"low input below {rating.low_input_v:.0f} V.")
    base = {"window": {"samples": len(history.get("current_a") or []), "confirm_samples": CONFIRM_SAMPLES,
                       "stale_after_s": STALE_AFTER.total_seconds()},
            "missing": missing, "stale": stale, "affected_assets": [asset], "hypotheses": []}

    if stale:
        return {**base, "code": "UNKNOWN", "status": "ABSTAINED", "severity": "unknown",
                "cause": "Stale sensor evidence",
                "evidence": evidence + ["Stale (no reading in the last "
                                        f"{STALE_AFTER.total_seconds():.0f} s): " + ", ".join(stale)],
                "recommendation": "Restore sensor telemetry before diagnosing."}
    if missing:
        return {**base, "code": "UNKNOWN", "status": "ABSTAINED", "severity": "unknown",
                "cause": "Insufficient sensor evidence",
                "evidence": evidence + ["Missing: " + ", ".join(q.replace("_", " ") for q in missing)],
                "recommendation": "Restore sensor telemetry before diagnosing."}

    n = min(len(v) for v in history.values())
    h = {q: v[-n:] for q, v in history.items()}
    input_low = [i < rating.low_input_v and o < rating.dead_output_v for i, o in zip(h["input_voltage_v"], h["output_voltage_v"])]
    overload = [c > rating.rated_current_a * rating.overload_factor for c in h["current_a"]]
    hot = [t >= rating.hot_c for t in h["temperature_c"]]
    cooling_failed = [c is False for c in h["cooling_ok"]]

    hypotheses = []
    low_status = _status(input_low)
    if low_status:
        if peers_input_low is None:  # no peer readings: cannot tell shared from local loss
            code, support, against = "UPSTREAM_LOSS", [], ["no peer readings to separate shared from local loss"]
        elif all(peers_input_low.values()):
            code, support, against = "UPSTREAM_LOSS", ["every transformer reports low input"], []
        else:
            code, support, against = "BRANCH_INTERRUPTION", ["other transformers report normal input"], []
        hypotheses.append({"code": code, "status": low_status,
                           "supporting": [f"input and output voltage low on {sum(input_low)} of {n} samples"] + support,
                           "contradicting": against})
    ov_status = _status(overload)
    if ov_status:
        hypotheses.append({"code": "OVERLOAD", "status": ov_status,
                           "supporting": [f"current above threshold on {sum(overload)} of {n} samples"]
                                         + (["temperature also high"] if hot[-1] else []),
                           "contradicting": [] if hot[-1] else ["temperature still normal (overload may be recent)"]})
    cf_status = _status([a and b for a, b in zip(hot, cooling_failed)])
    if cf_status:
        hypotheses.append({"code": "COOLING_FAILURE", "status": cf_status,
                           "supporting": ["high temperature with cooling reported failed"],
                           "contradicting": ["current also above threshold"] if overload[-1] else []})
    ht_status = _status(hot)
    if ht_status and not cf_status:
        hypotheses.append({"code": "HIGH_TEMPERATURE", "status": ht_status,
                           "supporting": ["temperature at or above hot threshold"],
                           "contradicting": [] if overload[-1] else ["current normal and cooling operational: check ambient and sensor"]})
    base["hypotheses"] = hypotheses

    order = ["UPSTREAM_LOSS", "BRANCH_INTERRUPTION", "OVERLOAD", "COOLING_FAILURE", "HIGH_TEMPERATURE"]
    inferred = sorted((x for x in hypotheses if x["status"] == "INFERRED"), key=lambda x: order.index(x["code"]))
    top = inferred[0] if inferred else None
    if top is None:
        alarms = [x["code"] for x in hypotheses if x["status"] == "ALARM"]
        if alarms:
            return {**base, "code": "ALARM", "status": "ALARM", "severity": "medium",
                    "cause": "Observation alarm awaiting confirmation (" + ", ".join(a.replace("_", " ").lower() for a in alarms) + ")",
                    "evidence": evidence, "recommendation": "Watch the next readings; no root cause inferred yet."}
        return {**base, "code": "NORMAL", "status": "INFERRED", "severity": "normal",
                "cause": "No configured threshold exceeded", "evidence": evidence, "recommendation": "Continue monitoring."}
    details = {
        "UPSTREAM_LOSS": ("critical", "Likely upstream supply loss shared by all transformers",
                          "Check the upstream supply and incoming connections."),
        "BRANCH_INTERRUPTION": ("critical", "Likely interruption on this transformer's own supply branch",
                                "Inspect this transformer's incoming branch and protection device."),
        "OVERLOAD": ("high", "Likely overload: current exceeds the configured rating threshold",
                     "Review connected demand and verify with qualified protection equipment."),
        "COOLING_FAILURE": ("high", "Likely cooling failure: elevated temperature with cooling reported failed",
                            "Inspect cooling equipment and temperature using approved procedures."),
        "HIGH_TEMPERATURE": ("medium", "Elevated temperature without a confirmed cause",
                             "Check loading, ventilation, ambient temperature and the sensor itself."),
    }[top["code"]]
    return {**base, "code": top["code"], "status": "INFERRED", "severity": details[0], "cause": details[1],
            "evidence": evidence + [f"Supporting: {s}" for s in top["supporting"]]
                        + [f"Contradicting: {s}" for s in top["contradicting"]],
            "recommendation": details[2]}


def diagnose_campus(window: ObservationWindow, bus: str, feeders: list[str], rating: FeederRating, now: datetime) -> dict:
    """Feeder interruptions from bus/feeder voltage telemetry. Configured capacity is not evidence."""
    bus_values, bus_series = _recent_values(window, bus, "bus_voltage_v", CONFIRM_SAMPLES)
    if not bus_series or bus_values[-1] is None or now - bus_series[-1].observed_at > STALE_AFTER:
        return {"has_fault": False, "status": "ABSTAINED", "severity": "UNKNOWN", "hypotheses": [],
                "diagnosis": "Insufficient or stale bus telemetry; no fault inferred.", "affected_assets": []}
    hypotheses = []
    bus_dead = _status([v < rating.dead_v for v in bus_values])
    if bus_dead:
        hypotheses.append({"code": "UPSTREAM_LOSS", "status": bus_dead, "assets": [bus] + feeders,
                           "supporting": ["source bus voltage near zero"], "contradicting": []})
    else:
        for feeder in feeders:
            values, series = _recent_values(window, feeder, "feeder_voltage_v", CONFIRM_SAMPLES)
            if not series or values[-1] is None or now - series[-1].observed_at > STALE_AFTER:
                hypotheses.append({"code": "UNKNOWN", "status": "ABSTAINED", "assets": [feeder],
                                   "supporting": [f"feeder {feeder} telemetry missing or stale"], "contradicting": []})
                continue
            dead = _status([v < rating.dead_v for v in values])
            if dead:
                hypotheses.append({"code": "BRANCH_INTERRUPTION", "status": dead, "assets": [feeder],
                                   "supporting": [f"feeder {feeder} voltage near zero while bus voltage is normal"],
                                   "contradicting": []})
    inferred = [x for x in hypotheses if x["status"] == "INFERRED" and x["code"] != "UNKNOWN"]
    alarms = [x for x in hypotheses if x["status"] == "ALARM"]
    abstained = [x for x in hypotheses if x["status"] == "ABSTAINED"]
    if inferred:
        text = " ".join(("Likely upstream supply loss." if x["code"] == "UPSTREAM_LOSS"
                         else f"Likely interruption on feeder {x['assets'][0]}.") for x in inferred)
        return {"has_fault": True, "status": "INFERRED", "severity": "HIGH", "hypotheses": hypotheses,
                "diagnosis": text, "affected_assets": sorted({a for x in inferred for a in x["assets"]})}
    if alarms:
        return {"has_fault": False, "status": "ALARM", "severity": "MEDIUM", "hypotheses": hypotheses,
                "diagnosis": "Voltage alarm awaiting confirmation.", "affected_assets": sorted({a for x in alarms for a in x["assets"]})}
    if abstained:
        return {"has_fault": False, "status": "ABSTAINED", "severity": "UNKNOWN", "hypotheses": hypotheses,
                "diagnosis": "Some feeder telemetry is missing or stale; no fault inferred for those feeders.",
                "affected_assets": sorted({a for x in abstained for a in x["assets"]})}
    return {"has_fault": False, "status": "INFERRED", "severity": "NONE", "hypotheses": [],
            "diagnosis": "Bus and feeder voltages normal.", "affected_assets": []}
