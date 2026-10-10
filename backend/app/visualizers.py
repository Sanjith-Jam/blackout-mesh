"""Independent synthetic classroom and hospital demos."""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

from app.core.edges import edge as power_edge
from app.core.restoration import RestorationGate
from app.diagnosis.infer import ObservationWindow, TransformerRating, diagnose_transformer
from app.diagnosis.observations import validate as validate_observation
from app.simulation.sensors import HOSPITAL_ASSETS, HOSPITAL_FAULTS, TRANSFORMER_FIELDS, add_noise, apply_fault, envelopes as sensor_envelopes, hospital_readings, zone_readings
from app.core.safety import SAFETY_POLICY_VERSION, ActivityGuard, RankDwell, shortfall_status
from app.core.active_site import CATALOG

# Classroom appliances (key, name, watts, essential) per room, from the site profile.
ROOMS = tuple(c["id"] for c in CATALOG.classrooms)
LOADS = CATALOG.classroom_loads
LOAD_KEYS = tuple((room, item[0]) for room in ROOMS for item in LOADS[room])

# The classroom view's supply slider spans its campus feeder; "overload" is the profile's shortage preset.
NORMAL_CAPACITY_W = CATALOG.feeder_limits_w["B"]
OVERLOAD_CAPACITY_W = CATALOG.feeder_presets_w["B"] if CATALOG.feeder_presets_w["B"] is not None else NORMAL_CAPACITY_W // 2
CAPACITY_RANGE_W = (0, NORMAL_CAPACITY_W)
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
        self.capacity = NORMAL_CAPACITY_W  # classroom limit (the slider): a named sub-budget
        self.campus_limit_w: int | None = None  # set by the site authority from campus feeder B headroom
        self.campus_feeder_closed: bool | None = None  # set by the site authority: is campus feeder B available?
        self._scanned: list[str] = []  # standalone demo fallback; live app binds GridState sessions
        self._sessions = None
        self._set_session = None
        self.gate = RestorationGate(clock)
        self.replay_running = self.replay_length > 0
        self.replay_base = 0
        self.replay_anchor = clock()
        self._predictions: dict[tuple[str, int], dict] = {}
        self._replay_index = 0
        self._activity: dict[str, dict] = {}
        self.guard = ActivityGuard()
        self.dwell = RankDwell()
        self.published: dict | None = None
        self.published_revision = 0
        self._advance_evidence()
        initial = (1 << len(LOAD_KEYS)) - 1
        self.gate.update(initial, self._signature(self._room_order()), range(len(LOAD_KEYS)))
        self.tick()

    @property
    def scanned(self):
        sessions = getattr(self, "_sessions", None)
        if sessions is not None:
            return [cid for cid in sessions if cid in ROOMS]
        return getattr(self, "_scanned", [])

    @scanned.setter
    def scanned(self, value):
        self._scanned = value

    def bind_sessions(self, sessions, set_session):
        self._sessions = sessions
        self._set_session = set_session

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
        # Each replay row is one reading; the guard confirms INACTIVE before it can lower a rank.
        # RankDwell then holds a changed state until it repeats, so single noisy readings cannot switch loads.
        self._activity = {cid: self.dwell.update(cid, self.guard.update(cid, self._infer(cid), self._replay_index),
                                                 self._replay_index) for cid in ROOMS}

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

    def effective_capacity(self):
        return self.capacity if self.campus_limit_w is None else min(self.capacity, self.campus_limit_w)

    def _signature(self, order):
        return (self.effective_capacity(), tuple(r for r in order if r in self.scanned))

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
        volatile = ("published_revision", "generated_at")
        if self.published is None or candidate != {k: v for k, v in self.published.items() if k not in volatile}:
            from datetime import datetime, timezone
            self.published_revision += 1
            candidate["published_revision"] = self.published_revision
            candidate["generated_at"] = datetime.now(timezone.utc).isoformat()
            self.published = candidate
        return self.snapshot()

    def _standalone_allocation(self, order, effective):
        """Greedy fill used only when the view runs without the site authority (unit tests, rehearsals)."""
        priority = self._priority(order)
        target: set[tuple[str, str]] = set()
        remaining = effective
        shortfall_note: dict[tuple[str, str], str] = {}
        for room, item in priority:
            key = (room, item[0])
            if item[2] <= remaining:
                target.add(key)
                remaining -= item[2]
            else:
                shortfall_note[key] = f"{item[2]:,} W did not fit in the {remaining:,} W left after higher-priority loads"
        proposed = sum(1 << LOAD_KEYS.index(key) for key in target)
        bit_order = [LOAD_KEYS.index((room, item[0])) for room, item in priority]
        applied = self.gate.update(proposed, self._signature(order), bit_order)
        current = {key for bit, key in enumerate(LOAD_KEYS) if applied & (1 << bit)}
        return target, current, shortfall_note

    def _project(self):
        order = self._room_order()
        effective = self.effective_capacity()
        decision = getattr(self, "site_decision", None)
        if decision is not None:
            # Live app: the site authority's appliance-level optimizer decides; this view projects it.
            target = {key for key, (commanded, _, reachable, _) in decision.items() if commanded and reachable}
            current = {key for key, (_, applied, _, _) in decision.items() if applied}
            shortfall_note = {key: reason for key, (commanded, _, _, reason) in decision.items() if not commanded}
        else:
            target, current, shortfall_note = self._standalone_allocation(order, effective)
        rooms = []
        for cid in ROOMS:
            loads = []
            for lid, name, watts, essential in LOADS[cid]:
                key = (cid, lid)
                on = key in current
                reason = (decision[key][3] if decision is not None else
                          "served by classroom demo" if on else
                          "Waiting for simulated restoration delay" if key in target else
                          "Insufficient capacity for essential load" if essential else
                          "Shed by classroom demo policy")
                loads.append({"id": lid, "name": name, "watts": watts, "essential": essential,
                              "served": on, "reason": reason})
            act = self.activity(cid)
            rooms.append({"id": cid, "name": f"Classroom {cid[-1]}", "rfid_active": cid in self.scanned,
                          "priority_rank": order.index(cid) + 1 if cid in self.scanned else None,
                          "activity": {key: act.get(key) for key in ("state", "raw_state", "guard", "score", "reason",
                                                                       "model_version", "evidence")},
                          "loads": loads})
        requested = sum(x[2] for rows in LOADS.values() for x in rows)
        served_w = sum(x[2] for r in ROOMS for x in LOADS[r] if (r, x[0]) in current)
        edges = self._edges(target, current, shortfall_note)
        essential = [(r, x) for r in ROOMS for x in LOADS[r] if x[3]]
        safety = shortfall_status(sum(x[2] for _, x in essential),
                                  sum(x[2] for r, x in essential if (r, x[0]) in current))
        status = self.model.status() if hasattr(self.model, "status") else {}
        limited_by = ("campus feeder B" if self.campus_limit_w is not None and self.campus_limit_w < self.capacity
                      else "classroom limit")
        return {"capacity_w": self.capacity, "capacity_range_w": list(CAPACITY_RANGE_W),
                "classroom_limit_w": self.capacity, "campus_limit_w": self.campus_limit_w,
                "effective_capacity_w": effective, "limited_by": limited_by,
                "requested_w": requested, "served_w": served_w, "shortfall_w": requested - served_w,
                "selected_classroom_id": self.scanned[-1] if self.scanned else None,
                "scanned_classroom_ids": [r for r in ROOMS if r in self.scanned],
                "priority_order": [r for r in order if r in self.scanned],
                "rooms": rooms, "mode": "SIMULATED", "safety": safety, "edges": edges,
                "model": {"ready": bool(status.get("ready")), "model_version": status.get("model_version", "unavailable"),
                          "fallback_reason": status.get("fallback_reason")},
                "replay": {"running": self.replay_running, "index": self.replay_index(),
                           "length": self.replay_length, "step_s": REPLAY_STEP_S},
                "policy": "Classroom-only: lighting and computers in every room are protected and served first, "
                          "whatever the model says. Scanned rooms' other equipment next, ranked by the activity "
                          "model (ACTIVE, then UNKNOWN, then INACTIVE; earlier scan first within a state). INACTIVE "
                          f"counts only after {self.guard.confirmations} consecutive readings, and any change of state "
                          f"reorders loads only after it repeats on {self.dwell.hold} readings. Unscanned rooms' "
                          f"optional loads last. Safety policy {SAFETY_POLICY_VERSION}."}

    def _edges(self, target, current, shortfall_note):
        """Supply -> bus -> room -> appliance edges for the classroom drawing (#23)."""
        closed = self.campus_feeder_closed is not False
        open_reason = "Open: campus feeder B is unavailable"
        any_cmd, any_on = bool(target), bool(current)
        edges = [power_edge("classroom:SUPPLY>BUS", "SUPPLY", "BUS", connected=closed, commanded=any_cmd, applied=any_on,
                            requested_w=sum(x[2] for rows in LOADS.values() for x in rows),
                            served_w=sum(x[2] for r in ROOMS for x in LOADS[r] if (r, x[0]) in current),
                            reason=open_reason if not closed else f"Shared bus; {self.effective_capacity():,} W available")]
        for cid in ROOMS:
            room_cmd = any((cid, x[0]) in target for x in LOADS[cid])
            room_on = any((cid, x[0]) in current for x in LOADS[cid])
            room_served = sum(x[2] for x in LOADS[cid] if (cid, x[0]) in current)
            edges.append(power_edge(f"classroom:BUS>{cid}", "BUS", cid, connected=closed, commanded=room_cmd, applied=room_on,
                                    requested_w=sum(x[2] for x in LOADS[cid]), served_w=room_served,
                                    reason=open_reason if not closed else f"{room_served:,} W of this room's loads served"))
            for lid, name, watts, essential in LOADS[cid]:
                key = (cid, lid)
                if not closed:
                    reason = open_reason
                elif key in current:
                    reason = f"{name}: served ({'protected essential' if essential else 'optional'})"
                elif key in target:
                    reason = f"{name}: commanded on, waiting for the restoration delay"
                else:
                    reason = f"{name}: shed by the allocator; {shortfall_note.get(key, 'not selected')}"
                edges.append(power_edge(f"classroom:{cid}>{lid}", cid, f"{cid}.{lid}", connected=closed,
                                        commanded=key in target, applied=key in current,
                                        requested_w=watts, served_w=watts if key in current else 0, reason=reason))
        return edges

    def act(self, action: str, classroom_id: str | None = None, capacity_w: int | None = None, source: str = "UI",
            event_id: str | None = None, event_time=None):
        if action == "scan":
            if self._set_session:
                self._set_session(classroom_id, True, source, event_id, event_time)
            elif classroom_id not in self.scanned:
                self._scanned.append(classroom_id)
        elif action == "unscan":
            if self._set_session:
                self._set_session(classroom_id, False, source, event_id, event_time)
            elif classroom_id in self.scanned:
                self._scanned.remove(classroom_id)
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
            sessions, set_session = self._sessions, self._set_session
            if set_session:
                for cid in list(self.scanned):
                    set_session(cid, False, "UI")
            self.__init__(self.gate.clock, self.model, self.replay)
            self.bind_sessions(sessions, set_session) if sessions is not None else None
        return self.tick()  # a command wakes control immediately


def diagnose(rated_current_a, current_a, temperature_c, input_voltage_v, output_voltage_v, cooling_ok):
    """Compatibility wrapper: one steady reading, diagnosed through the telemetry-only path.

    The reading is fed as two consecutive identical samples so it can be confirmed. Live routes use
    HospitalTelemetry, which keeps a real rolling window.
    """
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    window = ObservationWindow()
    values = dict(zip(TRANSFORMER_FIELDS, (current_a, temperature_c, input_voltage_v, output_voltage_v, cooling_ok)))
    for seq, at in ((1, now - timedelta(milliseconds=250)), (2, now)):
        for raw in sensor_envelopes({"TX": values}, seq, at):
            window.add(validate_observation(raw, {"TX"}, now))
    return diagnose_transformer(window, "TX", TransformerRating(rated_current_a=rated_current_a), now)



HOSP_ZONES = CATALOG.hospital_zones
# Hospital equipment are the leaves of the campus feeder A services (docs/CATALOG_MIGRATION.md): each leaf
# names its service in the site profile, and the profile is rejected unless essential leaves belong to T1
# services and every service's leaves sum to its watts. reconcile_catalog() re-checks the sums at startup.
HOSP_LOADS = CATALOG.hospital_loads
HOSP_PARENT = CATALOG.hospital_parent
ZONE_ASSET = {zone: asset for asset, zone in CATALOG.transformers.items()}
HOSPITAL_LOADS = {zone: [(item[0], item[3]) for item in loads] for zone, loads in HOSP_LOADS.items()}
HOSP_LOAD_KEYS = tuple((zone, item[0]) for zone in HOSP_ZONES for item in HOSP_LOADS[zone])


class HospitalPriorityDemo(ClassroomDemo):
    """Hospital zone view with the classroom demo's controls: zone scans, a supply slider and presets.

    Follows the same tick/publish contract as ClassroomDemo: tick() advances restoration and
    publishes; snapshot() is a read-only copy (#9, #10). Essential equipment is protected (#22).
    """

    NORMAL_W = CATALOG.feeder_limits_w["A"]
    OVERLOAD_W = CATALOG.feeder_presets_w["A"] if CATALOG.feeder_presets_w["A"] is not None else NORMAL_W // 2
    RANGE_W = (0, NORMAL_W)

    def __init__(self, clock=None, model=None, replay=None):
        import time
        clock = clock or time.monotonic
        if model is None:
            from app.activity.model import ActivityModel
            model = ActivityModel()
        self.model = model
        self.replay = {} if replay is None else replay
        self.replay_length = 0  # no recorded activity evidence exists for hospital zones
        self.capacity = self.NORMAL_W
        self.campus_limit_w: int | None = None  # set by the site authority from campus feeder A service
        self.campus_feeder_closed: bool | None = None  # set by the site authority: is campus feeder A available?
        self.scanned: list[str] = []
        self.gate = RestorationGate(clock)
        self.replay_running = False
        self.replay_base = 0
        self.replay_anchor = clock()
        self._predictions = {}
        self._replay_index = 0
        self._activity = {}
        self.guard = ActivityGuard()
        self.published = None
        self.published_revision = 0
        self.telemetry = ObservationWindow()
        self.telemetry_sequence = 0
        self.fault: dict | None = None  # injected sensor/supply fault (A4); allocation never reads its kind
        self._last_readings: dict[str, dict] = {}
        self._advance_evidence()
        initial = (1 << len(HOSP_LOAD_KEYS)) - 1
        self.gate.update(initial, self._signature(self._room_order()), range(len(HOSP_LOAD_KEYS)))
        self.tick()

    def _advance_evidence(self):
        self._activity = {z: {"state": "UNKNOWN", "raw_state": "UNKNOWN", "score": None, "model_version": "unavailable",
                              "reason": "no recorded activity evidence for hospital zones",
                              "guard": "conservative fallback: no evidence", "evidence": {}}
                          for z in HOSP_ZONES}

    def effective_capacity(self):
        if self.fault and self.fault["kind"] == "upstream_loss":
            return 0  # the injected loss removes the hospital's incoming supply
        return super().effective_capacity()

    def _supply_open_reason(self):
        if self.campus_feeder_closed is False:
            return "Open: campus feeder A is unavailable"
        if self.fault and self.fault["kind"] == "upstream_loss":
            return "Open: upstream supply lost (injected fault)"
        return None

    def _room_order(self):
        act = {z: self.activity(z) for z in HOSP_ZONES}
        def sort_key(z):
            state = act[z].get("state")
            state_rank = 0 if state == "ACTIVE" else 1 if state == "UNKNOWN" else 2
            scan_rank = self.scanned.index(z) if z in self.scanned else 999
            return (state_rank, scan_rank, HOSP_ZONES.index(z))
        return sorted(HOSP_ZONES, key=sort_key)

    def _priority(self, order):
        essentials = [(z, item) for z in HOSP_ZONES for item in HOSP_LOADS[z] if item[3]]
        optionals = [(z, item) for z in order for item in HOSP_LOADS[z] if not item[3]]
        return essentials + optionals

    def _project(self):
        order = self._room_order()
        decision = getattr(self, "site_decision", None)
        if decision is not None:
            # Live app: the site authority's appliance-level optimizer decides; this view projects it.
            target = {key for key, (commanded, _, reachable, _) in decision.items() if commanded and reachable}
            current = {key for key, (_, applied, _, _) in decision.items() if applied}
        else:
            priority = self._priority(order)
            target = set()
            remaining = self.effective_capacity()
            for z, item in priority:
                key = (z, item[0])
                if item[2] <= remaining:
                    target.add(key)
                    remaining -= item[2]
            proposed = sum(1 << HOSP_LOAD_KEYS.index(key) for key in target)
            bit_order = [HOSP_LOAD_KEYS.index((z, item[0])) for z, item in priority]
            applied = self.gate.update(proposed, self._signature(order), bit_order)
            current = {key for bit, key in enumerate(HOSP_LOAD_KEYS) if applied & (1 << bit)}
        readings, diagnoses = self._sense_and_diagnose(current)
        edges = self._hospital_edges(target, current, readings, diagnoses)

        transformers = []
        for i, z in enumerate(HOSP_ZONES):
            loads = []
            for lid, name, watts, essential in HOSP_LOADS[z]:
                key = (z, lid)
                on = key in current
                reason = ("served" if on else "waiting" if key in target else "shed")
                if decision is not None:
                    reason = decision[key][3]
                loads.append({"id": lid, "name": name, "watts": watts, "essential": essential, "served": on, "reason": reason})
            act = self.activity(z)
            transformers.append({
                "id": ZONE_ASSET[z], "name": CATALOG.transformer_names[ZONE_ASSET[z]], "zone": z,
                "rated_current_a": self._rating(z).rated_current_a, "sensors": readings[ZONE_ASSET[z]],
                "diagnosis": diagnoses[ZONE_ASSET[z]],
                "energized": any(l["served"] for l in loads),
                "rfid_active": z in self.scanned,
                "priority_rank": order.index(z) + 1 if z in self.scanned else None,
                "activity": {key: act.get(key) for key in ("state", "raw_state", "guard", "score", "reason", "model_version", "evidence")},
                "loads": loads
            })

        requested = sum(x[2] for rows in HOSP_LOADS.values() for x in rows)
        served_w = sum(x[2] for z in HOSP_ZONES for x in HOSP_LOADS[z] if (z, x[0]) in current)
        essential = [(z, x) for z in HOSP_ZONES for x in HOSP_LOADS[z] if x[3]]
        safety = shortfall_status(sum(x[2] for _, x in essential), sum(x[2] for z, x in essential if (z, x[0]) in current))
        status = self.model.status() if hasattr(self.model, "status") else {}
        limited_by = ("campus feeder A" if self.campus_limit_w is not None and self.campus_limit_w < self.capacity
                      else "hospital limit")
        return {
            "capacity_w": self.capacity, "capacity_range_w": list(self.RANGE_W),
            "hospital_limit_w": self.capacity, "campus_limit_w": self.campus_limit_w,
            "effective_capacity_w": self.effective_capacity(), "limited_by": limited_by,
            "requested_w": requested, "served_w": served_w, "shortfall_w": requested - served_w,
            "selected_zone_id": self.scanned[-1] if self.scanned else None,
            "scanned_zone_ids": [z for z in HOSP_ZONES if z in self.scanned],
            "priority_order": [z for z in order if z in self.scanned],
            "transformers": transformers, "mode": "SIMULATED", "safety": safety, "edges": edges,
            "fault": None if not self.fault else {"kind": self.fault["kind"], "zone_id": self.fault["zone"],
                                                  "asset_id": self.fault["asset"], "provenance": "INJECTED_SIMULATION"},
            "model": {"ready": bool(status.get("ready")), "model_version": status.get("model_version", "unavailable"), "fallback_reason": status.get("fallback_reason")},
            "replay": {"running": self.replay_running, "index": self.replay_index(), "length": self.replay_length, "step_s": REPLAY_STEP_S},
            "policy": "Hospital: the equipment decomposes campus feeder A (L0 essential circuit, L1 emergency "
                      "lighting, L2 water pump and HVAC). Essential equipment is always served first; scanned "
                      "zones' optional equipment next, within the feeder A power the campus allocated."
        }

    def _hospital_edges(self, target, current, readings, diagnoses):
        """Supply -> bus -> transformer -> equipment edges for the hospital drawing (#23)."""
        open_reason = self._supply_open_reason()
        closed = open_reason is None
        edges = [power_edge("hospital:SUPPLY>BUS", "UTILITY", "BUS", connected=closed, commanded=bool(target),
                            applied=bool(current), requested_w=sum(x[2] for rows in HOSP_LOADS.values() for x in rows),
                            served_w=sum(x[2] for z in HOSP_ZONES for x in HOSP_LOADS[z] if (z, x[0]) in current),
                            reason=open_reason if not closed else f"Campus feeder A; {self.effective_capacity():,} W available")]
        for i, z in enumerate(HOSP_ZONES):
            tx = ZONE_ASSET[z]
            vout = readings[tx].get("output_voltage_v")
            diagnosis = diagnoses[tx]
            observed = {"output_voltage_v": vout, "energized": None if vout is None else vout >= 100.0,
                        "provenance": "SIMULATED_SENSOR", "diagnosis_status": diagnosis.get("status"),
                        "note": "Voltage presence only; no measured branch current."}
            unknown = diagnosis.get("status") == "ABSTAINED" or vout is None
            zone_served = sum(x[2] for x in HOSP_LOADS[z] if (z, x[0]) in current)
            edges.append(power_edge(f"hospital:BUS>{tx}", "BUS", tx, connected=closed,
                                    commanded=any((z, x[0]) in target for x in HOSP_LOADS[z]),
                                    applied=any((z, x[0]) in current for x in HOSP_LOADS[z]),
                                    requested_w=sum(x[2] for x in HOSP_LOADS[z]), served_w=zone_served, observed=observed,
                                    evidence_unknown=unknown,
                                    reason=(open_reason if not closed else
                                            f"Diagnosis abstained: {diagnosis.get('cause')}" if unknown
                                            else f"{zone_served:,} W of {z} equipment served")))
            for lid, name, watts, essential in HOSP_LOADS[z]:
                key = (z, lid)
                reason = (open_reason if not closed else
                          f"{name}: served ({'essential' if essential else 'optional'})" if key in current else
                          f"{name}: commanded on, waiting for the restoration delay" if key in target else
                          f"{name}: shed by the allocator")
                edges.append(power_edge(f"hospital:{tx}>{lid}", tx, f"{tx}.{lid}", connected=closed,
                                        commanded=key in target, applied=key in current, requested_w=watts,
                                        served_w=watts if key in current else 0, reason=reason))
        return edges

    @staticmethod
    def _rating(zone):
        # Full zone demand sizes each transformer's configured current rating.
        return TransformerRating(rated_current_a=round(sum(x[2] for x in HOSP_LOADS[zone]) / 230.0, 2))

    def _sense_and_diagnose(self, current):
        """Simulated sensors from served load, then telemetry-only diagnosis (#4). Tick-only."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        served = {ZONE_ASSET[z]: sum(x[2] for x in HOSP_LOADS[z] if (z, x[0]) in current) for z in HOSP_ZONES}
        demand = {ZONE_ASSET[z]: sum(x[2] for x in HOSP_LOADS[z]) for z in HOSP_ZONES}
        readings = zone_readings(served, demand)
        if self.fault:
            ratings = {ZONE_ASSET[z]: self._rating(z).rated_current_a for z in HOSP_ZONES}
            readings = apply_fault(readings, self.fault, ratings, self.telemetry_sequence - self.fault["sequence"])
        frozen = {(self.fault["asset"], "current_a")} if self.fault and self.fault["kind"] == "stuck_sensor" else set()
        readings = add_noise(readings, self.telemetry_sequence, frozen)
        self._last_readings = readings
        self.telemetry_sequence += 1
        for raw in sensor_envelopes(readings, self.telemetry_sequence, now):
            self.telemetry.add(validate_observation(raw, set(readings), now))
        diagnoses = {ZONE_ASSET[z]: diagnose_transformer(self.telemetry, ZONE_ASSET[z], self._rating(z), now, peers_input_low={})
                     for z in HOSP_ZONES}
        return readings, diagnoses

    def inject_fault(self, kind: str, zone_id: str | None = None):
        """Persist an injected fault until cleared or reset; the diagnosis still sees only telemetry."""
        if kind not in HOSPITAL_FAULTS:
            raise ValueError(f"unknown fault {kind!r}")
        zone = zone_id or CATALOG.fault_zone
        asset = ZONE_ASSET[zone]
        frozen = (self._last_readings.get(asset) or {}).get("current_a")
        self.fault = {"kind": kind, "zone": zone, "asset": asset, "sequence": self.telemetry_sequence,
                      "frozen_current_a": frozen}

    def act(self, action: str, zone_id: str | None = None, capacity_w: int | None = None, fault: str | None = None):
        if action == "scan":
            if zone_id not in self.scanned:
                self.scanned.append(zone_id)
        elif action == "unscan":
            if zone_id in self.scanned:
                self.scanned.remove(zone_id)
        elif action == "inject_fault":
            self.inject_fault(fault, zone_id)
        elif action == "clear_fault":
            self.fault = None
        elif action == "set_capacity":
            self.capacity = capacity_w
        elif action == "normal":
            self.capacity = self.NORMAL_W
        elif action == "overload":
            self.capacity = self.OVERLOAD_W
        elif action == "reset":
            self.__init__(self.gate.clock, self.model, self.replay)
        return self.tick()  # a command wakes control immediately



class HospitalTelemetry:
    """Rolling sensor window for the hospital transformers; diagnosis sees only the envelopes."""

    def __init__(self):
        self.window = ObservationWindow()
        self.sequence = 0

    def sample(self, scenario, zone, now):
        self.sequence += 1
        readings = hospital_readings(scenario, zone, self.sequence)
        for raw in sensor_envelopes(readings, self.sequence, now):
            self.window.add(validate_observation(raw, set(HOSPITAL_ASSETS), now))
        return readings

    def diagnoses(self, now):
        rating = TransformerRating()
        low = {}
        for asset in HOSPITAL_ASSETS:
            ins, outs = self.window.series(asset, "input_voltage_v"), self.window.series(asset, "output_voltage_v")
            low[asset] = bool(ins and outs and ins[-1].value is not None and outs[-1].value is not None
                              and ins[-1].value < rating.low_input_v and outs[-1].value < rating.dead_output_v)
        return {asset: diagnose_transformer(self.window, asset, rating, now,
                                            peers_input_low={a: v for a, v in low.items()})
                for asset in HOSPITAL_ASSETS}


def hospital_projection(readings, diagnoses, scenario="normal", zone=None):
    """Route view. Load shedding here is simulated actuation; the diagnosis comes only from telemetry."""
    zone = zone or CATALOG.fault_zone
    transformers = []
    for asset, zname in HOSPITAL_ASSETS.items():
        sensors = readings[asset]
        vout = sensors["output_voltage_v"]
        energized = vout is not None and vout >= 100.0
        loads = []
        for eq_id, _name, _watts, essential in HOSP_LOADS[zname]:
            served = energized
            # In the overload teaching scenario, non-scanned zones shed their non-essential loads.
            if scenario == "overload" and zname != zone and not essential:
                served = False
            loads.append({"id": eq_id, "served": served})
        transformers.append({"id": asset, "name": CATALOG.transformer_names[asset], "zone": zname,
                             "rated_current_a": CATALOG.transformer_ratings_a[asset] or 100.0, "sensors": sensors, "diagnosis": diagnoses[asset],
                             "energized": energized, "loads": loads})
    return {"mode": "SIMULATED", "transformers": transformers,
            "summary": "Diagnosis uses only timestamped sensor observations and configured ratings; "
                       "a cause is inferred after two consecutive agreeing readings. Thresholds are not "
                       "certified protection settings."}


def hospital_snapshot(scenario="normal", zone=None):
    """Three observed samples for a diagnostic rehearsal, outside the live control loop."""
    from datetime import datetime, timedelta, timezone

    zone = zone or CATALOG.fault_zone
    telemetry = HospitalTelemetry()
    now = datetime.now(timezone.utc)
    telemetry.sample(scenario, zone, now - timedelta(milliseconds=500))
    telemetry.sample(scenario, zone, now - timedelta(milliseconds=250))
    readings = telemetry.sample(scenario, zone, now)
    return hospital_projection(readings, telemetry.diagnoses(now), scenario, zone)
