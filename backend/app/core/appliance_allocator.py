"""Appliance-level allocation: OR-Tools CP-SAT primary, independent validation on every plan.

Each appliance is its own 0/1 decision. Hard constraints: only requested and reachable appliances can
be served, the source, every feeder and every zone budget hold, an open feeder serves nothing, and any
configured indivisible group or dependency holds. The objective is lexicographic, solved as one CP-SAT
stage per level, each fixed at its proven optimum before the next:

  1. served watts of each priority class, in the policy's class order (protected classes first);
  2. fewest switches against the previously applied plan;
  3. a deterministic tie-break that prefers earlier catalog entries.

`validate()` re-checks every hard constraint without using the solver, and `exhaustive()` enumerates
every plan of a small model with the same objective; tests require both to agree with CP-SAT. A plan
that is not OPTIMAL at every stage or fails validation is never applied: the controller keeps a
validated fallback instead and reports it.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

SOLVER = f"OR-Tools CP-SAT {__import__('ortools').__version__}"
MAX_EXHAUSTIVE = 20


@dataclass(frozen=True)
class Item:
    id: str
    watts: int
    feeder: str
    zone: str
    cls: str
    requested: bool = True
    reachable: bool = True
    group: str | None = None
    requires: tuple = ()
    path: tuple = ()


@dataclass(frozen=True)
class Problem:
    items: tuple
    source_capacity_w: int
    feeder_limits_w: dict
    feeder_available: dict
    zone_limits_w: dict = field(default_factory=dict)
    class_order: tuple = ()
    previous: frozenset = frozenset()
    edge_limits_w: dict = field(default_factory=dict)


def _eligible(problem: Problem, item: Item) -> bool:
    return item.requested and item.reachable and problem.feeder_available.get(item.feeder, False)


def validate(problem: Problem, served) -> list[str]:
    """Every hard-constraint violation of a plan; empty means the plan may be applied."""
    served = set(served)
    by_id = {it.id: it for it in problem.items}
    violations = [f"{sid}: not in the catalog" for sid in served if sid not in by_id]
    on = [by_id[s] for s in served if s in by_id]
    for it in on:
        if not it.requested:
            violations.append(f"{it.id}: served without a request")
        if not it.reachable:
            violations.append(f"{it.id}: served while unreachable")
        if not problem.feeder_available.get(it.feeder, False):
            violations.append(f"{it.id}: served across open feeder {it.feeder}")
        for dep in it.requires:
            if dep not in served:
                violations.append(f"{it.id}: requires {dep}, which is not served")
    total = sum(it.watts for it in on)
    if total > problem.source_capacity_w:
        violations.append(f"source: {total} W exceeds {problem.source_capacity_w} W")
    for feeder, limit in problem.feeder_limits_w.items():
        w = sum(it.watts for it in on if it.feeder == feeder)
        if w > limit:
            violations.append(f"feeder {feeder}: {w} W exceeds {limit} W")
    for zone, limit in problem.zone_limits_w.items():
        w = sum(it.watts for it in on if it.zone == zone)
        if w > limit:
            violations.append(f"zone {zone}: {w} W exceeds {limit} W")
    for edge, limit in problem.edge_limits_w.items():
        watts = sum(it.watts for it in on if edge in it.path)
        if watts > limit:
            violations.append(f"edge {edge}: {watts} W exceeds {limit} W")
    for it in on:
        if any(edge not in problem.edge_limits_w for edge in it.path):
            violations.append(f"{it.id}: path contains an unconfigured edge")
    groups: dict[str, list[Item]] = {}
    for it in problem.items:
        if it.group:
            groups.setdefault(it.group, []).append(it)
    for name, members in groups.items():
        states = {m.id in served for m in members}
        if len(states) > 1:
            violations.append(f"group {name}: indivisible group partly served")
    return violations


def objective(problem: Problem, served) -> tuple:
    """The lexicographic objective of a plan (larger is better); shared by CP-SAT stages and the oracle."""
    served = set(served)
    n = len(problem.items)
    per_class = tuple(sum(it.watts for it in problem.items if it.cls == cls and it.id in served)
                      for cls in problem.class_order)
    switches = sum(1 for it in problem.items if (it.id in served) != (it.id in problem.previous))
    tiebreak = sum(1 << (n - 1 - i) for i, it in enumerate(problem.items) if it.id in served)
    return per_class + (-switches, tiebreak)


@dataclass
class Plan:
    served: frozenset
    status: str                  # OPTIMAL | FALLBACK
    stages: list                 # [{"stage", "status", "value"}]
    solve_ms: float
    violations: list
    objective: tuple
    solver: str = SOLVER


def solve(problem: Problem, time_limit_s: float = 2.0) -> Plan:
    """Sequential lexicographic CP-SAT; every stage must be proven OPTIMAL."""
    started = time.perf_counter()
    model = cp_model.CpModel()
    items = problem.items
    n = len(items)
    x = {it.id: model.NewBoolVar(it.id) for it in items}
    for it in items:
        if not _eligible(problem, it):
            model.Add(x[it.id] == 0)
        for dep in it.requires:
            if dep in x:
                model.Add(x[it.id] <= x[dep])
            else:
                model.Add(x[it.id] == 0)
    model.Add(sum(it.watts * x[it.id] for it in items) <= problem.source_capacity_w)
    for feeder, limit in problem.feeder_limits_w.items():
        model.Add(sum(it.watts * x[it.id] for it in items if it.feeder == feeder) <= limit)
    for zone, limit in problem.zone_limits_w.items():
        model.Add(sum(it.watts * x[it.id] for it in items if it.zone == zone) <= limit)
    for edge, limit in problem.edge_limits_w.items():
        model.Add(sum(it.watts * x[it.id] for it in items if edge in it.path) <= limit)
    for it in items:
        if any(edge not in problem.edge_limits_w for edge in it.path):
            model.Add(x[it.id] == 0)
    groups: dict[str, list[Item]] = {}
    for it in items:
        if it.group:
            groups.setdefault(it.group, []).append(it)
    for members in groups.values():
        for m in members[1:]:
            model.Add(x[m.id] == x[members[0].id])

    levels = [(f"class:{cls}", sum(it.watts * x[it.id] for it in items if it.cls == cls)) for cls in problem.class_order]
    levels.append(("switching", -sum((1 - x[it.id]) if it.id in problem.previous else x[it.id] for it in items)))
    levels.append(("tiebreak", sum((1 << (n - 1 - i)) * x[it.id] for i, it in enumerate(items))))

    stages = []
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.max_time_in_seconds = time_limit_s
    status_ok = True
    for name, expr in levels:
        model.Maximize(expr)
        status = solver.Solve(model)
        label = solver.StatusName(status)
        if status != cp_model.OPTIMAL:
            stages.append({"stage": name, "status": label, "value": None})
            status_ok = False
            break
        value = int(round(solver.ObjectiveValue()))
        stages.append({"stage": name, "status": label, "value": value})
        model.Add(expr == value)
    served = frozenset(it.id for it in items if status_ok and solver.Value(x[it.id]))
    elapsed = (time.perf_counter() - started) * 1000
    violations = validate(problem, served) if status_ok else ["solver did not prove optimality"]
    if status_ok and not violations:
        return Plan(served, "OPTIMAL", stages, elapsed, [], objective(problem, served))
    fallback = conservative_fallback(problem)
    return Plan(fallback, "FALLBACK", stages, elapsed, violations, objective(problem, fallback))


def conservative_fallback(problem: Problem) -> frozenset:
    """Never-unvalidated fallback: keep the previous plan's still-eligible loads, then shed the lowest
    classes until the plan validates. Used only when CP-SAT cannot prove an optimum."""
    rank = {cls: i for i, cls in enumerate(problem.class_order)}
    kept = [it for it in problem.items if it.id in problem.previous and _eligible(problem, it)]
    kept.sort(key=lambda it: (rank.get(it.cls, len(rank)), problem.items.index(it)))
    served = {it.id for it in kept}
    for it in reversed(kept):
        if not validate(problem, served):
            break
        served.discard(it.id)
        for other in problem.items:  # dropping a load drops its dependants and group
            if it.id in other.requires or (it.group and other.group == it.group):
                served.discard(other.id)
    return frozenset(served) if not validate(problem, served) else frozenset()


def exhaustive(problem: Problem) -> frozenset:
    """Oracle for small models: enumerate every plan, keep valid ones, maximize the same objective."""
    items = problem.items
    if len(items) > MAX_EXHAUSTIVE:
        raise ValueError(f"exhaustive oracle supports at most {MAX_EXHAUSTIVE} appliances")
    best, best_key = frozenset(), None
    for mask in range(1 << len(items)):
        served = frozenset(it.id for i, it in enumerate(items) if mask >> i & 1)
        if validate(problem, served):
            continue
        key = objective(problem, served)
        if best_key is None or key > best_key:
            best, best_key = served, key
    return best


class GroupRestorationGate:
    """The existing restoration policy at appliance level: shedding is immediate; additions wait for
    5 s of unchanged constraints and 3 s after the last shed, then restore one priority group per
    second (a group is one priority class in one room), highest class first."""

    STABLE_S, AFTER_SHED_S, STEP_S = 5, 3, 1

    def __init__(self, clock):
        self.clock = clock
        self.applied: frozenset | None = None
        self.signature = None
        self.stable_since = self.last_shed = self.last_restored = None

    def update(self, proposed: frozenset, signature, groups: list, now=None, check=None) -> frozenset:
        """`check(plan)` returns violations; a restoration step that would make the plan invalid
        (for example a dependant before its dependency) waits for a later group."""
        now = self.clock() if now is None else now
        if self.applied is None:
            self.applied, self.signature = proposed, signature
            self.stable_since = self.last_shed = self.last_restored = now
            return self.applied
        if signature != self.signature:
            self.signature, self.stable_since = signature, now
        shed = self.applied - proposed
        if shed:
            self.applied = self.applied & proposed
            self.last_shed = now
        additions = proposed - self.applied
        if (additions and now - self.stable_since >= self.STABLE_S and now - self.last_shed >= self.AFTER_SHED_S
                and now - self.last_restored >= self.STEP_S):
            for group in groups:
                step = additions & frozenset(group)
                if step and not (check and check(self.applied | step)):
                    self.applied = self.applied | step
                    self.last_restored = now
                    break
        return self.applied

    def state(self, now=None) -> dict:
        now = self.clock() if now is None else now
        if self.stable_since is None:
            return {"stable_for_s": None, "since_last_shed_s": None}
        return {"stable_for_s": round(now - self.stable_since, 2), "since_last_shed_s": round(now - self.last_shed, 2),
                "stable_required_s": self.STABLE_S, "after_shed_required_s": self.AFTER_SHED_S, "step_s": self.STEP_S}
