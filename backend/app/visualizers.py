"""Independent synthetic classroom and hospital demos."""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

from app.core.restoration import RestorationGate

ROOMS = ("CR1", "CR2", "CR3")
LOADS = {
    "CR1": [("lighting", "Lighting", 100, True), ("computers", "Computers", 600, True), ("fans", "Fans", 100, False), ("projector", "Projector", 200, False), ("ac", "Air conditioning", 1000, False)],
    "CR2": [("lighting", "Lighting", 100, True), ("computers", "Computers", 600, True), ("fans", "Fans", 100, False), ("projector", "Projector", 200, False), ("ac", "Air conditioning", 1000, False)],
    "CR3": [("lighting", "Lighting", 100, True), ("computers", "Computers", 600, True), ("fans", "Fans", 100, False), ("projector", "Projector", 200, False), ("ac", "Air conditioning", 1000, False), ("instruments", "Instruments", 2000, False)],
}
LOAD_KEYS = tuple((room, item[0]) for room in ROOMS for item in LOADS[room])
ZONES = ("ICU", "Theatre", "Wards")


NORMAL_CAPACITY_W = 8000
OVERLOAD_CAPACITY_W = 3400
CAPACITY_RANGE_W = (0, 8000)
REPLAY_STEP_S = 5.0
ACTIVITY_RANK = {"ACTIVE": 0, "UNKNOWN": 1, "INACTIVE": 2}
REPLAY_PATH = Path(__file__).resolve().parents[1] / "models" / "replay.json"


def load_replay(path=REPLAY_PATH):
    try:
        data = json.loads(Path(path).read_text())
        return {cid: rows for cid, rows in data.items() if cid in ROOMS and isinstance(rows, list) and rows}
    except (OSError, ValueError):
        return {}


class ClassroomDemo:
    """Several rooms may be scanned at once. The activity model ranks scanned rooms from
    recorded sensor observations; the rank orders optional loads only, never essentials."""

    def __init__(self, clock=time.monotonic, model=None, replay=None):
        if model is None:
            from app.activity.model import ActivityModel
            model = ActivityModel()
        self.model = model
        self.replay = load_replay() if replay is None else replay
        self.replay_length = min((len(rows) for rows in self.replay.values()), default=0)
        self.capacity = NORMAL_CAPACITY_W
        self.scanned: list[str] = []   # scan order; the last entry is the most recent card
        self.gate = RestorationGate(clock)
        self.replay_running = self.replay_length > 0
        self.replay_base = 0
        self.replay_anchor = clock()
        self._predictions: dict[tuple[str, int], dict] = {}
        self._replay_index = 0
        self._activity: dict[str, dict] = {}
        self.published: dict | None = None
        self.published_revision = 0
        self._advance_evidence()
        initial = (1 << len(LOAD_KEYS)) - 1
        self.gate.update(initial, self._signature(self._room_order()), range(len(LOAD_KEYS)))
        self.tick()

    # ---- recorded sensor replay and model evidence ----
    def replay_index(self):
        """Replay cursor as of the last tick (read-only)."""
        return self._replay_index

    def _clock_replay_index(self):
        if not self.replay_length:
            return 0
        steps = int((self.gate.clock() - self.replay_anchor) // REPLAY_STEP_S) if self.replay_running else 0
        return (self.replay_base + steps) % self.replay_length

    def _advance_evidence(self):
        """Move the replay cursor to the current time and run (cached) inference. Tick-only."""
        self._replay_index = self._clock_replay_index()
        self._activity = {cid: self._infer(cid) for cid in ROOMS}

    def activity(self, cid):
        """Model evidence for a room as of the last tick (read-only)."""
        return self._activity.get(cid) or {"state": "UNKNOWN", "score": None, "reason": "awaiting first tick",
                                           "model_version": "unavailable", "evidence": {}}

    def _infer(self, cid):
        if not self.replay_length or cid not in self.replay:
            return {"state": "UNKNOWN", "score": None, "reason": "no recorded sensor evidence",
                    "model_version": "unavailable", "evidence": {}}
        index = self._replay_index
        cached = self._predictions.get((cid, index))
        if cached is None:
            row = self.replay[cid][index]
            evidence = {key: row.get(key) for key in ("temperature_c", "humidity_pct", "co2_ppm", "humidity_ratio")}
            try:
                prediction = self.model.predict(evidence)
            except Exception as exc:
                prediction = {"state": "UNKNOWN", "score": None, "model_version": "unavailable",
                              "reason": f"inference failed: {type(exc).__name__}"}
            cached = {**prediction, "evidence": evidence}
            self._predictions[(cid, index)] = cached
        return cached

    # ---- allocation ----
    def _room_order(self):
        """Scanned rooms ranked by model state, then scan order; unscanned rooms after.
        Raw scores are not compared: small score noise would reorder rooms on every reading."""
        def key(cid):
            return (ACTIVITY_RANK.get(self.activity(cid).get("state"), 1), self.scanned.index(cid))
        return sorted(self.scanned, key=key) + [r for r in ROOMS if r not in self.scanned]

    def _signature(self, order):
        return (self.capacity, tuple(r for r in order if r in self.scanned))

    def _priority(self, order):
        # Essentials in every room first, then scanned rooms' optional loads in model rank, then the rest.
        result = [(r, item) for r in order for item in LOADS[r] if item[3]]
        result += [(r, item) for r in order for item in LOADS[r] if not item[3] and r in self.scanned]
        result += [(r, item) for r in ROOMS for item in LOADS[r] if not item[3] and r not in self.scanned]
        return result

    def snapshot(self):
        """Read-only: a copy of the last published state. Never advances replay or restoration."""
        return copy.deepcopy(self.published)

    def tick(self):
        """Advance replay evidence, allocation and staged restoration, then publish."""
        self._advance_evidence()
        candidate = self._project()
        if self.published is None or candidate != {k: v for k, v in self.published.items() if k != "published_revision"}:
            self.published_revision += 1
            candidate["published_revision"] = self.published_revision
            self.published = candidate
        return self.snapshot()

    def _project(self):
        order = self._room_order()
        priority = self._priority(order)
        target: set[tuple[str, str]] = set()
        remaining = self.capacity
        for room, item in priority:
            key = (room, item[0])
            if item[2] <= remaining:
                target.add(key)
                remaining -= item[2]
        proposed = sum(1 << LOAD_KEYS.index(key) for key in target)
        bit_order = [LOAD_KEYS.index((room, item[0])) for room, item in priority]
        applied = self.gate.update(proposed, self._signature(order), bit_order)
        current = {key for bit, key in enumerate(LOAD_KEYS) if applied & (1 << bit)}
        rooms = []
        for cid in ROOMS:
            loads = []
            for lid, name, watts, essential in LOADS[cid]:
                key = (cid, lid)
                on = key in current
                reason = ("served by classroom demo" if on else
                          "Waiting for simulated restoration delay" if key in target else
                          "Insufficient capacity for essential load" if essential else
                          "Shed by classroom demo policy")
                loads.append({"id": lid, "name": name, "watts": watts, "essential": essential,
                              "served": on, "reason": reason})
            act = self.activity(cid)
            rooms.append({"id": cid, "name": f"Classroom {cid[-1]}", "rfid_active": cid in self.scanned,
                          "priority_rank": order.index(cid) + 1 if cid in self.scanned else None,
                          "activity": {key: act.get(key) for key in ("state", "score", "reason", "model_version", "evidence")},
                          "loads": loads})
        requested = sum(x[2] for rows in LOADS.values() for x in rows)
        served_w = sum(x[2] for r in ROOMS for x in LOADS[r] if (r, x[0]) in current)
        status = self.model.status() if hasattr(self.model, "status") else {}
        return {"capacity_w": self.capacity, "capacity_range_w": list(CAPACITY_RANGE_W),
                "requested_w": requested, "served_w": served_w, "shortfall_w": requested - served_w,
                "selected_classroom_id": self.scanned[-1] if self.scanned else None,
                "scanned_classroom_ids": [r for r in ROOMS if r in self.scanned],
                "priority_order": [r for r in order if r in self.scanned],
                "rooms": rooms, "mode": "SIMULATED",
                "model": {"ready": bool(status.get("ready")), "model_version": status.get("model_version", "unavailable"),
                          "fallback_reason": status.get("fallback_reason")},
                "replay": {"running": self.replay_running, "index": self.replay_index(),
                           "length": self.replay_length, "step_s": REPLAY_STEP_S},
                "policy": "Classroom-only: lighting and computers in every room first. Scanned rooms' other "
                          "equipment next, ranked by the activity model (ACTIVE, then UNKNOWN, then INACTIVE; "
                          "earlier scan first within a state). Unscanned rooms' optional loads last."}

    def act(self, action: str, classroom_id: str | None = None, capacity_w: int | None = None):
        if action == "scan":
            if classroom_id not in self.scanned:
                self.scanned.append(classroom_id)
        elif action == "unscan":
            if classroom_id in self.scanned:
                self.scanned.remove(classroom_id)
        elif action == "set_capacity":
            self.capacity = capacity_w
        elif action == "normal":
            self.capacity = NORMAL_CAPACITY_W
        elif action == "overload":
            self.capacity = OVERLOAD_CAPACITY_W
        elif action == "replay_pause":
            self.replay_base, self.replay_running = self._clock_replay_index(), False
        elif action == "replay_resume":
            if self.replay_length:
                self.replay_base, self.replay_anchor, self.replay_running = self._clock_replay_index(), self.gate.clock(), True
        elif action == "replay_step":
            if self.replay_length:
                self.replay_base, self.replay_anchor = (self._clock_replay_index() + 1) % self.replay_length, self.gate.clock()
        elif action == "reset":
            self.__init__(self.gate.clock, self.model, self.replay)
        return self.tick()  # a command wakes control immediately


def diagnose(rated_current_a, current_a, temperature_c, input_voltage_v, output_voltage_v, cooling_ok):
    """Classify only provided synthetic sensor observations and configured rating."""
    missing = [name for name, value in (("current", current_a), ("temperature", temperature_c),
               ("input voltage", input_voltage_v), ("output voltage", output_voltage_v), ("cooling", cooling_ok)) if value is None]
    evidence = []
    if current_a is not None:
        evidence.append(f"Current {current_a:.1f} A; overload threshold {rated_current_a * 1.1:.1f} A (110% of rating).")
    if temperature_c is not None:
        evidence.append(f"Temperature {temperature_c:.1f} °C; hot threshold 80 °C.")
    if cooling_ok is not None:
        evidence.append(f"Cooling {'operational' if cooling_ok else 'failed'}.")
    if input_voltage_v is not None and output_voltage_v is not None:
        evidence.append(f"Input {input_voltage_v:.1f} V; output {output_voltage_v:.1f} V; low-input threshold 180 V.")
    if missing:
        return {"code": "UNKNOWN", "cause": "Insufficient sensor evidence", "severity": "unknown", "evidence": evidence + ["Missing: " + ", ".join(missing)], "recommendation": "Restore sensor telemetry before diagnosing."}
    if input_voltage_v < 180 and output_voltage_v < 100:
        return {"code": "UPSTREAM_LOSS", "cause": "Possible upstream supply loss", "severity": "critical", "evidence": evidence, "recommendation": "Check the upstream supply and incoming connections."}
    if current_a > rated_current_a * 1.1:
        return {"code": "OVERLOAD", "cause": "Current exceeds the configured rating threshold", "severity": "high", "evidence": evidence, "recommendation": "Review connected demand and verify with qualified protection equipment."}
    if temperature_c >= 80 and not cooling_ok:
        return {"code": "COOLING_FAILURE", "cause": "Elevated temperature with cooling reported failed", "severity": "high", "evidence": evidence, "recommendation": "Inspect cooling equipment and temperature using approved procedures."}
    if temperature_c >= 80:
        return {"code": "HIGH_TEMPERATURE", "cause": "Elevated transformer temperature", "severity": "medium", "evidence": evidence, "recommendation": "Check loading, ventilation and sensor readings."}
    return {"code": "NORMAL", "cause": "No configured demo threshold exceeded", "severity": "normal", "evidence": evidence, "recommendation": "Continue monitoring."}


NORMAL_SENSORS = (45.0, 58.0, 230.0, 220.0, True)
HOSPITAL_FAULT_FIXTURES = {
    "overload": (130.0, 72.0, 230.0, 218.0, True),
    "cooling_failure": (45.0, 91.0, 230.0, 220.0, False),
    "missing_sensor": (None, 55.0, 230.0, 220.0, True),
}


def hospital_snapshot(scenario="normal", zone="Theatre"):
    target_i = 2
    if zone == "ICU":
        target_i = 1
    elif zone == "Wards":
        target_i = 3

    transformers = []
    for i in range(1, 4):
        fixture = ((0.0, 40.0, 90.0, 20.0, True) if scenario == "upstream_loss"
                   else HOSPITAL_FAULT_FIXTURES.get(scenario, NORMAL_SENSORS) if i == target_i
                   else NORMAL_SENSORS)
        current, temp, vin, vout, cooling = fixture
        sensors = {"current_a": current, "temperature_c": temp, "input_voltage_v": vin,
                   "output_voltage_v": vout, "cooling_ok": cooling}
        diagnosis = diagnose(100.0, **sensors)
        transformers.append({"id": f"TX{i}", "name": f"Transformer {i}", "zone": ZONES[i - 1],
                             "rated_current_a": 100.0, "sensors": sensors, "diagnosis": diagnosis,
                             "energized": vout is not None and vout >= 100.0})
    return {"mode": "SIMULATED", "transformers": transformers,
            "summary": "Synthetic sensor diagnosis for demonstration; thresholds are not certified protection settings."}
