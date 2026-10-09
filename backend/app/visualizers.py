"""Independent synthetic classroom and hospital demos."""
from __future__ import annotations

import time
from app.core.restoration import RestorationGate

ROOMS = ("CR1", "CR2", "CR3")
LOADS = {
    "CR1": [("lighting", "Lighting", 100, True), ("computers", "Computers", 600, True), ("fans", "Fans", 100, False), ("projector", "Projector", 200, False), ("ac", "Air conditioning", 1000, False)],
    "CR2": [("lighting", "Lighting", 100, True), ("computers", "Computers", 600, True), ("fans", "Fans", 100, False), ("projector", "Projector", 200, False), ("ac", "Air conditioning", 1000, False)],
    "CR3": [("lighting", "Lighting", 100, True), ("computers", "Computers", 600, True), ("fans", "Fans", 100, False), ("projector", "Projector", 200, False), ("ac", "Air conditioning", 1000, False), ("instruments", "Instruments", 2000, False)],
}
LOAD_KEYS = tuple((room, item[0]) for room in ROOMS for item in LOADS[room])
ZONES = ("ICU", "Theatre", "Wards")


class ClassroomDemo:
    def __init__(self, clock=time.monotonic):
        self.capacity = 8000
        self.selected: str | None = None
        self.rfid: str | None = None
        self.gate = RestorationGate(clock)
        initial = (1 << len(LOAD_KEYS)) - 1
        self.gate.update(initial, (self.capacity, self.selected), range(len(LOAD_KEYS)))

    def _priority(self):
        selected = self.selected
        # Essential loads in every room come first; the scanned room leads ties.
        order = ([selected] if selected else []) + [r for r in ROOMS if r != selected]
        result = [(r, item) for r in order for item in LOADS[r] if item[3]]
        result += [(r, item) for r in order for item in LOADS[r] if not item[3] and r == selected]
        result += [(r, item) for r in ROOMS for item in LOADS[r] if not item[3] and r != selected]
        return result

    def snapshot(self):
        priority = self._priority()
        target: set[tuple[str, str]] = set()
        remaining = self.capacity
        for room, item in priority:
            key = (room, item[0])
            if item[2] <= remaining:
                target.add(key)
                remaining -= item[2]
        proposed = sum(1 << LOAD_KEYS.index(key) for key in target)
        applied = self.gate.update(proposed, (self.capacity, self.selected), range(len(LOAD_KEYS)))
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
            rooms.append({"id": cid, "name": f"Classroom {cid[-1]}", "rfid_active": self.rfid == cid, "loads": loads})
        requested = sum(x[2] for rows in LOADS.values() for x in rows)
        served_w = sum(x[2] for r in ROOMS for x in LOADS[r] if (r, x[0]) in current)
        return {"capacity_w": self.capacity, "requested_w": requested, "served_w": served_w,
                "shortfall_w": requested-served_w, "selected_classroom_id": self.selected,
                "rooms": rooms, "mode": "SIMULATED", "policy": "Classroom-only: essential lighting and computers first, selected room next, then deterministic optional loads."}

    def act(self, action: str, classroom_id: str | None):
        if action == "scan":
            self.selected = self.rfid = classroom_id
        elif action == "normal":
            self.capacity = 8000
        elif action == "overload":
            self.capacity = 3400
        elif action == "reset":
            clock = self.gate.clock
            self.__init__(clock)
        return self.snapshot()


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


def hospital_snapshot(scenario="normal"):
    transformers = []
    for i in range(1, 4):
        fixture = ((0.0, 40.0, 90.0, 20.0, True) if scenario == "upstream_loss"
                   else HOSPITAL_FAULT_FIXTURES.get(scenario, NORMAL_SENSORS) if i == 2
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
