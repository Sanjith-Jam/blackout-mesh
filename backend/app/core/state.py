import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Any

from app.schemas.snapshot import (
    SystemSnapshot, SourceInfo, SourceKind, HardwareLinkStatus,
    ServiceSnapshot, Tier, FacilityZones, HospitalZone, HospitalRoom,
    ClassroomZone, ClassroomInfo, RfidReaderStatus, RfidEventType,
    SystemEvent, FaultDiagnosis
)
from app.core.allocator import allocate, fixed_priority_mask, explain
from app.core.restoration import RestorationGate
from app.core.policy import AllocationPolicy
from app.activity.model import ActivityModel, FEATURES
from app.diagnosis.infer import FeederRating, ObservationWindow, diagnose_campus
from app.diagnosis.observations import validate as validate_observation
from app.simulation.sensors import CAMPUS_BUS, CAMPUS_FEEDERS, campus_readings, envelopes as sensor_envelopes
from app.core.safety import ActivityGuard, CAMPUS_PROTECTED_SERVICES, normalize_prediction, shortfall_status

SERVICE_CATALOG = [
    {"id": "L0", "name": "Hospital Essential Circuit", "tier": "T1", "feeder": "A", "watts": 2000, "zone": "hospital"},
    {"id": "L1", "name": "Emergency Lighting", "tier": "T1", "feeder": "A", "watts": 1000, "zone": "hospital"},
    {"id": "L2", "name": "Water Pump", "tier": "T2", "feeder": "A", "watts": 3000, "zone": "hospital"},
    {"id": "L3", "name": "Classroom 1", "tier": "T2", "feeder": "B", "watts": 2000, "zone": "classroom"},
    {"id": "L4", "name": "Classroom 2", "tier": "T2", "feeder": "B", "watts": 2000, "zone": "classroom"},
    {"id": "L5", "name": "Classroom 3", "tier": "T3", "feeder": "B", "watts": 4000, "zone": "classroom"},
]

HOSPITAL_ROOMS = [
    {"id": "HR1", "name": "Hospital Room 1", "lighting_service": "L0", "led_bit": 0},
    {"id": "HR2", "name": "Hospital Room 2", "lighting_service": "L0", "led_bit": 1},
    {"id": "HR3", "name": "Hospital Room 3", "lighting_service": "L0", "led_bit": 2},
]

CLASSROOMS = [
    {"id": "CR1", "name": "Classroom 1", "service_id": "L3", "led_bit": 3},
    {"id": "CR2", "name": "Classroom 2", "service_id": "L4", "led_bit": 4},
    {"id": "CR3", "name": "Classroom 3", "service_id": "L5", "led_bit": 5},
]

# Configurable RFID UID mapping. Replace with real UIDs during hardware registration.
DEFAULT_RFID_MAP = {
    "CARD_1_UID": "CR1",
    "CARD_2_UID": "CR2",
    "CARD_3_UID": "CR3",
}

RFID_SCAN_COOLDOWN_SECONDS = 2.0
NORMAL_SOURCE_CAPACITY_W = 14000

class GridState:
    _instance = None
    _init_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super(GridState, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        self._lock = threading.RLock()
        self.clock = time.monotonic
        self.published: Optional[SystemSnapshot] = None
        self.published_revision = 0
        self.tick_count = 0
        self.source_capacity_w = 14000
        self.feeder_limits_w = {"A": 6000, "B": 8000}
        self.feeder_available = {"A": True, "B": True}
        self.control_revision = 0
        self.active_classroom_id = None
        self.recent_rfid_scan = None
        self.last_rfid_scan_time = None
        self.last_rfid_uid = None
        self.classroom_load_events = {"CR1": False, "CR2": False, "CR3": False}
        self.rfid_map = DEFAULT_RFID_MAP.copy()
        self.indicator_confirmed_mask = None
        self.model = ActivityModel()
        self.activity = {c["id"]: {"state": "UNKNOWN", "score": None, "reason": "no sensor observation",
                                    "source": None, "observed_at": None, "recorded_at": None,
                                    "model_version": "unavailable", "priority": "UNKNOWN",
                                    "evidence": {key: None for key in FEATURES}}
                         for c in CLASSROOMS}
        self.software_mode = False
        self.replay_running = False
        self.replay_index = 0
        self.replay_length = 0
        self.activity_guard = ActivityGuard()
        self.activity_tokens = {c["id"]: 0 for c in CLASSROOMS}
        self.activity_received_monotonic = {c["id"]: None for c in CLASSROOMS}
        self.policy = AllocationPolicy()
        self.waiting_s = {}
        self.last_policy_tick = self.clock()
        self.allocation_explanation = {}
        self.last_allocation_mask = 0
        self.last_allocation_key = None
        self.proposed_mask = 0
        self.restoration_gate = RestorationGate(lambda: self.clock())
        self.events = []
        self.fault_diagnosis = None
        self.telemetry_window = ObservationWindow()
        self.telemetry_sequence = 0
        self.restoration_gate.update(0b111111, (self.source_capacity_w, tuple(sorted(self.feeder_limits_w.items())),
                                                  tuple(sorted(self.feeder_available.items())),), range(6))
        self.last_allocation_mask = 0b111111
        self._initialized = True
        self.tick()  # initial publication so the first read is never empty

    def add_event(self, event_type: str, desc: str):
        with self._lock:
            event = SystemEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                type=event_type,
                description=desc
            )
            self.events.append(event)
            if len(self.events) > 50:
                self.events.pop(0)

    def sample_telemetry(self, now: datetime):
        """Simulation side: turn the modeled campus state into bus/feeder sensor envelopes."""
        served = {"A": 0, "B": 0}
        for i, svc in enumerate(SERVICE_CATALOG):
            if self.last_allocation_mask & (1 << i):
                served[svc["feeder"]] += svc["watts"]
        self.telemetry_sequence += 1
        readings = campus_readings(self.source_capacity_w, self.feeder_available, served)
        for raw in sensor_envelopes(readings, self.telemetry_sequence, now):
            self.telemetry_window.add(validate_observation(raw, {CAMPUS_BUS, *CAMPUS_FEEDERS}, now))

    def compute_fault_diagnosis(self):
        """Sample telemetry, then diagnose from the observation window only (#4).

        A configured capacity limit is an explicit operating constraint, never inferred fault evidence.
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            self.sample_telemetry(now)
            result = diagnose_campus(self.telemetry_window, CAMPUS_BUS, list(CAMPUS_FEEDERS), FeederRating(), now)
            constraint = (f"Configured supply limit {self.source_capacity_w} W (operating constraint, not a diagnosed fault)."
                          if self.source_capacity_w < NORMAL_SOURCE_CAPACITY_W else None)
            if result["status"] == "NORMAL" and constraint is None:
                self.fault_diagnosis = None
                return
            self.fault_diagnosis = FaultDiagnosis(
                has_fault=result["has_fault"], diagnosis=result["diagnosis"], severity=result["severity"],
                status=result["status"], hypotheses=result["hypotheses"], affected_assets=result["affected_assets"],
                supply_constraint=constraint)


    def process_rfid_scan(self, uid: str) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
        with self._lock:
            now = time.time()
            if self.last_rfid_uid == uid and self.last_rfid_scan_time is not None:
                if now - self.last_rfid_scan_time < RFID_SCAN_COOLDOWN_SECONDS:
                    self.last_rfid_scan_time = now
                    return RfidEventType.DUPLICATE_SUPPRESSED.value, None, None, None
            
            self.last_rfid_uid = uid
            self.last_rfid_scan_time = now
            self.recent_rfid_scan = uid

            classroom_id = self.rfid_map.get(uid)
            if not classroom_id:
                self.active_classroom_id = None
                self.control_revision += 1
                self.add_event("RFID_SCAN", f"Unknown RFID card scanned: {uid}")
                return RfidEventType.UNKNOWN_CARD.value, None, None, None

            self.active_classroom_id = classroom_id
            self.control_revision += 1
            
            classroom = next((c for c in CLASSROOMS if c["id"] == classroom_id), None)
            if classroom:
                self.add_event("RFID_SCAN", f"RFID scan recognized for {classroom['name']}")
                return RfidEventType.CARD_RECOGNIZED.value, classroom_id, classroom["name"], classroom["service_id"]
            
            self.add_event("RFID_SCAN", f"RFID scan recognized for unknown classroom ID: {classroom_id}")
            return RfidEventType.CARD_RECOGNIZED.value, classroom_id, None, None

    def set_capacity(self, capacity_w: int):
        with self._lock:
            self.source_capacity_w = capacity_w
            self.control_revision += 1
            self.add_event("CAPACITY_CHANGE", f"Source capacity set to {capacity_w}W")

    def set_feeder(self, feeder: str, available: bool):
        with self._lock:
            if feeder in self.feeder_available:
                self.feeder_available[feeder] = available
                self.control_revision += 1
                status = "connected" if available else "disconnected"
                self.add_event("FEEDER_CHANGE", f"Feeder {feeder} {status}")

    def set_classroom_load(self, classroom_id: str, active: bool):
        with self._lock:
            if classroom_id in self.classroom_load_events:
                self.classroom_load_events[classroom_id] = active
                self.control_revision += 1
                status = "active" if active else "inactive"
                self.add_event("LOAD_CHANGE", f"Classroom {classroom_id} load became {status}")

    def record_activity(self, classroom_id, features, observed_at, source, recorded_at=None):
        """Store evidence and apply only the inference matching its current revision."""
        with self._lock:
            self.software_mode = True
            self.control_revision += 1
            self.activity_tokens[classroom_id] += 1
            current_revision = self.activity_tokens[classroom_id]
            self.activity[classroom_id] = {"state": "UNKNOWN", "score": None, "reason": "inference pending",
                                           "source": source, "observed_at": observed_at,
                                           "recorded_at": recorded_at, "model_version": "unavailable",
                                           "priority": "UNKNOWN", "evidence": dict(features)}
            age = max(0.0, (datetime.now(timezone.utc) - observed_at).total_seconds())
            self.activity_received_monotonic[classroom_id] = self.clock() - age
        return current_revision

    def apply_prediction(self, classroom_id, revision, prediction):
        with self._lock:
            if revision != self.activity_tokens[classroom_id]:
                return False
            pred = self.activity_guard.update(classroom_id, normalize_prediction(prediction), revision)
            state = pred["state"]
            priority = {"ACTIVE": "HIGH", "UNKNOWN": "MEDIUM", "INACTIVE": "LOW"}[state]
            self.activity[classroom_id].update(state=state, score=pred.get("score"), reason=pred.get("reason") or "inference failed",
                                                model_version=pred.get("model_version", "unavailable"), priority=priority,
                                                raw_state=pred["raw_state"], guard=pred["guard"])
            self.control_revision += 1
            return True

    def current_activity(self):
        activity = {cid: dict(value) for cid, value in self.activity.items()}
        now = self.clock()
        for cid, received in self.activity_received_monotonic.items():
            if received is not None and now - received > 600:
                activity[cid].update(state="UNKNOWN", score=None, reason="sensor evidence stale", priority="UNKNOWN",
                                     guard="conservative fallback: evidence older than 600 s")
        return activity

    def compute_allocation(self) -> int:
        with self._lock:
            now = self.clock()
            freshness = tuple(received is not None and now - received > 600
                              for received in self.activity_received_monotonic.values())
            requested = 0b111111
            if self.software_mode:
                requested = 0b111
                for c in CLASSROOMS:
                    if self.classroom_load_events[c["id"]]:
                        requested |= 1 << int(c["service_id"][1:])
            elapsed = max(0, now - self.last_policy_tick)
            self.last_policy_tick = now
            for bit, svc in enumerate(SERVICE_CATALOG):
                self.waiting_s[svc["id"]] = (self.waiting_s.get(svc["id"], 0) + elapsed
                    if requested & (1 << bit) and not self.last_allocation_mask & (1 << bit) else 0)
            cache_key = (self.control_revision, freshness, tuple(int(v) for v in self.waiting_s.values()) if self.policy.fairness_weight else ())
            if cache_key != self.last_allocation_key:
                self.proposed_mask = allocate(SERVICE_CATALOG, self.source_capacity_w, self.feeder_limits_w,
                                              self.feeder_available, requested, self.current_activity(),
                                              self.last_allocation_mask, self.policy, self.waiting_s)
                self.decision_previous_mask = self.last_allocation_mask
                self.decision_waiting_s = {key: int(value) for key, value in self.waiting_s.items()}
                self.decision_requested_mask = requested
                self.decision_activity = {cid: {"state": value["state"]} for cid, value in self.current_activity().items()}
                self.last_allocation_key = cache_key
            order = sorted(range(len(SERVICE_CATALOG)), key=lambda bit: (
                0 if bit == 0 else 1 if bit == 1 else
                2 if SERVICE_CATALOG[bit]["zone"] == "classroom" and self.current_activity()[CLASSROOMS[bit - 3]["id"]]["state"] == "ACTIVE" else
                3 if SERVICE_CATALOG[bit]["zone"] == "classroom" and self.current_activity()[CLASSROOMS[bit - 3]["id"]]["state"] == "UNKNOWN" else
                (2 if self.policy.name == "water_first" else 4) if bit == 2 else 5, bit))
            signature = (self.policy.model_dump_json(), self.source_capacity_w, tuple(sorted(self.feeder_limits_w.items())),
                         tuple(sorted(self.feeder_available.items())))
            gate_before = {k: v for k, v in vars(self.restoration_gate).items() if k != "clock"}
            self.last_allocation_mask = self.restoration_gate.update(self.proposed_mask, signature, order, now=now)
            explanation = explain(SERVICE_CATALOG, self.source_capacity_w, self.feeder_limits_w,
                self.feeder_available, self.decision_requested_mask,
                self.decision_activity, self.decision_previous_mask, self.policy, self.decision_waiting_s,
                self.proposed_mask, self.last_allocation_mask)
            if (self.allocation_explanation.get("decision_id") != explanation["decision_id"] or
                    self.allocation_explanation.get("control_revision") != self.control_revision):
                explanation["restoration_replay"] = {"before": gate_before, "now_s": now,
                    "signature": signature, "order": order}
                explanation["control_revision"] = self.control_revision
                self.allocation_explanation = explanation
            return self.last_allocation_mask

    def compute_indicator_command_mask(self, modeled_mask: int) -> int:
        with self._lock:
            mask = 0
            # Hospital rooms L0
            l0_served = bool((modeled_mask >> 0) & 1)
            if l0_served:
                for room in HOSPITAL_ROOMS:
                    mask |= (1 << room["led_bit"])
                    
            # Classroom logic
            if self.active_classroom_id:
                classroom = next((c for c in CLASSROOMS if c["id"] == self.active_classroom_id), None)
                if classroom:
                    cr_svc = classroom["service_id"]
                    svc_bit = int(cr_svc[1:])
                    svc_served = bool((modeled_mask >> svc_bit) & 1)
                    load_active = self.classroom_load_events.get(self.active_classroom_id, False)
                    
                    cr_svc_obj = next((s for s in SERVICE_CATALOG if s["id"] == cr_svc), None)
                    feeder_avail = False
                    if cr_svc_obj:
                        feeder_avail = self.feeder_available.get(cr_svc_obj["feeder"], False)
                    
                    if svc_served and load_active and feeder_avail:
                        mask |= (1 << classroom["led_bit"])
                        
            return mask

    def tick(self) -> SystemSnapshot:
        """Advance control (evidence freshness, allocation, staged restoration) and publish.

        This is the only place time-dependent state moves forward. Readers call build_snapshot().
        """
        with self._lock:
            modeled_mask = self.compute_allocation()
            self.compute_fault_diagnosis()
            candidate = self._project(modeled_mask)
            self.tick_count += 1
            if self.published is None or _content(candidate) != _content(self.published):
                self.published_revision += 1
                candidate.published_revision = self.published_revision
                self.published = candidate
            return self.published

    def build_snapshot(self) -> Optional[SystemSnapshot]:
        """Read-only: a copy of the last published snapshot, or None before the first tick.
        Never advances control."""
        with self._lock:
            return None if self.published is None else self.published.model_copy(deep=True)

    def _project(self, modeled_mask: int) -> SystemSnapshot:
        with self._lock:
            indicator_command = self.compute_indicator_command_mask(modeled_mask)
            requested_mask = 0b111111
            if self.software_mode:
                requested_mask = 0b111
                for c in CLASSROOMS:
                    if self.classroom_load_events[c["id"]]:
                        requested_mask |= 1 << int(c["service_id"][1:])
            
            services_out = []
            for svc in SERVICE_CATALOG:
                bit = int(svc["id"][1:])
                served = bool((modeled_mask >> bit) & 1)
                
                if served:
                    reason = "Served by allocation policy"
                elif self.proposed_mask & (1 << bit):
                    reason = "Waiting for simulated restoration delay"
                elif not requested_mask & (1 << bit):
                    reason = "No active load request"
                elif not self.feeder_available.get(svc["feeder"], False):
                    reason = f"Feeder {svc['feeder']} unavailable"
                else:
                    reason = "Excluded by priority or capacity limits"
                services_out.append(ServiceSnapshot(
                    id=svc["id"],
                    name=svc["name"],
                    tier=Tier(svc["tier"]),
                    feeder=svc["feeder"],
                    watts=svc["watts"],
                    requested=bool(requested_mask & (1 << bit)),
                    modeled_served=served,
                    indicator_confirmed=None,
                    model_reason=reason
                ))

            hospital_rooms = [
                HospitalRoom(id=r["id"], name=r["name"], lighting_service=r["lighting_service"], led_bit=r["led_bit"])
                for r in HOSPITAL_ROOMS
            ]
            
            classroom_infos = []
            for c in CLASSROOMS:
                cid = c["id"]
                is_registered = any(v == cid for v in self.rfid_map.values())
                cinfo = ClassroomInfo(
                    id=cid,
                    name=c["name"],
                    service_id=c["service_id"],
                    rfid_card_registered=is_registered,
                    led_bit=c["led_bit"],
                    load_event_active=self.classroom_load_events.get(cid, False)
                )
                classroom_infos.append(cinfo)
            
            zones = FacilityZones(
                hospital=HospitalZone(rooms=hospital_rooms),
                classroom=ClassroomZone(
                    active_classroom_id=self.active_classroom_id,
                    recent_rfid_scan=self.recent_rfid_scan,
                    rfid_reader_status=RfidReaderStatus.NOT_CONNECTED,
                    classrooms=classroom_infos
                )
            )

            activity = self.current_activity()

            return SystemSnapshot(
                control_revision=self.control_revision,
                generated_at=datetime.now(timezone.utc),
                source=SourceInfo(kind=SourceKind.SIMULATED, capacity_w=self.source_capacity_w),
                feeder_limits_w=self.feeder_limits_w.copy(),
                requested_mask=requested_mask,
                modeled_mask=modeled_mask,
                proposed_mask=self.proposed_mask,
                indicator_mask=None,
                indicator_command_mask=indicator_command,
                indicator_confirmed_mask=self.indicator_confirmed_mask,
                zones=zones,
                hardware_link=HardwareLinkStatus.NOT_CONNECTED,
                services=services_out,
                events=self.events.copy(),
                fault_diagnosis=self.fault_diagnosis,
                activity=activity,
                model=self.model.status(),
                replay={"running": self.replay_running, "index": self.replay_index, "length": self.replay_length},
                allocation={"objective": ", ".join(self.policy.objective_order),
                            "explanation": self.allocation_explanation,
                            "critical_shortfall_w": max(0, sum(s["watts"] for s in SERVICE_CATALOG[:2]) -
                                                         sum(SERVICE_CATALOG[i]["watts"] for i in range(2) if modeled_mask & (1 << i))),
                            "served_w": sum(s["watts"] for i, s in enumerate(SERVICE_CATALOG) if modeled_mask & (1 << i)),
                            "baseline_mask": fixed_priority_mask(SERVICE_CATALOG, self.source_capacity_w, self.feeder_limits_w,
                                                                 self.feeder_available, requested_mask),
                            "safety": shortfall_status(
                                sum(s["watts"] for i, s in enumerate(SERVICE_CATALOG)
                                    if s["id"] in CAMPUS_PROTECTED_SERVICES and requested_mask & (1 << i)),
                                sum(s["watts"] for i, s in enumerate(SERVICE_CATALOG)
                                    if s["id"] in CAMPUS_PROTECTED_SERVICES and modeled_mask & (1 << i)))}
            )


def _content(snapshot: SystemSnapshot) -> dict:
    """Snapshot fields that define state, excluding publication bookkeeping."""
    return snapshot.model_dump(exclude={"generated_at", "published_revision"})
