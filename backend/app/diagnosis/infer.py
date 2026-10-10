"""Explainable fault hypotheses from observation windows and configured ratings only (#4).

Inputs: validated Observation envelopes, equipment ratings, topology (which assets share a supply).
Never: scenario names, fixture labels, simulator feeder/capacity flags.
Each reading goes through the multi-hypothesis engine in app.diagnostics (#19). A hypothesis is
confirmed when it holds on CONFIRM_SAMPLES consecutive readings (status FAULT_DETECTED); holding only on
the latest reading makes it an observation ALARM. Missing or stale data makes the result ABSTAINED.
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
# A current reading repeated exactly on STUCK_SAMPLES readings while temperature moves by at least
# STUCK_TEMPERATURE_SPAN_C with cooling reported OK is treated as a frozen sensor (A2). The flag stays
# until the reading changes, so a stuck sensor cannot turn back into a confident NORMAL.
STUCK_SAMPLES = 3
STUCK_TEMPERATURE_SPAN_C = 3.0


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
        self.stuck: dict[tuple[str, str], float] = {}  # (asset, quantity) -> frozen value

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
        self.stuck.clear()


def _recent_values(window, asset, quantity, n):
    series = window.series(asset, quantity)[-n:]
    return [o.value for o in series], series


def _status(flags: list[bool]) -> str | None:
    if len(flags) >= CONFIRM_SAMPLES and all(flags[-CONFIRM_SAMPLES:]):
        return "INFERRED"
    if flags and flags[-1]:
        return "ALARM"
    return None


def _readings(window: ObservationWindow, asset: str, n: int) -> list[dict]:
    """Last n complete readings (one observation per quantity with the same sequence), oldest first."""
    by_seq: dict[int, dict] = {}
    for q in TRANSFORMER_QUANTITIES:
        for o in window.series(asset, q):
            by_seq.setdefault(o.sequence, {})[q] = o
    complete = sorted(s for s, row in by_seq.items() if len(row) == len(TRANSFORMER_QUANTITIES))
    return [by_seq[s] for s in complete[-n:]]


def _update_stuck(window: ObservationWindow, asset: str) -> float | None:
    """Latch a frozen current sensor; returns its frozen value while it stays frozen."""
    key = (asset, "current_a")
    rows = _readings(window, asset, STUCK_SAMPLES)
    if not rows:
        return window.stuck.get(key)
    latest = rows[-1]["current_a"].value
    if key in window.stuck:
        if latest == window.stuck[key]:
            return latest
        del window.stuck[key]
    if len(rows) < STUCK_SAMPLES:
        return None
    currents = [r["current_a"].value for r in rows]
    temps = [r["temperature_c"].value for r in rows]
    cooling = [r["cooling_ok"].value for r in rows]
    if (None in currents or None in temps or len(set(currents)) != 1 or not all(c is True for c in cooling)
            or max(temps) - min(temps) < STUCK_TEMPERATURE_SPAN_C):
        return None
    window.stuck[key] = latest
    return latest


def _engine(rating: TransformerRating, asset: str, row: dict) -> dict:
    """One reading through the multi-hypothesis engine (#19)."""
    from app.diagnostics import diagnose_transformer as engine
    values = {q: row[q].value for q in TRANSFORMER_QUANTITIES}
    return engine(rated_current_a=rating.rated_current_a, asset_id=asset, **values).model_dump(mode="json")


def _relabel_supply_loss(result: dict, peers_input_low: dict[str, bool] | None) -> dict:
    """The engine sees one asset; peer readings tell a shared upstream loss from a local branch loss."""
    for h in result["hypotheses"]:
        if h["code"] != "UPSTREAM_LOSS":
            continue
        if peers_input_low is None:
            h["contradicting_evidence"] = h["contradicting_evidence"] + ["No peer readings to separate shared from local loss."]
        elif all(peers_input_low.values()):
            h["supporting_evidence"] = h["supporting_evidence"] + ["Every transformer reports low input."]
        else:
            h["code"] = "LOCAL_SUPPLY_LOSS"
            h["id"] = h["id"].replace("UPSTREAM_LOSS", "LOCAL_SUPPLY_LOSS")
            h["cause"] = "Likely supply loss on this transformer's own incoming branch"
            h["supporting_evidence"] = h["supporting_evidence"] + ["Other transformers report normal input."]
            h["recommendation"] = "Inspect this transformer's incoming branch and protection device."
    if result["hypotheses"] and result["code"] == "UPSTREAM_LOSS":
        result["code"] = result["hypotheses"][0]["code"]
    return result


def diagnose_transformer(window: ObservationWindow, asset: str, rating: TransformerRating, now: datetime,
                         peers_input_low: dict[str, bool] | None = None) -> dict:
    """Windowed, telemetry-only diagnosis (#4) using the multi-hypothesis engine (#19) per reading.

    Status: NORMAL | FAULT_DETECTED (a hypothesis held on CONFIRM_SAMPLES consecutive readings) |
    ALARM (held on the latest reading only) | ABSTAINED (engine abstained, or evidence missing/stale).
    """
    rows = _readings(window, asset, CONFIRM_SAMPLES)
    base = {"asset_id": asset, "affected_assets": [asset], "stale": [], "missing": [],
            "window": {"samples": len(rows), "confirm_samples": CONFIRM_SAMPLES,
                       "stale_after_s": STALE_AFTER.total_seconds()}}

    def abstain(details, missing=(), stale=()):
        abstention = {"asset_id": asset, "reason": "INSUFFICIENT_TELEMETRY", "details": details,
                      "missing_sensors": list(missing), "contradictory_readings": [], "indistinguishable_candidates": [],
                      "next_check_needed": "Restore sensor telemetry before diagnosing."}
        return {**base, "status": "ABSTAINED", "hypotheses": [], "abstention": abstention, "code": "UNKNOWN",
                "cause": details, "severity": "unknown", "missing": list(missing), "stale": list(stale),
                "evidence": [details], "recommendation": abstention["next_check_needed"]}

    if not rows:
        return abstain("Insufficient sensor evidence: no complete reading yet.", missing=TRANSFORMER_QUANTITIES)
    latest = rows[-1]
    stale = [q for q in TRANSFORMER_QUANTITIES if now - latest[q].observed_at > STALE_AFTER]
    if stale:
        return abstain("Stale sensor evidence", stale=stale)
    missing = [q for q in TRANSFORMER_QUANTITIES if latest[q].value is None]
    frozen = _update_stuck(window, asset)

    results = [_relabel_supply_loss(_engine(rating, asset, r), peers_input_low) for r in rows]
    current = results[-1]
    out = {**base, **current, "missing": missing, "affected_assets": [asset]}
    if frozen is not None and current["status"] in ("NORMAL", "FAULT_DETECTED") and not current["hypotheses"]:
        details = (f"Current sensor suspected stuck: {frozen} A repeated on {STUCK_SAMPLES}+ readings while "
                   "temperature changed with cooling OK. Its reading cannot rule out an overload.")
        abstention = {"asset_id": asset, "reason": "SUSPECTED_STUCK_SENSOR", "details": details,
                      "missing_sensors": [], "contradictory_readings": ["current_a", "temperature_c"],
                      "indistinguishable_candidates": ["OVERLOAD", "STUCK_CURRENT_SENSOR"],
                      "next_check_needed": "Check the current transformer and its wiring, or measure the load with a clamp meter."}
        return {**base, "status": "ABSTAINED", "hypotheses": [], "abstention": abstention, "code": "UNKNOWN",
                "cause": details, "severity": "unknown", "missing": missing, "stale": [],
                "evidence": [details], "recommendation": abstention["next_check_needed"]}
    if frozen is not None:
        out["evidence"] = list(out.get("evidence", [])) + [f"Current reading {frozen} A has not changed; sensor may be stuck."]
    if current["status"] != "FAULT_DETECTED":
        return out  # NORMAL, or the engine's own abstention (missing, contradictory, indistinguishable)

    earlier = [{h["code"] for h in r["hypotheses"]} for r in results[:-1]]
    confirmed = []
    for h in current["hypotheses"]:
        ok = len(results) >= CONFIRM_SAMPLES and all(h["code"] in codes for codes in earlier)
        h["confirmation"] = "INFERRED" if ok else "ALARM"
        if ok:
            confirmed.append(h)
    if not confirmed:
        codes = ", ".join(h["code"].replace("_", " ").lower() for h in current["hypotheses"])
        return {**out, "status": "ALARM", "code": "ALARM", "severity": "medium",
                "cause": f"Observation alarm awaiting confirmation ({codes})",
                "recommendation": "Watch the next readings; no root cause inferred yet."}
    top = confirmed[0]  # engine order: severity, then evidence score
    cause = top["cause"] if len(confirmed) == 1 else f"Multiple co-occurring faults ({', '.join(h['code'] for h in confirmed)})"
    return {**out, "status": "FAULT_DETECTED", "code": top["code"], "severity": top["severity"], "cause": cause,
            "recommendation": top["recommendation"]}


def _campus_hypothesis(code, asset, cause, confirmation, support, recommendation, severity="high"):
    return {"id": f"{asset}:{code}", "code": code, "asset_id": asset, "cause": cause, "severity": severity,
            "evidence_score": 1.0 if confirmation == "INFERRED" else 0.5,
            "sufficiency": "SUFFICIENT" if confirmation == "INFERRED" else "PARTIAL",
            "supporting_evidence": support, "contradicting_evidence": [], "recommendation": recommendation,
            "confirmation": confirmation}


def diagnose_campus(window: ObservationWindow, bus: str, feeders: list[str], rating: FeederRating, now: datetime) -> dict:
    """Feeder interruptions from bus/feeder voltage telemetry. Configured capacity is not evidence.

    Status: NORMAL | FAULT_DETECTED | ALARM | ABSTAINED; hypotheses use the #19 engine's shape.
    """
    bus_values, bus_series = _recent_values(window, bus, "bus_voltage_v", CONFIRM_SAMPLES)
    if not bus_series or bus_values[-1] is None or now - bus_series[-1].observed_at > STALE_AFTER:
        return {"has_fault": False, "status": "ABSTAINED", "severity": "UNKNOWN", "hypotheses": [],
                "diagnosis": "Insufficient or stale bus telemetry; no fault inferred.", "affected_assets": []}
    hypotheses = []
    bus_dead = _status([v < rating.dead_v for v in bus_values])
    if bus_dead:
        hypotheses.append(_campus_hypothesis("UPSTREAM_LOSS", "MAIN_SUPPLY", "Likely loss of the upstream supply",
                                             bus_dead, ["Source bus voltage near zero."],
                                             "Check the upstream supply and incoming connections.", "critical"))
    else:
        for feeder in feeders:
            values, series = _recent_values(window, feeder, "feeder_voltage_v", CONFIRM_SAMPLES)
            if not series or values[-1] is None or now - series[-1].observed_at > STALE_AFTER:
                hypotheses.append(_campus_hypothesis("UNKNOWN", f"FEEDER_{feeder}", f"Feeder {feeder} telemetry missing or stale",
                                                     "ABSTAINED", [], "Restore feeder telemetry.", "unknown"))
                continue
            dead = _status([v < rating.dead_v for v in values])
            if dead:
                hypotheses.append(_campus_hypothesis(
                    "FEEDER_DISCONNECTED", f"FEEDER_{feeder}", f"Likely interruption on feeder {feeder}", dead,
                    [f"Feeder {feeder} voltage near zero while the bus voltage is normal."],
                    f"Inspect breaker and feeder line {feeder}."))
    inferred = [h for h in hypotheses if h["confirmation"] == "INFERRED"]
    alarms = [h for h in hypotheses if h["confirmation"] == "ALARM"]
    abstained = [h for h in hypotheses if h["confirmation"] == "ABSTAINED"]
    if inferred:
        return {"has_fault": True, "status": "FAULT_DETECTED", "severity": "HIGH", "hypotheses": hypotheses,
                "diagnosis": " ".join(h["cause"] + "." for h in inferred),
                "affected_assets": sorted({h["asset_id"] for h in inferred})}
    if alarms:
        return {"has_fault": False, "status": "ALARM", "severity": "MEDIUM", "hypotheses": hypotheses,
                "diagnosis": "Voltage alarm awaiting confirmation.", "affected_assets": sorted({h["asset_id"] for h in alarms})}
    if abstained:
        return {"has_fault": False, "status": "ABSTAINED", "severity": "UNKNOWN", "hypotheses": hypotheses,
                "diagnosis": "Some feeder telemetry is missing or stale; no fault inferred for those feeders.",
                "affected_assets": sorted({h["asset_id"] for h in abstained})}
    return {"has_fault": False, "status": "NORMAL", "severity": "NONE", "hypotheses": [],
            "diagnosis": "Bus and feeder voltages normal.", "affected_assets": []}
