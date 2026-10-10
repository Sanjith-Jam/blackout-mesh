"""The site's one appliance-level decision, owned by the site authority.

Each tick builds an allocation problem from authoritative state only: configured demand and ratings,
the requested operating state of every appliance, the source capacity and feeder switch states set
by commands, the zone budgets, classroom sessions and the classroom activity evidence. It never reads
diagnosis hypotheses or scenario labels. CP-SAT proposes, the validator checks, and the restoration
gate stages additions; the classroom and hospital views and the campus service masks are projections
of the applied result, so every drawing and indicator shows the same decision.
"""
from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timezone

from app.core import appliances as cat
from app.core.appliance_allocator import GroupRestorationGate, Item, Problem, solve, validate

SERVED, PENDING, SHED, UNREACHABLE, NOT_REQUESTED = "SERVED", "PENDING_RESTORATION", "SHED", "UNREACHABLE", "NOT_REQUESTED"
APPLIANCE_EVENTS = 200


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


class ApplianceController:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.gate = GroupRestorationGate(clock)
        self.requested = {a.id: True for a in cat.APPLIANCES}  # requested operating state (ON) per appliance
        self.problem: Problem | None = None
        self.plan = None
        self.applied: frozenset = frozenset()
        self.applied_violations: list = []
        self.last_key = None
        self.solves = 0
        self.decision_revision = 0
        self.states: dict[str, str] = {}
        self.events: deque = deque(maxlen=APPLIANCE_EVENTS)
        self.last_command: str | None = None
        self.reasons: dict[str, dict] = {}

    # ---- inputs -------------------------------------------------------------------------------
    def set_requested(self, appliance_id: str, requested: bool):
        if appliance_id not in cat.APPLIANCE_BY_ID:
            raise ValueError(f"unknown appliance {appliance_id!r}")
        self.requested[appliance_id] = bool(requested)

    def reset_requests(self):
        self.requested = {a.id: True for a in cat.APPLIANCES}

    @staticmethod
    def classify(appliance, sessions, activity) -> str:
        static = appliance.static_class()
        if static is not None:
            return static
        if appliance.room_id not in sessions:
            return cat.IDLE
        state = (activity.get(appliance.room_id) or {}).get("state", "UNKNOWN")
        return {"ACTIVE": cat.ACTIVE, "INACTIVE": cat.INACTIVE}.get(state, cat.UNKNOWN)

    def build_problem(self, grid, classroom, hospital) -> Problem:
        sessions = set(classroom.scanned)
        activity = {r["id"]: classroom.activity(r["id"]) for r in cat.ROOMS if r["zone"] == "classroom"}
        upstream_lost = bool(hospital.fault and hospital.fault.get("kind") == "upstream_loss")
        items = []
        for a in cat.APPLIANCES:
            reachable = bool(grid.feeder_available.get(a.feeder, False)) and grid.source_capacity_w > 0
            if a.zone == "hospital" and upstream_lost:
                reachable = False
            items.append(Item(id=a.id, watts=a.demand_w, feeder=a.feeder, zone=a.zone,
                              cls=self.classify(a, sessions, activity), requested=self.requested[a.id],
                              reachable=reachable, group=a.indivisible_group, requires=a.requires))
        return Problem(items=tuple(items), source_capacity_w=grid.source_capacity_w,
                       feeder_limits_w=dict(grid.feeder_limits_w), feeder_available=dict(grid.feeder_available),
                       zone_limits_w={"hospital": hospital.capacity, "classroom": classroom.capacity},
                       class_order=cat.CLASS_ORDER[grid.policy.name], previous=self.applied)

    # ---- control step -------------------------------------------------------------------------
    def step(self, grid, classroom, hospital, command: str | None = None):
        if command:
            self.last_command = command
        problem = self.build_problem(grid, classroom, hospital)
        key = (problem.items, problem.source_capacity_w, tuple(sorted(problem.feeder_limits_w.items())),
               tuple(sorted(problem.feeder_available.items())), tuple(sorted(problem.zone_limits_w.items())),
               problem.class_order, problem.previous)
        if key != self.last_key or self.plan is None:
            self.plan = solve(problem)
            self.solves += 1
            self.last_key = key
        self.problem = problem
        rank = {c: i for i, c in enumerate(problem.class_order)}
        groups = []
        for item in sorted(problem.items, key=lambda it: (rank.get(it.cls, 99), cat.APPLIANCE_BY_ID[it.id].room_id)):
            label = (item.cls, cat.APPLIANCE_BY_ID[item.id].room_id)
            if not groups or groups[-1][0] != label:
                groups.append((label, []))
            groups[-1][1].append(item.id)
        signature = key[1:5]
        applied = self.gate.update(self.plan.served, signature, [ids for _, ids in groups],
                                   check=lambda plan: validate(problem, plan))
        self.applied_violations = validate(problem, applied)
        if self.applied_violations:  # never publish an invalid applied plan
            applied = self.gate.applied = frozenset(i for i in applied if i in self.plan.served)
            self.applied_violations = validate(problem, applied)
        changed = applied != self.applied
        self.applied = applied
        self._record_states(problem)
        if changed:
            self.decision_revision += 1
        return self

    # ---- outputs ------------------------------------------------------------------------------
    def state_of(self, item) -> str:
        if not item.requested:
            return NOT_REQUESTED
        if not item.reachable:
            return UNREACHABLE
        if item.id in self.applied:
            return SERVED
        if item.id in self.plan.served:
            return PENDING
        return SHED

    def _reason(self, problem: Problem, item) -> dict:
        state = self.state_of(item)
        a = cat.APPLIANCE_BY_ID[item.id]
        if state == NOT_REQUESTED:
            return {"code": "NOT_REQUESTED", "text": f"{a.name} is switched off by request; it draws no modeled power."}
        if state == UNREACHABLE:
            if not problem.feeder_available.get(a.feeder, False):
                return {"code": "FEEDER_OPEN", "text": f"Feeder {a.feeder} is open, so no path from the source reaches {a.name}."}
            if problem.source_capacity_w <= 0:
                return {"code": "SOURCE_ZERO", "text": "The source has no capacity."}
            return {"code": "UPSTREAM_LOSS", "text": f"The {a.room_id} supply is cut by the injected upstream-loss fault."}
        if state == SERVED:
            return {"code": "SERVED", "text": f"Served by the optimizer ({cat.CLASS_LABELS[item.cls]})."}
        if state == PENDING:
            return {"code": "PENDING_RESTORATION",
                    "text": "Selected by the optimizer; waiting for the restoration gate (stable constraints, then one priority group per second)."}
        served = [it for it in problem.items if it.id in self.plan.served]
        total = sum(it.watts for it in served)
        binding = []
        if total + item.watts > problem.source_capacity_w:
            binding.append(("SOURCE_CAPACITY", f"source has {max(0, problem.source_capacity_w - total):,} W left of {problem.source_capacity_w:,} W"))
        fw = sum(it.watts for it in served if it.feeder == item.feeder)
        if fw + item.watts > problem.feeder_limits_w.get(item.feeder, 0):
            binding.append(("FEEDER_CAPACITY", f"feeder {item.feeder} has {max(0, problem.feeder_limits_w[item.feeder] - fw):,} W left"))
        zl = problem.zone_limits_w.get(item.zone)
        zw = sum(it.watts for it in served if it.zone == item.zone)
        if zl is not None and zw + item.watts > zl:
            binding.append(("ZONE_BUDGET", f"{item.zone} budget has {max(0, zl - zw):,} W left of {zl:,} W"))
        if not binding:
            return {"code": "SHED_LOWER_PRIORITY", "text": "Shed: a higher-priority plan uses the remaining capacity."}
        return {"code": "SHED_" + binding[0][0],
                "text": f"Shed: it needs {item.watts:,} W but the " + "; the ".join(b[1] for b in binding)
                        + f" after higher-priority loads ({cat.CLASS_LABELS[item.cls]}).",
                "binding": [b[0] for b in binding]}

    def _record_states(self, problem):
        now = _now_iso()
        for item in problem.items:
            state = self.state_of(item)
            self.reasons[item.id] = self._reason(problem, item)
            previous = self.states.get(item.id)
            if previous != state:
                self.states[item.id] = state
                if previous is not None:
                    self.events.append({"timestamp": now, "appliance_id": item.id, "from": previous, "to": state,
                                        "reason": self.reasons[item.id]["code"], "command": self.last_command,
                                        "provenance": "MODELED"})

    def service_watts(self) -> dict:
        """Per campus service: requested, commanded (optimizer) and served (applied) watts."""
        out = {}
        for a in cat.APPLIANCES:
            row = out.setdefault(a.service_id, {"requested_w": 0, "commanded_w": 0, "served_w": 0})
            item = next(it for it in self.problem.items if it.id == a.id)
            if item.requested:
                row["requested_w"] += a.demand_w
                if a.id in self.plan.served:
                    row["commanded_w"] += a.demand_w
                if a.id in self.applied:
                    row["served_w"] += a.demand_w
        return out

    def view_decision(self, zone: str) -> dict:
        """(room, key) -> (commanded, applied, reachable) for the classroom or hospital view."""
        out = {}
        for item in self.problem.items:
            a = cat.APPLIANCE_BY_ID[item.id]
            if a.zone == zone:
                out[(a.room_id, a.key)] = (item.id in self.plan.served, item.id in self.applied, item.reachable,
                                           self.reasons[item.id]["text"])
        return out

    def summary(self) -> dict:
        p, plan = self.problem, self.plan
        return {"solver": plan.solver, "status": plan.status, "stages": plan.stages, "solve_ms": round(plan.solve_ms, 2),
                "proposed_violations": plan.violations, "applied_violations": self.applied_violations,
                "validated": not plan.violations and not self.applied_violations,
                "class_order": list(p.class_order), "class_labels": {c: cat.CLASS_LABELS[c] for c in p.class_order},
                "solves": self.solves, "decision_revision": self.decision_revision,
                "restoration": self.gate.state()}
