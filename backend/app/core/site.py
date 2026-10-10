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

from app.core.state import CLASSROOMS, SERVICE_CATALOG, site_profile
from app.schemas.snapshot import SiteIdentityResponse
from app.storage.models import Run
from app.visualizers import HOSP_LOADS, HOSP_PARENT, LOADS as CLASSROOM_LEAVES

CATALOG_VERSION = "site-catalog-2026-10-10.1"
PROFILE = "campus"
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


def classroom_headroom_w(grid) -> int:
    """Power the campus can make available to classroom loads on feeder B, from its last published state."""
    snap = grid.published
    if snap is None or not grid.feeder_available.get("B", False):
        return 0
    feeder_a_served = sum(s["watts"] for i, s in enumerate(SERVICE_CATALOG)
                          if s["feeder"] == "A" and snap.modeled_mask & (1 << i))
    return max(0, min(grid.feeder_limits_w["B"], grid.source_capacity_w - feeder_a_served))


def hospital_headroom_w(grid) -> int:
    """Feeder A power the campus allocated to hospital services, from its last published state."""
    snap = grid.published
    if snap is None or not grid.feeder_available.get("A", False):
        return 0
    return sum(s["watts"] for i, s in enumerate(SERVICE_CATALOG)
               if s["feeder"] == "A" and snap.modeled_mask & (1 << i))


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
        self._seen = None
        self.tick()

    def _part_revisions(self):
        return (self.grid.published_revision, self.classroom.published_revision, self.hospital.published_revision)

    def tick(self):
        """Advance every part in a fixed order; campus first so its headroom bounds the classroom view."""
        with self._lock:
            self.grid.tick()
            self.classroom.campus_limit_w = classroom_headroom_w(self.grid)
            self.classroom.campus_feeder_closed = bool(self.grid.feeder_available.get("B", False))
            self.classroom.tick()
            self.hospital.campus_limit_w = hospital_headroom_w(self.grid)
            self.hospital.campus_feeder_closed = bool(self.grid.feeder_available.get("A", False))
            self.hospital.tick()
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
                    "catalog_version": CATALOG_VERSION}
