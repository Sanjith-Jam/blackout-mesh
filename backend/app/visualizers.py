"""Independent synthetic classroom and hospital demos."""
from __future__ import annotations

import time
from app.core.restoration import RestorationGate

from app.core.identity import get_run_identity
from app.core.state import GridState, SITE_CONFIG_HASH, site_profile
from app.core.config import load_site_profile, AssetType
import os

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SITE_PATH = os.environ.get("SITE_PROFILE", os.path.join(_BASE_DIR, "sites", "default_campus.json"))
site_profile = load_site_profile(DEFAULT_SITE_PATH)

ROOMS = []
LOADS = {}
ZONES = []
TRANSFORMERS_CONFIG = []

for asset in site_profile.assets:
    if asset.type == AssetType.CLASSROOM:
        ROOMS.append(asset.id)
        LOADS[asset.id] = []
    elif asset.type == AssetType.TRANSFORMER:
        ZONES.append(asset.zone)
        TRANSFORMERS_CONFIG.append({
            "id": asset.id,
            "name": asset.name,
            "zone": asset.zone,
            "rated_current_a": float(asset.rating_w or 100.0)
        })

for asset in site_profile.assets:
    if asset.type == AssetType.LOAD and asset.parent_id in LOADS:
        # id like L_CR1_lighting -> strip L_CR1_ to get 'lighting'
        short_id = asset.id.split("_", 2)[-1]
        LOADS[asset.parent_id].append((short_id, asset.name, asset.rating_w, asset.essential))

ROOMS = tuple(ROOMS)
ZONES = tuple(ZONES)
LOAD_KEYS = tuple((room, item[0]) for room in ROOMS for item in LOADS[room])



class ClassroomDemo:
    def __init__(self, clock=time.monotonic):
        self.capacity = 8000
        self.active_rooms = set()
        self.gate = RestorationGate(clock)
        initial = (1 << len(LOAD_KEYS)) - 1
        self.gate.update(initial, (self.capacity, tuple(sorted(self.active_rooms))), range(len(LOAD_KEYS)))

    def _priority(self):
        # Essential loads in every room come first; scanned rooms lead ties.
        active = sorted(list(self.active_rooms))
        inactive = [r for r in ROOMS if r not in active]
        order = active + inactive
        
        result = [(r, item) for r in order for item in LOADS[r] if item[3]]
        for a in active:
            result += [(a, item) for item in LOADS[a] if not item[3]]
        for i in inactive:
            result += [(i, item) for item in LOADS[i] if not item[3]]
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
        applied = self.gate.update(proposed, (self.capacity, tuple(sorted(self.active_rooms))), range(len(LOAD_KEYS)))
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
            rooms.append({"id": cid, "name": f"Classroom {cid[-1]}", "rfid_active": cid in self.active_rooms, "loads": loads})
        requested = sum(x[2] for rows in LOADS.values() for x in rows)
        served_w = sum(x[2] for r in ROOMS for x in LOADS[r] if (r, x[0]) in current)

        identity = get_run_identity(site_profile.name, SITE_CONFIG_HASH, site_profile.version, GridState().control_revision)
        contract = {
            "identity": identity,
            "zone_totals": {
                "classroom": {
                    "capacity_w": self.capacity,
                    "requested_w": requested,
                    "served_w": served_w
                }
            }
        }
        return {"contract": contract, "capacity_w": self.capacity, "requested_w": requested, "served_w": served_w,
                "shortfall_w": requested-served_w, "selected_classroom_id": next(iter(self.active_rooms)) if self.active_rooms else None,
                "rooms": rooms, "mode": "SIMULATED", "policy": "Classroom-only: essential lighting and computers first, selected room next, then deterministic optional loads."}

    def act(self, action: str, classroom_id: str | None):
        if action == "scan" and classroom_id:
            self.active_rooms.add(classroom_id)
        elif action == "unscan" and classroom_id:
            self.active_rooms.discard(classroom_id)
        elif action == "normal":
            self.capacity = 8000
        elif action == "overload":
            self.capacity = 3400
        elif action == "reset":
            clock = self.gate.clock
            self.__init__(clock)
        return self.snapshot()


def diagnose(rated_current_a, current_a, temperature_c, input_voltage_v, output_voltage_v, cooling_ok):
    missing = [name for name, value in (("current", current_a), ("temperature", temperature_c),
               ("input voltage", input_voltage_v), ("output voltage", output_voltage_v), ("cooling", cooling_ok)) if value is None]
    
    hypotheses = []
    
    if missing:
        hypotheses.append({
            "code": "UNKNOWN",
            "cause": "Insufficient sensor evidence",
            "severity": "unknown", "time_window": "current",
            "score": 0.0,
            "supporting_evidence": ["Missing: " + ", ".join(missing)],
            "contradicting_evidence": [],
            "sufficiency": "insufficient",
            "recommendation": "Restore sensor telemetry before diagnosing."
        })
        # If missing critical things, maybe we abstain. But let's evaluate others if possible.
    
    # 1. UPSTREAM_LOSS
    up_supp = []
    up_contra = []
    if input_voltage_v is not None:
        if input_voltage_v < 180: up_supp.append(f"Input {input_voltage_v:.1f} V is below 180 V")
        else: up_contra.append(f"Input {input_voltage_v:.1f} V is normal")
    if output_voltage_v is not None:
        if output_voltage_v < 100: up_supp.append(f"Output {output_voltage_v:.1f} V is below 100 V")
        else: up_contra.append(f"Output {output_voltage_v:.1f} V is normal")
        
    if up_supp and not up_contra:
        hypotheses.append({
            "code": "UPSTREAM_LOSS",
            "cause": "Possible upstream supply loss",
            "severity": "critical", "time_window": "current",
            "score": 0.8,
            "supporting_evidence": up_supp,
            "contradicting_evidence": up_contra,
            "sufficiency": "sufficient",
            "recommendation": "Check the upstream supply and incoming connections."
        })
        
    # 2. OVERLOAD
    ov_supp = []
    ov_contra = []
    if current_a is not None:
        if current_a > rated_current_a * 1.1: ov_supp.append(f"Current {current_a:.1f} A exceeds overload threshold {rated_current_a * 1.1:.1f} A")
        else: ov_contra.append(f"Current {current_a:.1f} A is within limits")
        
    if ov_supp:
        hypotheses.append({
            "code": "OVERLOAD",
            "cause": "Current exceeds the configured rating threshold",
            "severity": "high", "time_window": "current",
            "score": 0.9,
            "supporting_evidence": ov_supp,
            "contradicting_evidence": ov_contra,
            "sufficiency": "sufficient",
            "recommendation": "Review connected demand and verify with qualified protection equipment."
        })
        
    # 3. COOLING_FAILURE
    cf_supp = []
    cf_contra = []
    if temperature_c is not None:
        if temperature_c >= 80: cf_supp.append(f"Temperature {temperature_c:.1f} °C exceeds hot threshold 80 °C")
        else: cf_contra.append(f"Temperature {temperature_c:.1f} °C is normal")
    if cooling_ok is not None:
        if not cooling_ok: cf_supp.append("Cooling reported failed")
        else: cf_contra.append("Cooling reported operational")
        
    if temperature_c is not None and temperature_c >= 80:
        if cooling_ok is False:
            hypotheses.append({
                "code": "COOLING_FAILURE",
                "cause": "Elevated temperature with cooling reported failed",
                "severity": "high", "time_window": "current",
                "score": 0.85,
                "supporting_evidence": cf_supp,
                "contradicting_evidence": cf_contra,
                "sufficiency": "sufficient",
                "recommendation": "Inspect cooling equipment and temperature using approved procedures."
            })
        elif cooling_ok is None:
            hypotheses.append({
                "code": "AMBIGUOUS_THERMAL_FAULT",
                "cause": "Elevated temperature but cooling status is unknown",
                "severity": "unknown", "time_window": "current",
                "score": 0.5,
                "supporting_evidence": cf_supp,
                "contradicting_evidence": cf_contra,
                "sufficiency": "ambiguous",
                "recommendation": "Check cooling system status."
            })
        
    # Sort hypotheses by score descending
    hypotheses.sort(key=lambda x: x["score"], reverse=True)
    
    # If no hypotheses and not missing, it's NORMAL
    if not hypotheses:
        hypotheses.append({
            "code": "NORMAL",
            "cause": "No configured demo fault found",
            "severity": "normal", "time_window": "current",
            "score": 1.0,
            "supporting_evidence": ["All available sensors within normal limits"],
            "contradicting_evidence": [],
            "sufficiency": "sufficient",
            "recommendation": "No action required."
        })
        
    # We now return the full ranked array of hypotheses.
    # To maintain backward compatibility with old `diagnosis` for now, we can wrap it.
    # The requirement asks to Expose the ranked result. Let's return a dict with hypotheses.
    return {
        "code": hypotheses[0]["code"],
        "cause": hypotheses[0]["cause"],
        "severity": hypotheses[0]["severity"],
        "evidence": hypotheses[0]["supporting_evidence"],
        "recommendation": hypotheses[0]["recommendation"],
        "hypotheses": hypotheses
    }

    if input_voltage_v < 180 and output_voltage_v < 100:
        return {"code": "UPSTREAM_LOSS", "cause": "Possible upstream supply loss", "severity": "critical", "time_window": "current", "evidence": evidence, "recommendation": "Check the upstream supply and incoming connections."}
    if current_a > rated_current_a * 1.1:
        return {"code": "OVERLOAD", "cause": "Current exceeds the configured rating threshold", "severity": "high", "time_window": "current", "evidence": evidence, "recommendation": "Review connected demand and verify with qualified protection equipment."}
    if temperature_c >= 80 and not cooling_ok:
        return {"code": "COOLING_FAILURE", "cause": "Elevated temperature with cooling reported failed", "severity": "high", "time_window": "current", "evidence": evidence, "recommendation": "Inspect cooling equipment and temperature using approved procedures."}
    if temperature_c >= 80:
        return {"code": "HIGH_TEMPERATURE", "cause": "Elevated transformer temperature", "severity": "medium", "evidence": evidence, "recommendation": "Check loading, ventilation and sensor readings."}
    return {"code": "NORMAL", "cause": "No configured demo threshold exceeded", "severity": "normal", "time_window": "current", "evidence": evidence, "recommendation": "Continue monitoring."}


NORMAL_SENSORS = (45.0, 58.0, 230.0, 220.0, True)
HOSPITAL_FAULT_FIXTURES = {
    "overload": (130.0, 72.0, 230.0, 218.0, True),
    "cooling_failure": (45.0, 91.0, 230.0, 220.0, False),
    "missing_sensor": (None, 55.0, 230.0, 220.0, True),
}


def hospital_snapshot(scenario="normal"):
    transformers = []
    for i, tx in enumerate(TRANSFORMERS_CONFIG):
        fixture = ((0.0, 40.0, 90.0, 20.0, True) if scenario == "upstream_loss"
                   else HOSPITAL_FAULT_FIXTURES.get(scenario, NORMAL_SENSORS) if i == 1
                   else NORMAL_SENSORS)
        current, temp, vin, vout, cooling = fixture
        sensors = {"current_a": current, "temperature_c": temp, "input_voltage_v": vin,
                   "output_voltage_v": vout, "cooling_ok": cooling}
        diagnosis = diagnose(tx["rated_current_a"], **sensors)
        transformers.append({"id": tx["id"], "name": tx["name"], "zone": tx["zone"],
                             "rated_current_a": tx["rated_current_a"], "sensors": sensors, "diagnosis": diagnosis,
                             "energized": vout is not None and vout >= 100.0})

    identity = get_run_identity(site_profile.name, SITE_CONFIG_HASH, site_profile.version, GridState().control_revision)
    contract = {
        "identity": identity,
        "zone_totals": {
            "hospital": {
                "capacity_w": None,
                "requested_w": 0,
                "served_w": 0
            }
        }
    }
    return {"contract": contract, "mode": "SIMULATED", "transformers": transformers,
            "summary": "Synthetic sensor diagnosis for demonstration; thresholds are not certified protection settings."}
