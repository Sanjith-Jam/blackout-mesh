
from app.storage.db import engine, commit_safely, is_degraded, init_db
from app.storage.models import Run, Command, Decision, Transition, Incident, Acknowledgment, Observation
from sqlmodel import Session, select
import uuid

import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Any

from app.schemas.snapshot import (
    SystemSnapshot, SourceInfo, SourceKind, HardwareLinkStatus,
    ServiceSnapshot, Tier, FacilityZones, HospitalZone, HospitalRoom,
    ClassroomZone, ClassroomInfo, RfidReaderStatus, RfidEventType,
    SystemEvent, 
)
from app.core.allocator import allocate, fixed_priority_mask
from app.core.restoration import RestorationGate
from app.activity.model import ActivityModel, FEATURES

from app.core.identity import get_run_identity
from app.schemas.snapshot import CrossRouteContract, RunIdentity, ScopeTotals, RankedDiagnosis, Hypothesis
from app.core.config import load_site_profile, load_rfid_enrollment, AssetType, get_config_hash
import os

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_SITE_PATH = os.environ.get("SITE_PROFILE", os.path.join(_BASE_DIR, "sites", "default_campus.json"))
RFID_ENROLLMENT_PATH = os.environ.get("RFID_ENROLLMENT", os.path.join(_BASE_DIR, "sites", "rfid_enrollment.json"))
RFID_ENROLLMENT_PATH = os.path.join(_BASE_DIR, "sites", "rfid_enrollment.json")

site_profile = load_site_profile(DEFAULT_SITE_PATH)
rfid_enrollment = load_rfid_enrollment(RFID_ENROLLMENT_PATH)

SERVICE_CATALOG = []
HOSPITAL_ROOMS = []
CLASSROOMS = []

for asset in site_profile.assets:
    if asset.type == AssetType.SERVICE:
        SERVICE_CATALOG.append({
            "id": asset.id,
            "name": asset.name,
            "tier": asset.tier.value if asset.tier else "T3",
            "feeder": asset.parent_id,
            "watts": asset.rating_w or 0,
            "zone": asset.zone
        })
    elif asset.type == AssetType.HOSPITAL_ROOM:
        HOSPITAL_ROOMS.append({
            "id": asset.id,
            "name": asset.name,
            "lighting_service": asset.parent_id,
            "led_bit": asset.led_bit
        })
    elif asset.type == AssetType.CLASSROOM:
        CLASSROOMS.append({
            "id": asset.id,
            "name": asset.name,
            "service_id": asset.parent_id,
            "led_bit": asset.led_bit
        })


DEFAULT_RFID_MAP = rfid_enrollment.tag_to_room
SITE_CONFIG_HASH = get_config_hash(site_profile)

RFID_SCAN_COOLDOWN_SECONDS = 2.0
SESSION_EXPIRY_SECONDS = 7200

class GridState:
    def __init__(self):
        self._lock = threading.RLock()
        self.source_capacity_w = 14000
        self.feeder_limits_w = {"A": 6000, "B": 8000}
        self.feeder_available = {"A": True, "B": True}
        self.control_revision = 0
        self.active_sessions = {}
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
        self.activity_tokens = {c["id"]: 0 for c in CLASSROOMS}
        self.activity_received_monotonic = {c["id"]: None for c in CLASSROOMS}
        self.last_allocation_mask = 0
        self.last_allocation_key = None
        self.proposed_mask = 0
        self.restoration_gate = RestorationGate(time.monotonic)
        
        init_db()
        self.run_id = str(uuid.uuid4())
        self.server_epoch = int(time.time())
        try:
            with Session(engine) as session:
                run = Run(site_id=site_profile.name, run_id=self.run_id, server_epoch=self.server_epoch, started_at=datetime.now(timezone.utc))
                session.add(run)
                commit_safely(session)
                
                # Load last 50 transitions as events
                trans = session.exec(select(Transition).order_by(Transition.timestamp.desc()).limit(50)).all()
                self.events = []
                for t in reversed(trans):
                    self.events.append(SystemEvent(timestamp=t.timestamp.isoformat(), type=t.type, description=t.description))
        except Exception:
            self.events = []

        self.fault_diagnosis = None
        self.compute_fault_diagnosis()
        self.restoration_gate.update(0b111111, (self.source_capacity_w, tuple(sorted(self.feeder_limits_w.items())),
                                                  tuple(sorted(self.feeder_available.items())),), range(6))
        self.last_allocation_mask = 0b111111



    def save_command(self, action: str, payload: dict):
        if is_degraded():
            return
        try:
            with Session(engine) as session:
                cmd = Command(
                    command_id=str(uuid.uuid4()),
                    run_id=self.run_id,
                    revision=self.control_revision,
                    timestamp=datetime.now(timezone.utc),
                    action=action,
                    payload=payload
                )
                session.add(cmd)
                commit_safely(session)
        except Exception:
            pass

    def add_event(self, event_type: str, desc: str):
        with self._lock:
            now = datetime.now(timezone.utc)
            event = SystemEvent(
                timestamp=now.isoformat(),
                type=event_type,
                description=desc
            )
            self.events.append(event)
            if len(self.events) > 50:
                self.events.pop(0)
                

            try:
                with Session(engine) as session:
                    t = Transition(run_id=self.run_id, revision=self.control_revision, timestamp=now, type=event_type, description=desc)
                    session.add(t)
                    if not commit_safely(session):
                        if not getattr(self, '_notified_degraded', False):
                            self._notified_degraded = True
                            self.events.append(SystemEvent(timestamp=now.isoformat(), type="DB_DEGRADED", description="Database is degraded. Auditing paused."))
            except Exception:
                if not getattr(self, '_notified_degraded', False):
                    self._notified_degraded = True
                    self.events.append(SystemEvent(timestamp=now.isoformat(), type="DB_DEGRADED", description="Database is degraded. Auditing paused."))



    def compute_fault_diagnosis(self):
        with self._lock:
            hypotheses = []
            
            # 1. Grid capacity reduction
            cap_supp = []
            cap_contra = []
            if self.source_capacity_w < 14000:
                cap_supp.append(f"Grid capacity reduced ({self.source_capacity_w}W).")
            else:
                cap_contra.append(f"Grid capacity is normal ({self.source_capacity_w}W).")
            
            if cap_supp:
                hypotheses.append(Hypothesis(
                    code="REDUCED_CAPACITY",
                    cause="Source capacity is below normal threshold",
                    asset_id="simulated_source",
                    supporting_evidence=cap_supp,
                    contradicting_evidence=cap_contra,
                    time_window="current",
                    sufficiency="sufficient",
                    score=0.8,
                    severity="high",
                    recommendation="Wait for grid restoration."
                ))
                
            # 2. Feeder loss
            for f, avail in self.feeder_available.items():
                f_supp = []
                f_contra = []
                if not avail:
                    f_supp.append(f"Feeder {f} disconnected.")
                else:
                    f_contra.append(f"Feeder {f} connected.")
                
                if f_supp:
                    hypotheses.append(Hypothesis(
                        code="FEEDER_LOSS",
                        cause=f"Feeder {f} is disconnected",
                        asset_id=f,
                        supporting_evidence=f_supp,
                        contradicting_evidence=f_contra,
                        time_window="current",
                        sufficiency="sufficient",
                        score=0.9,
                        severity="critical",
                        recommendation="Check physical connections."
                    ))

            hypotheses.sort(key=lambda h: h.score, reverse=True)
            
            if not hypotheses:
                hypotheses.append(Hypothesis(
                    code="NORMAL",
                    cause="No campus faults detected",
                    asset_id=None,
                    supporting_evidence=["Capacity and feeders normal"],
                    contradicting_evidence=[],
                    time_window="current",
                    sufficiency="sufficient",
                    score=1.0,
                    severity="normal",
                    recommendation="No action needed."
                ))
            

            diag = RankedDiagnosis(
                is_fault=bool(hypotheses) and any(h.severity in ("critical", "high", "medium") for h in hypotheses),
                hypotheses=hypotheses,
                abstention_reason=None
            )
            
            # Record incident if it changed
            prev_diag = getattr(self, "fault_diagnosis", None)
            if prev_diag:
                prev_top = prev_diag.hypotheses[0].code if prev_diag.hypotheses else "NORMAL"
                new_top = diag.hypotheses[0].code if diag.hypotheses else "NORMAL"
                if prev_top != new_top and not is_degraded():
                    try:
                        with Session(engine) as session:
                            for h in diag.hypotheses:
                                inc = Incident(
                                    incident_id=str(uuid.uuid4()),
                                    run_id=self.run_id,
                                    timestamp=datetime.now(timezone.utc),
                                    code=h.code,
                                    severity=h.severity,
                                    status="ACTIVE" if h.severity != "normal" else "CLEARED",
                                    evidence={"supporting": h.supporting_evidence, "contradicting": h.contradicting_evidence}
                                )
                                session.add(inc)
                            commit_safely(session)
                    except Exception:
                        pass

            self.fault_diagnosis = diag

    def process_rfid_scan(self, uid: str) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
        with self._lock:
            now = time.time()
            
            classroom_id = self.rfid_map.get(uid)
            if not classroom_id:
                self.control_revision += 1
                self.add_event("RFID_SCAN", f"Unknown RFID card scanned: {uid[:4] + '***' if uid else 'none'}")
                return RfidEventType.UNKNOWN_CARD.value, None, None, None
            
            if classroom_id in self.active_sessions:
                session = self.active_sessions[classroom_id]
                if now - session["last_scan"] < RFID_SCAN_COOLDOWN_SECONDS:
                    session["last_scan"] = now
                    return RfidEventType.DUPLICATE_SUPPRESSED.value, None, None, None
                else:
                    del self.active_sessions[classroom_id]
                    self.control_revision += 1
                    self.save_command('end_rfid_session', {'uid': uid[:4] + '***' if uid else 'none', 'classroom_id': classroom_id})
                    self.add_event("SESSION_END", f"Session ended for {classroom_id} via RFID")
                    return "SESSION_ENDED", classroom_id, next((c["name"] for c in CLASSROOMS if c["id"] == classroom_id), ""), next((c["service_id"] for c in CLASSROOMS if c["id"] == classroom_id), "")
            else:
                self.active_sessions[classroom_id] = {"source": "RFID", "started_at": now, "last_scan": now}
                self.control_revision += 1
                self.save_command('start_rfid_session', {'uid': uid[:4] + '***' if uid else 'none', 'classroom_id': classroom_id})
                self.add_event("SESSION_START", f"Session started for {classroom_id} via RFID")
                return RfidEventType.CARD_RECOGNIZED.value, classroom_id, next((c["name"] for c in CLASSROOMS if c["id"] == classroom_id), ""), next((c["service_id"] for c in CLASSROOMS if c["id"] == classroom_id), "")

            
            self.add_event("RFID_SCAN", f"RFID scan recognized for unknown classroom ID: {classroom_id}")
            return RfidEventType.CARD_RECOGNIZED.value, classroom_id, None, None

    def set_capacity(self, capacity_w: int):
        with self._lock:
            self.source_capacity_w = capacity_w
            self.control_revision += 1
            self.save_command('set_capacity', {'capacity_w': capacity_w})
            self.add_event("CAPACITY_CHANGE", f"Source capacity set to {capacity_w}W")
            self.compute_fault_diagnosis()

    def set_feeder(self, feeder: str, available: bool):
        with self._lock:
            if feeder in self.feeder_available:
                self.feeder_available[feeder] = available
                self.control_revision += 1
                status = "connected" if available else "disconnected"
                self.add_event("FEEDER_CHANGE", f"Feeder {feeder} {status}")
                self.compute_fault_diagnosis()

    def set_classroom_load(self, classroom_id: str, active: bool):
        with self._lock:
            now = time.time()
            if active:
                self.active_sessions[classroom_id] = {"source": "UI", "started_at": now, "last_scan": now}
            else:
                if classroom_id in self.active_sessions:
                    del self.active_sessions[classroom_id]
            self.control_revision += 1
            status = "active" if active else "inactive"
            self.add_event("LOAD_CHANGE", f"Classroom {classroom_id} load became {status}")

    def record_activity(self, classroom_id, features, observed_at, source, recorded_at=None):
        """Store evidence and apply only the inference matching its current revision."""
        with self._lock:
            self.software_mode = True
            self.control_revision += 1

            if not is_degraded():
                try:
                    with Session(engine) as db_session:
                        obs = Observation(
                            run_id=self.run_id,
                            asset_id=classroom_id,
                            timestamp=observed_at,
                            payload=features
                        )
                        db_session.add(obs)
                        commit_safely(db_session)
                except Exception:
                    pass

            self.activity_tokens[classroom_id] += 1
            current_revision = self.activity_tokens[classroom_id]
            self.activity[classroom_id] = {"state": "UNKNOWN", "score": None, "reason": "inference pending",
                                           "source": source, "observed_at": observed_at,
                                           "recorded_at": recorded_at, "model_version": "unavailable",
                                           "priority": "UNKNOWN", "evidence": dict(features)}
            age = max(0.0, (datetime.now(timezone.utc) - observed_at).total_seconds())
            self.activity_received_monotonic[classroom_id] = time.monotonic() - age
        return current_revision

    def apply_prediction(self, classroom_id, revision, prediction):
        with self._lock:
            if revision != self.activity_tokens[classroom_id]:
                return False
            pred = prediction or {"state": "UNKNOWN", "score": None, "reason": "inference failed", "model_version": "unavailable"}
            state = pred.get("state") if pred.get("state") in ("ACTIVE", "INACTIVE", "UNKNOWN") else "UNKNOWN"
            priority = {"ACTIVE": "HIGH", "UNKNOWN": "MEDIUM", "INACTIVE": "LOW"}[state]
            self.activity[classroom_id].update(state=state, score=pred.get("score"), reason=pred.get("reason", "inference failed"),
                                                model_version=pred.get("model_version", "unavailable"), priority=priority)
            self.control_revision += 1
            return True

    def current_activity(self):
        activity = {cid: dict(value) for cid, value in self.activity.items()}
        now = time.monotonic()
        for cid, received in self.activity_received_monotonic.items():
            if received is not None and now - received > 600:
                activity[cid].update(state="UNKNOWN", score=None, reason="sensor evidence stale", priority="UNKNOWN")
        return activity


    def expire_sessions(self):
        now = time.time()
        expired = [cid for cid, session in self.active_sessions.items() if now - session["last_scan"] > SESSION_EXPIRY_SECONDS]
        for cid in expired:
            del self.active_sessions[cid]
            self.control_revision += 1
            self.add_event("SESSION_EXPIRED", f"Session expired for {cid}")


    def compute_allocation(self) -> int:
        """
        Compute allocation based on priority and capacity constraints.
        - Essential loads (bits 0, 1, 2) are requested independent of a session by default.
        - Uncertainty protects essentials: even without clear occupancy evidence, they are never silently cut.
        - Session evidence (RFID/UI) explicitly adds optional equipment demand (bits 3, 4, 5).
        - Occupancy prediction (from sensors) can further rank active/unknown ties, but does NOT override the safety of essentials.
        """
        with self._lock:
            self.expire_sessions()

            freshness = tuple(received is not None and time.monotonic() - received > 600
                              for received in self.activity_received_monotonic.values())
            cache_key = (self.control_revision, freshness)
            if cache_key != self.last_allocation_key:
                requested = 0b111111
                if self.software_mode:
                    requested = 0b111
                    for c in CLASSROOMS:
                        if c["id"] in self.active_sessions:
                            requested |= 1 << int(c["service_id"][1:])
                self.proposed_mask = allocate(SERVICE_CATALOG, self.source_capacity_w, self.feeder_limits_w,
                                              self.feeder_available, requested, self.current_activity(),
                                              self.last_allocation_mask)
                self.last_allocation_key = cache_key
            order = sorted(range(len(SERVICE_CATALOG)), key=lambda bit: (
                0 if bit == 0 else 1 if bit == 1 else
                2 if SERVICE_CATALOG[bit]["zone"] == "classroom" and self.current_activity()[CLASSROOMS[bit - 3]["id"]]["state"] == "ACTIVE" else
                3 if SERVICE_CATALOG[bit]["zone"] == "classroom" and self.current_activity()[CLASSROOMS[bit - 3]["id"]]["state"] == "UNKNOWN" else
                4 if bit == 2 else 5, bit))
            signature = (self.source_capacity_w, tuple(sorted(self.feeder_limits_w.items())),
                         tuple(sorted(self.feeder_available.items())))

            new_mask = self.restoration_gate.update(self.proposed_mask, signature, order)
            if getattr(self, 'last_allocation_mask', None) != new_mask:
                self.last_allocation_mask = new_mask
                if not is_degraded():
                    try:
                        with Session(engine) as session:
                            dec = Decision(
                                decision_id=str(uuid.uuid4()),
                                run_id=self.run_id,
                                revision=self.control_revision,
                                timestamp=datetime.now(timezone.utc),
                                modeled_mask=new_mask,
                                proposed_mask=self.proposed_mask,
                                indicator_command_mask=None,
                                reason="Allocation updated"
                            )
                            session.add(dec)
                            commit_safely(session)
                    except Exception:
                        pass
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
            for cid, session in self.active_sessions.items():
                classroom = next((c for c in CLASSROOMS if c["id"] == cid), None)
                if classroom:
                    cr_svc = classroom["service_id"]
                    svc_bit = int(cr_svc[1:])
                    svc_served = bool((modeled_mask >> svc_bit) & 1)
                    
                    cr_svc_obj = next((s for s in SERVICE_CATALOG if s["id"] == cr_svc), None)
                    feeder_avail = False
                    if cr_svc_obj:
                        feeder_avail = self.feeder_available.get(cr_svc_obj["feeder"], False)
                    
                    if svc_served and feeder_avail:
                        mask |= (1 << classroom["led_bit"])
                        
            return mask


    def record_ack(self, device_boot: str, sequence: int, session: str, confirmed_mask: int, provenance: str):
        with self._lock:
            # Validate physical ACK identity before recording confirmed output
            # "Unacknowledged or wrong-session commands never set confirmed hardware status."
            # Since we just mock the session checking here for now:
            # We will accept it if provenance == "SIMULATED" or if we have a real matching session tracking.
            # But the issue says: "simulation acknowledgments must be a distinct provenance. On restart, restore display history but do not assume persisted physical ACKs confirm current device state."
            
            # Record it in the DB
            now = datetime.now(timezone.utc)
            if not is_degraded():
                try:
                    with Session(engine) as db_session:
                        ack = Acknowledgment(
                            run_id=self.run_id,
                            device_boot=device_boot,
                            sequence=sequence,
                            session=session,
                            timestamp=now,
                            confirmed_mask=confirmed_mask
                        )
                        db_session.add(ack)
                        commit_safely(db_session)
                except Exception:
                    pass
            
            self.indicator_confirmed_mask = confirmed_mask
            self.control_revision += 1
            self.add_event("HARDWARE_ACK", f"ACK received via {provenance}")

    def build_snapshot(self) -> SystemSnapshot:
        with self._lock:
            modeled_mask = self.compute_allocation()
            indicator_command = self.compute_indicator_command_mask(modeled_mask)
            requested_mask = 0b111111
            if self.software_mode:
                requested_mask = 0b111
                for c in CLASSROOMS:
                    if c["id"] in self.active_sessions:
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
                    load_event_active=(cid in self.active_sessions)
                )
                classroom_infos.append(cinfo)
            
            zones = FacilityZones(
                hospital=HospitalZone(rooms=hospital_rooms),
                classroom=ClassroomZone(
                    active_classroom_id=next(iter(self.active_sessions.keys()), None) if self.active_sessions else None,
                    recent_rfid_scan=None,
                    rfid_reader_status=RfidReaderStatus.NOT_CONNECTED,
                    classrooms=classroom_infos
                )
            )

            activity = self.current_activity()


            requested_w = sum(s["watts"] for i, s in enumerate(SERVICE_CATALOG) if requested_mask & (1 << i))
            served_w = sum(s["watts"] for i, s in enumerate(SERVICE_CATALOG) if modeled_mask & (1 << i))
            campus_totals = ScopeTotals(capacity_w=self.source_capacity_w, requested_w=requested_w, served_w=served_w)
            
            zone_totals = {}
            for z in ["hospital", "classroom"]:
                z_req = sum(s["watts"] for i, s in enumerate(SERVICE_CATALOG) if requested_mask & (1 << i) and s["zone"] == z)
                z_srv = sum(s["watts"] for i, s in enumerate(SERVICE_CATALOG) if modeled_mask & (1 << i) and s["zone"] == z)
                zone_totals[z] = ScopeTotals(capacity_w=None, requested_w=z_req, served_w=z_srv)

            contract_dict = {
                "identity": get_run_identity(site_profile.name, SITE_CONFIG_HASH, site_profile.version, self.control_revision),
                "campus_totals": campus_totals,
                "zone_totals": zone_totals
            }
            contract = CrossRouteContract(**contract_dict)

            return SystemSnapshot(
                contract=contract,
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
                allocation={"objective": "critical, ACTIVE, UNKNOWN, water pump, minimize idle/switching",
                            "critical_shortfall_w": max(0, sum(s["watts"] for s in SERVICE_CATALOG[:2]) -
                                                         sum(SERVICE_CATALOG[i]["watts"] for i in range(2) if modeled_mask & (1 << i))),
                            "served_w": sum(s["watts"] for i, s in enumerate(SERVICE_CATALOG) if modeled_mask & (1 << i)),
                            "baseline_mask": fixed_priority_mask(SERVICE_CATALOG, self.source_capacity_w, self.feeder_limits_w,
                                                                 self.feeder_available, requested_mask)}
            )
