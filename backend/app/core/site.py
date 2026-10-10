"""One site authority over the campus, classroom and hospital views (#3, first step).

All commands go through SiteAuthority.command(); all parts tick together; every projection
carries the same run_id and revision. See docs/CATALOG_MIGRATION.md for the catalog mapping.
"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from sqlmodel import Session

from app.core.active_site import CATALOG
from app.core.appliance_control import ApplianceController
from app.core.appliances import APPLIANCES
from app.core.state import CLASSROOMS, NORMAL_SOURCE_CAPACITY_W, SERVICE_CATALOG, site_profile
from app.schemas.snapshot import SiteIdentityResponse
from app.storage.models import Run
from app.visualizers import (HOSP_LOADS, HOSP_PARENT, LOADS as CLASSROOM_LEAVES, NORMAL_CAPACITY_W as CLASSROOM_NORMAL_W,
                             OVERLOAD_CAPACITY_W as CLASSROOM_OVERLOAD_W, HospitalPriorityDemo)

# The active site profile names the catalog; its content hash pins exactly which inventory a run used (#26).
CATALOG_VERSION = f"site-catalog-{CATALOG.version}"
CONFIG_HASH = CATALOG.config_hash
PROFILE = "campus"
DEFAULT_SCENARIO = "normal"
CUSTOM_SCENARIO = "custom"  # any budget changed by hand after a scenario was applied


def _scenarios() -> dict:
    """Named teaching scenarios (#33), derived from the active site profile's limits and presets.

    Each one sets every budget, so switching is deterministic and never leaves part of the previous
    scenario behind. Sessions and recorded replay are left alone.
    """
    feeders = {f: True for f in CATALOG.feeder_limits_w}
    base = {"source_w": NORMAL_SOURCE_CAPACITY_W, "feeders": feeders, "classroom_limit_w": CLASSROOM_NORMAL_W,
            "hospital_limit_w": HospitalPriorityDemo.NORMAL_W}
    shortage = CATALOG.feeder_limits_w["A"]
    return {
        "normal": {**base, "description": "Full supply, every feeder closed, no sub-limits."},
        "source_shortage": {**base, "source_w": shortage,
                            "description": f"Source drops to {shortage:,} W; protected services first, the rest "
                                           "share what is left."},
        "feeder_b_trip": {**base, "feeders": {**feeders, "B": False},
                          "description": "Feeder B is open; every classroom load loses supply."},
        "classroom_overload": {**base, "classroom_limit_w": CLASSROOM_OVERLOAD_W,
                               "description": f"Classrooms limited to {CLASSROOM_OVERLOAD_W:,} W; essentials first, "
                                              "then scanned rooms."},
        "hospital_overload": {**base, "hospital_limit_w": HospitalPriorityDemo.OVERLOAD_W,
                              "description": f"Hospital limited to {HospitalPriorityDemo.OVERLOAD_W:,} W; essential "
                                             "equipment first."},
    }


SCENARIOS = _scenarios()
# Commands that change a budget a scenario sets; after one, the site no longer matches its scenario.
BUDGET_COMMANDS = {"campus.capacity", "campus.feeder", "classroom.set_capacity", "classroom.normal", "classroom.reset",
                   "classroom.overload", "hospital.set_capacity", "hospital.normal", "hospital.overload", "hospital.reset"}
log = logging.getLogger(__name__)


class AuditUnavailable(RuntimeError):
    """A state-changing request cannot proceed without its command record."""

# Classroom appliance leaves decompose these campus services (no double counting).
CLASSROOM_PARENT = {c["id"]: c["service_id"] for c in CLASSROOMS}
# Hospital equipment leaves decompose every campus feeder A service.
HOSPITAL_SERVICES = tuple(s["id"] for s in SERVICE_CATALOG if s["feeder"] == "A")


def reconcile_catalog() -> list[str]:
    """Leaf sums must equal their parent service watts; returns any mismatches."""
    services = {s["id"]: s for s in SERVICE_CATALOG}
    problems = []
    for room, parent in CLASSROOM_PARENT.items():
        leaves = sum(item[2] for item in CLASSROOM_LEAVES[room])
        if leaves != services[parent]["watts"]:
            problems.append(f"{room}: leaves {leaves} W != {parent} {services[parent]['watts']} W")
        if services[parent]["feeder"] != "B":
            problems.append(f"{parent} is not on feeder B")
    hospital = {sid: 0 for sid in HOSPITAL_SERVICES}
    for zone, rows in HOSP_LOADS.items():
        for lid, _name, watts, essential in rows:
            parent = HOSP_PARENT.get((zone, lid))
            if parent not in hospital:
                problems.append(f"{zone}.{lid} has no hospital parent service")
                continue
            hospital[parent] += watts
            if essential != (services[parent]["tier"] == "T1"):
                problems.append(f"{zone}.{lid}: essential={essential} but {parent} is {services[parent]['tier']}")
    for sid, leaves in hospital.items():
        if leaves != services[sid]["watts"]:
            problems.append(f"hospital leaves of {sid} {leaves} W != {services[sid]['watts']} W")
    return problems


def _zone_served_w(appliances, zone: str) -> int:
    return sum(a.demand_w for a in APPLIANCES if a.zone == zone and a.id in appliances.applied)


def classroom_headroom_w(grid, appliances) -> int:
    """Feeder B power the classrooms could use: the feeder limit or what the source has left after the
    hospital's applied appliances, whichever is lower (display bound; the optimizer enforces both)."""
    if not grid.feeder_available.get("B", False):
        return 0
    return max(0, min(grid.feeder_limits_w["B"], grid.source_capacity_w - _zone_served_w(appliances, "hospital")))


def hospital_headroom_w(grid, appliances) -> int:
    """Feeder A power the hospital could use, bounded the same way."""
    if not grid.feeder_available.get("A", False):
        return 0
    return max(0, min(grid.feeder_limits_w["A"], grid.source_capacity_w - _zone_served_w(appliances, "classroom")))


class SiteAuthority:
    def __init__(self, grid, classroom, hospital):
        problems = reconcile_catalog()
        if problems:
            raise ValueError("catalog does not reconcile: " + "; ".join(problems))
        self.grid = grid
        self.classroom = classroom
        self.hospital = hospital
        self._lock = threading.RLock()
        self.run_id = grid.run_id
        self.revision = 0
        self.last_command = None
        self.scenario = DEFAULT_SCENARIO
        self.appliances = ApplianceController(lambda: self.grid.clock())
        self._pending_command = None
        self._seen = None
        self.tick()

    def _part_revisions(self):
        return (self.grid.published_revision, self.classroom.published_revision, self.hospital.published_revision)

    def tick(self):
        """Advance every part in a fixed order. The campus service-level allocator still runs as the
        regression fixture and baseline; the appliance-level optimizer makes the decision, and the
        classroom view, hospital view and campus publication are projections of it."""
        with self._lock:
            self.grid.advance()
            self.classroom._advance_evidence()  # activity evidence ranks optional classroom loads
            self.appliances.step(self.grid, self.classroom, self.hospital, self._pending_command)
            self._pending_command = None
            self.classroom.site_decision = self.appliances.view_decision("classroom")
            self.classroom.campus_limit_w = classroom_headroom_w(self.grid, self.appliances)
            self.classroom.campus_feeder_closed = bool(self.grid.feeder_available.get("B", False))
            self.classroom.tick()
            self.hospital.site_decision = self.appliances.view_decision("hospital")
            self.hospital.campus_limit_w = hospital_headroom_w(self.grid, self.appliances)
            self.hospital.campus_feeder_closed = bool(self.grid.feeder_available.get("A", False))
            self.hospital.tick()
            self.grid.leaf_decision = self.appliances.service_watts()
            self.grid.publish()
            seen = self._part_revisions()
            if seen != self._seen:
                self._seen = seen
                self.revision += 1
            if self.grid.history:
                self._sync_history_run()
                snapshot = self.grid.build_snapshot()
                snapshot.site = SiteIdentityResponse.model_validate(self.identity())
                try:
                    self.grid.history.capture(snapshot, self.grid.history_inputs())
                    self.grid.pending_command_identity = None
                except Exception:
                    log.exception("History snapshot recording failed; live controller continues")
            return self.revision

    def command(self, name: str, apply, payload=None):
        """Apply one command, tick all parts, and return (result, receipt)."""
        with self._lock:
            command_id = str(uuid.uuid4())
            if not self.grid.save_command(name, payload or {}, command_id):
                raise AuditUnavailable("Command audit storage is unavailable; no change was applied")
            result = apply()
            self._pending_command = name
            if name in BUDGET_COMMANDS:
                self.scenario = CUSTOM_SCENARIO
            revision = self.tick()
            self.last_command = {"command_id": command_id, "name": name, "run_id": self.run_id,
                                 "applied_revision": revision}
            return result, dict(self.last_command)

    def complete_command(self, receipt, name):
        """Publish a delayed result under its already-persisted command identity."""
        with self._lock:
            self.grid.pending_command_identity = {"command_id": receipt["command_id"], "run_id": receipt["run_id"],
                                                 "action": name, "revision": self.grid.control_revision}
            revision = self.tick()
            self.last_command = {**receipt, "applied_revision": revision}
            return dict(self.last_command)

    def apply_scenario(self, name: str) -> dict:
        """Switch the whole site to a named scenario in one command and one revision."""
        if name not in SCENARIOS:
            raise ValueError(f"unknown scenario {name!r}")
        settings = SCENARIOS[name]

        def apply():
            self.grid.set_capacity(settings["source_w"])
            for feeder, available in settings["feeders"].items():
                self.grid.set_feeder(feeder, available)
            self.classroom.capacity = settings["classroom_limit_w"]
            self.hospital.capacity = settings["hospital_limit_w"]
            self.hospital.fault = None
            self.appliances.reset_requests()
            self.scenario = name

        return self.command("site.scenario", apply, {"scenario": name})[1]

    def restore_zone_supply(self, zone: str) -> None:
        """Full supply / reset on a facility page: close the feeders that zone hangs off and restore the
        source if it was reduced, so the preset can actually deliver its watts. Call inside a command."""
        for feeder in sorted({a.feeder for a in APPLIANCES if a.zone == zone}):
            if not self.grid.feeder_available.get(feeder, True):
                self.grid.set_feeder(feeder, True)
        if self.grid.source_capacity_w < NORMAL_SOURCE_CAPACITY_W:
            self.grid.set_capacity(NORMAL_SOURCE_CAPACITY_W)

    def commit(self, name: str, payload=None) -> dict:
        """For handlers that already applied their mutation: tick all parts and record the receipt."""
        return self.command(name, lambda: None, payload)[1]

    def read(self, project):
        """Run a read-only projection and the identity under one lock, so both describe one revision."""
        with self._lock:
            return project(), self.identity()

    def _sync_history_run(self):
        if self.grid.history and self.grid.history.run_id != self.run_id:
            from app.storage.recorder import HistoryRecorder
            previous = self.grid.history
            self.grid.history = HistoryRecorder(previous.store, self.run_id, previous.clock)

    def new_run(self):
        with self._lock:
            self.run_id = uuid.uuid4().hex[:12]
            self.grid.run_id = self.run_id
            self.grid.pending_command_identity = None
            self.grid.reset_sessions()
            with Session(self.grid.storage.engine) as session:
                session.add(Run(site_id=site_profile.name, run_id=self.run_id,
                                server_epoch=self.grid.server_epoch, started_at=datetime.now(timezone.utc)))
                self.grid.storage.commit(session)
            self._sync_history_run()
            self.tick()
            return self.run_id

    def identity(self) -> dict:
        with self._lock:
            return {"run_id": self.run_id, "revision": self.revision, "profile": PROFILE,
                    "catalog_version": CATALOG_VERSION, "config_hash": CONFIG_HASH, "site_name": CATALOG.name,
                    "scenario": self.scenario}
