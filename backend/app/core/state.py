
from app.storage.db import Storage
from app.storage.models import Run, Command, Decision, Transition, Incident, Acknowledgment, Observation
from sqlmodel import Session, select
import uuid
import logging

import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Any

from app.schemas.snapshot import (
    SystemSnapshot, SourceInfo, SourceKind, HardwareLinkStatus,
    ServiceSnapshot, Tier, FacilityZones, HospitalZone, HospitalRoom,
    ClassroomZone, ClassroomInfo, RfidReaderStatus, RfidEventType,
    SystemEvent, FaultDiagnosis,
)
from app.core.allocator import allocate, fixed_priority_mask, explain
from app.core.edges import edge as power_edge
from app.core.restoration import RestorationGate
from app.core.policy import AllocationPolicy
from app.activity.model import ActivityModel, FEATURES
from app.diagnosis.infer import FeederRating, ObservationWindow, diagnose_campus
from app.diagnosis.observations import validate as validate_observation
from app.simulation.sensors import CAMPUS_BUS, CAMPUS_FEEDERS, campus_readings, envelopes as sensor_envelopes
from app.core.safety import ActivityGuard, CAMPUS_PROTECTED_SERVICES, RankDwell, normalize_prediction, shortfall_status

from app.schemas.snapshot import CrossRouteContract, ScopeTotals
from app.core.active_site import CATALOG, rfid_enrollment, site_profile

log = logging.getLogger(__name__)

SERVICE_CATALOG = CATALOG.services
HOSPITAL_ROOMS = CATALOG.hospital_rooms
CLASSROOMS = CATALOG.classrooms
CLASSROOM_IDS = {c["id"] for c in CLASSROOMS}
SERVICE_BIT = {s["id"]: i for i, s in enumerate(SERVICE_CATALOG)}
ALL_SERVICES_MASK = (1 << len(SERVICE_CATALOG)) - 1
# Services requested whatever the classroom sessions say (the hospital feeder's services).
BASE_REQUESTED_MASK = sum(1 << i for i, s in enumerate(SERVICE_CATALOG) if s["zone"] != "classroom")

# Cards enrolled for rooms this site does not have are ignored rather than mapped to nothing.
DEFAULT_RFID_MAP = {uid: room for uid, room in rfid_enrollment.tag_to_room.items() if room in CLASSROOM_IDS}
SITE_CONFIG_HASH = CATALOG.config_hash

RFID_SCAN_COOLDOWN_SECONDS = 2.0
SESSION_EXPIRY_SECONDS = 7200
NORMAL_SOURCE_CAPACITY_W = CATALOG.source_capacity_w

class GridState:
    def __init__(self, storage=None):
        self._lock = threading.RLock()
        self.clock = time.monotonic
        self.published: Optional[SystemSnapshot] = None
        self.published_revision = 0
        self.tick_count = 0
        self.source_capacity_w = NORMAL_SOURCE_CAPACITY_W
        self.feeder_limits_w = dict(CATALOG.feeder_limits_w)
        self.feeder_available = {f: True for f in CATALOG.feeder_limits_w}
        self.control_revision = 0
        self.active_sessions = {}
        self.session_event_ids = {}
        self.last_session_event_at = {}
        self.rfid_map = DEFAULT_RFID_MAP.copy()
        self.indicator_confirmed_mask = None
        self.model = ActivityModel()
        self.activity = {c["id"]: {"state": "UNKNOWN", "score": None, "reason": "no sensor observation",
                                    "source": None, "observed_at": None, "recorded_at": None,
                                    "model_version": "unavailable", "priority": "UNKNOWN",
                                    "evidence": {key: None for key in FEATURES}}
                         for c in CLASSROOMS}
        self.software_mode = False
        # Classroom leaf decision per feeder B service, set by the site authority (#33):
        # {service_id: {"requested_w", "commanded_w", "served_w"}}. None when GridState runs alone.
        self.feeder_b_leaves = None
        self.replay_running = False
        self.replay_index = 0
        self.replay_length = 0
        self.activity_guard = ActivityGuard()
        self.rank_dwell = RankDwell()
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

        self.storage = storage or Storage()
        self.history = None
        self.pending_command_identity = None
        self.storage.init()
        self.run_id = str(uuid.uuid4())
        self.server_epoch = int(time.time())
        try:
            with Session(self.storage.engine) as session:
                run = Run(site_id=site_profile.name, run_id=self.run_id, server_epoch=self.server_epoch, started_at=datetime.now(timezone.utc))
                session.add(run)
                self.storage.commit(session)

                # Load last 50 transitions as events
                trans = session.exec(select(Transition).where(Transition.run_id == self.run_id)
                                     .order_by(Transition.timestamp.desc()).limit(50)).all()
                self.events = []
                for t in reversed(trans):
                    self.events.append(SystemEvent(timestamp=t.timestamp.isoformat(), type=t.type, description=t.description))
        except Exception:
            self.events = []

        self.fault_diagnosis = None
        self._diagnostic_signature = None
        self.telemetry_window = ObservationWindow()
        self.telemetry_sequence = 0
        self._active_incidents = {}
        self.restoration_gate.update(ALL_SERVICES_MASK, (self.source_capacity_w, tuple(sorted(self.feeder_limits_w.items())),
                                                  tuple(sorted(self.feeder_available.items())),), range(len(SERVICE_CATALOG)))
        self.last_allocation_mask = ALL_SERVICES_MASK
        self._initialized = True
        self.tick()  # initial publication so the first read is never empty



    def identity(self):
        return dict(site_id=site_profile.name, run_id=self.run_id, server_epoch=self.server_epoch,
            config_hash=SITE_CONFIG_HASH, catalog_version=site_profile.version,
            policy_version=self.policy.version, model_version=self.model.status()["model_version"],
            state_revision=self.published_revision, observation_time=self.published.generated_at.isoformat()
                if self.published else datetime.now(timezone.utc).isoformat())

    def save_command(self, action: str, payload: dict, command_id: str | None = None):
        if self.storage.degraded:
            return False
        try:
            command_id = command_id or str(uuid.uuid4())
            with Session(self.storage.engine) as session:
                cmd = Command(
                    command_id=command_id,
                    run_id=self.run_id,
                    revision=self.control_revision,
                    timestamp=datetime.now(timezone.utc),
                    action=action,
                    payload=payload
                )
                session.add(cmd)
                if not self.storage.commit(session):
                    return False
                self.pending_command_identity = {"command_id": command_id, "run_id": self.run_id,
                                                 "action": action, "revision": self.control_revision}
                return self.pending_command_identity
        except Exception:
            log.exception("Command audit write failed")
            return False

    def add_event(self, event_type: str, desc: str, metadata=None):
        with self._lock:
            now = datetime.now(timezone.utc)
            event = SystemEvent(
                event_id=str(uuid.uuid4()),
                run_id=self.history.run_id if self.history else None,
                revision=self.control_revision,
                timestamp=now.isoformat(),
                type=event_type,
                description=desc
            )
            if self.history:
                try:
                    self.history.event(event, self.history_inputs() | (metadata or {}))
                except Exception:
                    log.exception("History event recording failed; live state transition continues")
            self.events.append(event)
            if len(self.events) > 50:
                self.events.pop(0)


            try:
                with Session(self.storage.engine) as session:
                    t = Transition(run_id=self.run_id, revision=self.control_revision, timestamp=now, type=event_type, description=desc)
                    session.add(t)
                    if not self.storage.commit(session):
                        if not getattr(self, '_notified_degraded', False):
                            self._notified_degraded = True
                            self.events.append(SystemEvent(timestamp=now.isoformat(), type="DB_DEGRADED", description="Database is degraded. Auditing paused."))
            except Exception:
                if not getattr(self, '_notified_degraded', False):
                    self._notified_degraded = True
                    self.events.append(SystemEvent(timestamp=now.isoformat(), type="DB_DEGRADED", description="Database is degraded. Auditing paused."))



    def sample_telemetry(self, now: datetime):
        """Simulation side: turn the modeled campus state into bus/feeder sensor envelopes."""
        served = {"A": 0, "B": 0}
        rows = self.service_watts(self.last_allocation_mask, self.proposed_mask, 0)
        for svc, (_, _, served_w) in zip(SERVICE_CATALOG, rows):
            served[svc["feeder"]] += served_w
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
            self._sync_incidents(result.get("hypotheses", []))
            constraint = (f"Configured supply limit {self.source_capacity_w} W (operating constraint, not a diagnosed fault)."
                          if self.source_capacity_w < NORMAL_SOURCE_CAPACITY_W else None)
            if result["status"] == "NORMAL" and constraint is None:
                self.fault_diagnosis = None
                return
            self.fault_diagnosis = FaultDiagnosis(
                has_fault=result["has_fault"], diagnosis=result["diagnosis"], severity=result["severity"],
                status=result["status"], hypotheses=result["hypotheses"], affected_assets=result["affected_assets"],
                supply_constraint=constraint)

    def _sync_incidents(self, hypotheses):
        current = {}
        ranked = []
        for rank, hypothesis in enumerate(hypotheses, 1):
            item = hypothesis.model_dump(mode="json") if hasattr(hypothesis, "model_dump") else dict(hypothesis)
            key = (item.get("code", "UNKNOWN"), item.get("asset_id", "unknown"))
            item["rank"] = rank
            current[key] = item
            ranked.append(item)
        signature = tuple((item["code"], item["asset_id"], item.get("confirmation"), item.get("severity"),
                           item.get("sufficiency")) for item in ranked)
        if self.storage.degraded:
            return
        if current.keys() == self._active_incidents.keys() and signature == self._diagnostic_signature:
            return
        now = datetime.now(timezone.utc)
        active = dict(self._active_incidents)
        try:
            with Session(self.storage.engine) as session:
                for key, incident_id in active.items():
                    if key in current:
                        continue
                    incident = session.exec(select(Incident).where(Incident.incident_id == incident_id)).first()
                    if incident is not None:
                        incident.status = "RESOLVED"
                        session.add(incident)
                next_active = {}
                for key, evidence in current.items():
                    incident_id = active.get(key)
                    if incident_id is None:
                        incident_id = str(uuid.uuid4())
                        session.add(Incident(incident_id=incident_id, run_id=self.run_id, timestamp=now,
                            code=key[0], severity=str(evidence.get("severity", "unknown")), status="OPEN",
                            evidence=evidence | {"asset_id": key[1]}))
                    else:
                        incident = session.exec(select(Incident).where(Incident.incident_id == incident_id)).first()
                        if incident is not None:
                            incident.severity = str(evidence.get("severity", "unknown"))
                            incident.evidence = evidence | {"asset_id": key[1]}
                            session.add(incident)
                    next_active[key] = incident_id
                if not self.storage.commit(session):
                    return
            for key in active.keys() - current.keys():
                self.add_event("INCIDENT_RESOLVED", f"{key[0]} resolved for {key[1]}")
            for key in current.keys() - active.keys():
                self.add_event("INCIDENT_OPENED", f"{key[0]} detected for {key[1]}")
            self._active_incidents = next_active
            previous_signature = self._diagnostic_signature
            if signature != previous_signature:
                self._diagnostic_signature = signature
                if ranked or previous_signature is not None:
                    summary = ", ".join(f"#{h['rank']} {h['code']} at {h['asset_id']}" for h in ranked) or "No supported hypotheses"
                    self.add_event("DIAGNOSIS_UPDATED", f"Ranked telemetry diagnosis: {summary}",
                                   {"ranked_hypotheses": ranked})
        except Exception:
            log.exception("Incident history write failed")

    def history_inputs(self):
        return {"capacity_w": self.source_capacity_w, "feeder_limits_w": self.feeder_limits_w.copy(),
                "feeder_available": self.feeder_available.copy(), "active_sessions": sorted(self.active_sessions),
                "command_identity": self.pending_command_identity,
                "activity": self.current_activity(), "catalog": SERVICE_CATALOG,
                "model_identity": {key: getattr(self.model, "_manifest", {}).get(key) for key in
                                   ("model_version", "sha256", "features", "decision_threshold", "abstain_margin")}}


    def _cached_session_event(self, event_id, fingerprint):
        if not event_id or event_id not in self.session_event_ids:
            return None
        previous_fingerprint, result = self.session_event_ids[event_id]
        if previous_fingerprint != fingerprint:
            raise ValueError("event_id was already used for a different session event")
        return result

    def _remember_session_event(self, event_id, fingerprint, result):
        if event_id:
            self.session_event_ids[event_id] = (fingerprint, result)
            if len(self.session_event_ids) > 2048:
                self.session_event_ids.pop(next(iter(self.session_event_ids)))

    def process_rfid_scan(self, uid: str, event_id: str | None = None, event_time: datetime | None = None) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
        with self._lock:
            now = time.time()
            classroom_id = self.rfid_map.get(uid)
            fingerprint = ("rfid", classroom_id)
            cached = self._cached_session_event(event_id, fingerprint)
            if cached is not None:
                return cached
            if not classroom_id:
                self.control_revision += 1
                self.add_event("RFID_SCAN", "Unknown RFID card scanned")
                result = (RfidEventType.UNKNOWN_CARD.value, None, None, None)
                self._remember_session_event(event_id, fingerprint, result)
                return result
            if event_time is not None:
                if event_time.tzinfo is None or event_time.astimezone(timezone.utc).timestamp() <= self.last_session_event_at.get(classroom_id, 0):
                    raise ValueError("stale or out-of-order session event")

            if classroom_id in self.active_sessions:
                session = self.active_sessions[classroom_id]
                if now - session["last_scan"] < RFID_SCAN_COOLDOWN_SECONDS:
                    session["last_scan"] = now
                    if event_time is not None:
                        self.last_session_event_at[classroom_id] = event_time.astimezone(timezone.utc).timestamp()
                    result = (RfidEventType.DUPLICATE_SUPPRESSED.value, None, None, None)
                    self._remember_session_event(event_id, fingerprint, result)
                    return result
                else:
                    self.set_classroom_load(classroom_id, False, source="RFID", event_time=event_time)
                    result = ("SESSION_ENDED", classroom_id, next((c["name"] for c in CLASSROOMS if c["id"] == classroom_id), ""), next((c["service_id"] for c in CLASSROOMS if c["id"] == classroom_id), ""))
                    self._remember_session_event(event_id, fingerprint, result)
                    return result
            else:
                self.set_classroom_load(classroom_id, True, source="RFID", event_time=event_time)
                result = (RfidEventType.CARD_RECOGNIZED.value, classroom_id, next((c["name"] for c in CLASSROOMS if c["id"] == classroom_id), ""), next((c["service_id"] for c in CLASSROOMS if c["id"] == classroom_id), ""))
                self._remember_session_event(event_id, fingerprint, result)
                return result


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

    def set_classroom_load(self, classroom_id: str, active: bool, source: str = "UI", event_id: str | None = None,
                           event_time: datetime | None = None):
        with self._lock:
            if classroom_id not in {c["id"] for c in CLASSROOMS}:
                raise ValueError(f"unknown classroom {classroom_id!r}")
            fingerprint = ("session", classroom_id, bool(active))
            cached = self._cached_session_event(event_id, fingerprint)
            if cached is not None:
                return cached
            occurred = event_time or datetime.now(timezone.utc)
            if occurred.tzinfo is None:
                raise ValueError("session event time must include a UTC offset")
            occurred = occurred.astimezone(timezone.utc)
            occurred_s = occurred.timestamp()
            if occurred_s <= self.last_session_event_at.get(classroom_id, 0):
                raise ValueError("stale or out-of-order session event")
            now = time.time()
            changed = (classroom_id not in self.active_sessions) if active else (classroom_id in self.active_sessions)
            self.software_mode = True
            self.last_session_event_at[classroom_id] = occurred_s
            if not changed:
                if active:
                    self.active_sessions[classroom_id]["last_scan"] = now
                self._remember_session_event(event_id, fingerprint, False)
                return False
            if active:
                self.active_sessions[classroom_id] = {"source": source, "started_at": now, "last_scan": now,
                                                      "last_event_at": occurred_s}
            else:
                del self.active_sessions[classroom_id]
            self.control_revision += 1
            status = "active" if active else "inactive"
            self.add_event("SESSION_START" if active else "SESSION_END", f"Session for {classroom_id} became {status} via {source}")
            self._remember_session_event(event_id, fingerprint, True)
            return True

    def reset_sessions(self):
        with self._lock:
            self.active_sessions.clear()
            self.session_event_ids.clear()
            self.last_session_event_at.clear()
            self.software_mode = False
            self.control_revision += 1

    def record_activity(self, classroom_id, features, observed_at, source, recorded_at=None):
        """Store evidence and apply only the inference matching its current revision."""
        with self._lock:
            self.software_mode = True
            self.control_revision += 1

            if not self.storage.degraded:
                try:
                    with Session(self.storage.engine) as db_session:
                        obs = Observation(
                            run_id=self.run_id,
                            asset_id=classroom_id,
                            timestamp=observed_at,
                            payload=features
                        )
                        db_session.add(obs)
                        self.storage.commit(db_session)
                except Exception:
                    pass

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
            pred = self.rank_dwell.update(classroom_id, pred, revision)
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


    def expire_sessions(self):
        now = time.time()
        expired = [cid for cid, session in self.active_sessions.items() if now - session["last_scan"] > SESSION_EXPIRY_SECONDS]
        for cid in expired:
            del self.active_sessions[cid]
            self.control_revision += 1
            self.save_command('session_expired', {'classroom_id': cid})
            self.add_event("SESSION_EXPIRED", f"Session expired for {cid}")


    def compute_allocation(self) -> int:
        """
        Compute allocation based on priority and capacity constraints.
        - Hospital feeder services are requested independent of a session by default.
        - Uncertainty protects essentials: even without clear occupancy evidence, they are never silently cut.
        - Session evidence (RFID/UI) explicitly adds each classroom's service demand.
        - Occupancy prediction (from sensors) can further rank active/unknown ties, but does NOT override the safety of essentials.
        """
        with self._lock:
            self.expire_sessions()
            now = self.clock()
            freshness = tuple(received is not None and now - received > 600
                              for received in self.activity_received_monotonic.values())
            requested = ALL_SERVICES_MASK
            if self.software_mode:
                requested = BASE_REQUESTED_MASK
                for c in CLASSROOMS:
                    if c["id"] in self.active_sessions:
                        requested |= 1 << SERVICE_BIT[c["service_id"]]
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
            if self.storage.degraded:
                self.proposed_mask &= self.last_allocation_mask
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
                if not self.storage.degraded:
                    with Session(self.storage.engine) as session:
                        session.add(Decision(decision_id=str(uuid.uuid4()), run_id=self.run_id,
                            revision=self.control_revision, timestamp=datetime.now(timezone.utc),
                            modeled_mask=self.last_allocation_mask, proposed_mask=self.proposed_mask,
                            indicator_command_mask=self.compute_indicator_command_mask(self.last_allocation_mask),
                            reason="Protected-first allocation",
                            context={**explanation, "config_hash": SITE_CONFIG_HASH,
                                     "catalog_version": site_profile.version}))
                        self.storage.commit(session)
            return self.last_allocation_mask


    def compute_indicator_command_mask(self, modeled_mask: int) -> int:
        with self._lock:
            mask = 0
            # Hospital rooms light when their lighting service is served
            for room in HOSPITAL_ROOMS:
                if (modeled_mask >> SERVICE_BIT[room["lighting_service"]]) & 1:
                    mask |= (1 << room["led_bit"])

            # Classroom logic
            for cid, session in self.active_sessions.items():
                classroom = next((c for c in CLASSROOMS if c["id"] == cid), None)
                if classroom:
                    cr_svc = classroom["service_id"]
                    svc_served = bool((modeled_mask >> SERVICE_BIT[cr_svc]) & 1)

                    cr_svc_obj = next((s for s in SERVICE_CATALOG if s["id"] == cr_svc), None)
                    feeder_avail = False
                    if cr_svc_obj:
                        feeder_avail = self.feeder_available.get(cr_svc_obj["feeder"], False)

                    if svc_served and feeder_avail:
                        mask |= (1 << classroom["led_bit"])

            return mask

    def record_ack(self, device_boot: str, sequence: int, session: str, confirmed_mask: int, provenance: str):
        with self._lock:
            if provenance != "SIMULATED":
                raise ValueError("No physical command/session identity has been provisioned")
            if self.storage.degraded:
                raise RuntimeError("Acknowledgment storage is unavailable")
            # Record it in the DB
            now = datetime.now(timezone.utc)
            if not self.storage.degraded:
                try:
                    with Session(self.storage.engine) as db_session:
                        duplicate = db_session.exec(select(Acknowledgment).where(
                            Acknowledgment.run_id == self.run_id,
                            Acknowledgment.device_boot == device_boot,
                            Acknowledgment.sequence == sequence,
                            Acknowledgment.session == session,
                        )).first()
                        if duplicate:
                            return False
                        ack = Acknowledgment(
                            run_id=self.run_id,
                            device_boot=device_boot,
                            sequence=sequence,
                            session=session,
                            timestamp=now,
                            confirmed_mask=confirmed_mask
                        )
                        db_session.add(ack)
                        if not self.storage.commit(db_session):
                            raise RuntimeError("acknowledgment could not be persisted")
                except Exception:
                    log.exception("Acknowledgment persistence failed")
                    raise

            # Simulation history never confirms physical GPIO output.
            self.control_revision += 1
            self.add_event("HARDWARE_ACK", f"ACK received via {provenance}")
            return True

    def service_watts(self, allocation_mask: int, proposed_mask: int, requested_mask: int):
        """(requested_w, proposed_w, served_w) per service, in catalog order.

        Services decomposed into classroom leaves report the leaf decision (partial service is possible);
        the rest are whole services decided by the campus allocator.
        """
        rows = []
        for i, svc in enumerate(SERVICE_CATALOG):
            leaves = (self.feeder_b_leaves or {}).get(svc["id"])
            if leaves is not None:
                rows.append((leaves["requested_w"], leaves["commanded_w"], leaves["served_w"]))
            else:
                rows.append(tuple(svc["watts"] if mask & (1 << i) else 0
                                  for mask in (requested_mask, proposed_mask, allocation_mask)))
        return rows

    def advance(self) -> int:
        """Advance control (evidence freshness, allocation, staged restoration) without publishing."""
        with self._lock:
            modeled_mask = self.compute_allocation()
            self.compute_fault_diagnosis()
            return modeled_mask

    def publish(self) -> SystemSnapshot:
        """Project the current decision (campus services plus any classroom leaf decision) and publish."""
        with self._lock:
            candidate = self._project(self.last_allocation_mask)
            self.tick_count += 1
            if self.published is None or _content(candidate) != _content(self.published):
                self.published_revision += 1
                candidate.published_revision = self.published_revision
                self.published = candidate
            return self.published

    def tick(self) -> SystemSnapshot:
        """Advance control and publish. This is the only place time-dependent state moves forward.
        Readers call build_snapshot(). The site authority calls advance() and publish() separately so the
        classroom leaf decision can be included in the same publication; a standalone tick has none."""
        with self._lock:
            self.feeder_b_leaves = None
            self.advance()
            return self.publish()

    def build_snapshot(self) -> Optional[SystemSnapshot]:
        """Read-only: a copy of the last published snapshot, or None before the first tick.
        Never advances control."""
        with self._lock:
            return None if self.published is None else self.published.model_copy(deep=True)

    def _published_explanation(self, served_w_of):
        """The campus decision record; feeder B rows say the classroom leaf allocation decided them."""
        leaves = self.feeder_b_leaves or {}
        if not leaves or not self.allocation_explanation.get("decisions"):
            return self.allocation_explanation
        index = {svc["id"]: i for i, svc in enumerate(SERVICE_CATALOG)}
        decisions = []
        for row in self.allocation_explanation["decisions"]:
            leaf = leaves.get(row.get("service_id"))
            if leaf is not None:
                served = served_w_of[index[row["service_id"]]]
                reason = row["reason"]
                if "not_requested" in row.get("binding_constraints", []):
                    # The campus solve counts rooms with a session; the leaves always protect every room's essentials.
                    reason = (f"No session in this room; the classroom leaf allocation serves {served:,} of "
                              f"{leaf['requested_w']:,} W (essentials first, then any budget left)")
                elif 0 < served < leaf["requested_w"]:
                    partly = f"{served:,} of {leaf['requested_w']:,} W served by the classroom leaf allocation"
                    reason = (f"Partly served: {partly} within the feeder B budget" if row.get("applied")
                              else f"{reason}; {partly}")
                elif served == 0 and row.get("applied"):
                    reason = "Feeder B budget granted, but the classroom leaf allocation served none of this room"
                row = {**row, "decided_by": "classroom_leaf_allocation", "served_w": served,
                       "shortfall_w": leaf["requested_w"] - served,
                       "campus_allocator_applied": row.get("applied"), "reason": reason}
            decisions.append(row)
        # The published masks include the leaf decision; replay the restoration gate against these.
        return {**self.allocation_explanation, "decisions": decisions,
                "campus_proposed_mask": self.proposed_mask, "campus_applied_mask": self.last_allocation_mask}

    def _project(self, allocation_mask: int) -> SystemSnapshot:
        with self._lock:
            requested_mask = ALL_SERVICES_MASK
            if self.software_mode:
                requested_mask = BASE_REQUESTED_MASK
                for c in CLASSROOMS:
                    if c["id"] in self.active_sessions:
                        requested_mask |= 1 << SERVICE_BIT[c["service_id"]]
            # One decision per load (#33): feeder B services report the classroom leaf decision, so
            # masks and watts below agree with /classrooms. A bit means "some of this service".
            rows = self.service_watts(allocation_mask, self.proposed_mask, requested_mask)
            requested_mask, proposed_mask, modeled_mask = (
                sum(1 << i for i, row in enumerate(rows) if row[k] > 0) for k in range(3))
            requested_w_of = [row[0] for row in rows]
            proposed_w_of = [row[1] for row in rows]
            served_w_of = [row[2] for row in rows]
            indicator_command = self.compute_indicator_command_mask(modeled_mask)

            services_out = []
            for svc in SERVICE_CATALOG:
                bit = SERVICE_BIT[svc["id"]]
                served = bool((modeled_mask >> bit) & 1)
                leaf_decided = svc["id"] in (self.feeder_b_leaves or {})

                if leaf_decided and served:
                    reason = ("Served by classroom leaf allocation" if served_w_of[bit] >= requested_w_of[bit] else
                              f"Partly served by classroom leaf allocation: {served_w_of[bit]:,} of "
                              f"{requested_w_of[bit]:,} W")
                elif served:
                    reason = "Served by allocation policy"
                elif proposed_mask & (1 << bit):
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
                    requested_w=requested_w_of[bit],
                    served_w=served_w_of[bit],
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


            requested_w = sum(requested_w_of)
            served_w = sum(served_w_of)
            campus_totals = ScopeTotals(capacity_w=self.source_capacity_w, requested_w=requested_w, served_w=served_w)

            zone_totals = {}
            for z in ["hospital", "classroom"]:
                z_req = sum(requested_w_of[i] for i, s in enumerate(SERVICE_CATALOG) if s["zone"] == z)
                z_srv = sum(served_w_of[i] for i, s in enumerate(SERVICE_CATALOG) if s["zone"] == z)
                zone_totals[z] = ScopeTotals(capacity_w=None, requested_w=z_req, served_w=z_srv)

            contract_dict = {
                "identity": self.identity(),
                "campus_totals": campus_totals,
                "zone_totals": zone_totals
            }
            contract = CrossRouteContract(**contract_dict)

            edges = [power_edge(f"campus:SRC>{f}", "SRC", f, connected=self.source_capacity_w > 0,
                                commanded=any(proposed_mask & (1 << i) for i, s in enumerate(SERVICE_CATALOG) if s["feeder"] == f),
                                applied=any(modeled_mask & (1 << i) for i, s in enumerate(SERVICE_CATALOG) if s["feeder"] == f),
                                requested_w=sum(requested_w_of[i] for i, s in enumerate(SERVICE_CATALOG) if s["feeder"] == f),
                                served_w=sum(served_w_of[i] for i, s in enumerate(SERVICE_CATALOG) if s["feeder"] == f),
                                reason="Source has no capacity" if self.source_capacity_w <= 0 else f"Feeder {f} head")
                     for f in self.feeder_limits_w]
            for i, svc in enumerate(SERVICE_CATALOG):
                closed = self.source_capacity_w > 0 and self.feeder_available.get(svc["feeder"], False)
                edges.append(power_edge(f"campus:{svc['feeder']}>{svc['id']}", svc["feeder"], svc["id"], connected=closed,
                                        commanded=bool(proposed_mask & (1 << i)), applied=bool(modeled_mask & (1 << i)),
                                        requested_w=requested_w_of[i], served_w=served_w_of[i],
                                        reason=(f"Open: feeder {svc['feeder']} unavailable" if not closed
                                                else services_out[i].model_reason)))

            return SystemSnapshot(
                contract=contract,
                config_hash=SITE_CONFIG_HASH,
                edges=edges,
                control_revision=self.control_revision,
                generated_at=datetime.now(timezone.utc),
                source=SourceInfo(kind=SourceKind.SIMULATED, capacity_w=self.source_capacity_w),
                feeder_limits_w=self.feeder_limits_w.copy(),
                requested_mask=requested_mask,
                modeled_mask=modeled_mask,
                proposed_mask=proposed_mask,
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
                            "explanation": self._published_explanation(served_w_of),
                            "critical_shortfall_w": max(0, sum(s["watts"] for s in SERVICE_CATALOG[:2]) -
                                                         sum(SERVICE_CATALOG[i]["watts"] for i in range(2) if modeled_mask & (1 << i))),
                            "served_w": served_w,
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
    return snapshot.model_dump(exclude={"generated_at", "published_revision", "contract"})
