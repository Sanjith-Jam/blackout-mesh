"""Allocation benchmark against fair baselines with external outcome metrics (#20).

Every policy sees the same exogenous timeline (capacity, feeder availability, booked rooms and, for
ML policies, the same classifier outputs), the same feasibility limits and the same restoration gate.
True occupancy is used only by the evaluator, never by a deployable policy. The oracle policy reads
it on purpose and is reported as an upper bound, not a candidate.

Outcome metrics are defined independently of the allocator's own objective:
critical unmet Wh, essential unmet Wh, occupied-room service time, worst-room starvation,
switching count, recovery latency and constraint violations. Watt-hours integrate power over
simulated time; they are not measured energy savings.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field

from app.core.allocator import allocate, feasible, fixed_priority_mask
from app.core.restoration import RestorationGate
from app.core.safety import RANK_DWELL_READINGS, SAFETY_POLICY_VERSION, ActivityGuard, RankDwell
from app.core.state import SERVICE_CATALOG
from benchmarks.citylearn_metrics import _equity_distribution_metrics

BENCHMARK_VERSION = "alloc-bench-2026-10-10.3"
STEP_S = 5.0
ROOMS = ("CR1", "CR2", "CR3")
ROOM_BIT = {"CR1": 3, "CR2": 4, "CR3": 5}
CRITICAL_BITS = (0, 1)
ROOM_ESSENTIAL_W = 700  # lighting 100 + computers 600 per classroom (#22)
LIMITS = {"A": 6000, "B": 8000}
NORMAL_CAPACITY_W = 14000

# Classifier confusion rates per true state (pred ACTIVE, INACTIVE, UNKNOWN), from backend/models/manifest.json.
CLASSIFIERS = {
    "perfect": {"occupied": (1.0, 0.0, 0.0), "empty": (0.0, 1.0, 0.0)},
    "validation_rates": {"occupied": (656 / 802, 68 / 802, 78 / 802), "empty": (205 / 1764, 1491 / 1764, 68 / 1764)},
    "heavy_errors": {"occupied": (0.55, 0.30, 0.15), "empty": (0.30, 0.55, 0.15)},
}


# ---- exogenous timeline -------------------------------------------------------------------

@dataclass(frozen=True)
class Step:
    t: float
    capacity_w: int
    feeders: tuple  # (("A", bool), ("B", bool))
    booked: tuple   # rooms with a session (requested load)


@dataclass
class Timeline:
    scenario: str
    seed: int
    steps: list
    occupied: list = field(repr=False)        # hidden truth, evaluator only: list[dict room->bool]
    predictions: dict = field(repr=False)     # classifier name -> list[dict room->raw prediction]

    def input_digest(self) -> str:
        """Hash of what policies may see (no truth), to prove every policy got identical inputs."""
        visible = [(s.t, s.capacity_w, s.feeders, s.booked) for s in self.steps]
        return hashlib.sha256(json.dumps([visible, self.predictions], sort_keys=True).encode()).hexdigest()


SCENARIOS = {
    # name: list of (start_s, end_s, capacity_w or None, feeder overrides)
    "shortage_6kw": [(600, 1500, 6000, {})],
    "deep_shortage_4kw": [(600, 1500, 4000, {})],
    "feeder_b_loss": [(600, 1200, None, {"B": False})],
    "feeder_a_loss": [(600, 1200, None, {"A": False})],
    "insufficient_critical_2kw": [(600, 1200, 2000, {})],
    "zero_supply": [(600, 900, 0, {})],
    "recovery_chatter": [(600 + k * 60, 630 + k * 60, 6000, {}) for k in range(10)],
}
DURATION_S = 2400


def make_timeline(scenario: str, seed: int) -> Timeline:
    rng = random.Random(f"{scenario}:{seed}")
    n = int(DURATION_S / STEP_S)
    # Room sessions: booked in blocks; a booked room is actually occupied most, not all, of the time.
    booked = {r: [False] * n for r in ROOMS}
    occupied = {r: [False] * n for r in ROOMS}
    for r in ROOMS:
        i = 0
        while i < n:
            length = rng.randint(60, 240)  # 5–20 min blocks
            is_booked = rng.random() < 0.7
            show_up = rng.random() < 0.7    # booked but empty ~30% of sessions
            for j in range(i, min(n, i + length)):
                booked[r][j] = is_booked
                occupied[r][j] = is_booked and show_up
            i += length
    steps = []
    for k in range(n):
        t = k * STEP_S
        cap, feeders = NORMAL_CAPACITY_W, {"A": True, "B": True}
        for start, end, c, f in SCENARIOS[scenario]:
            if start <= t < end:
                cap = c if c is not None else cap
                feeders.update(f)
        steps.append(Step(t, cap, tuple(sorted(feeders.items())), tuple(r for r in ROOMS if booked[r][k])))
    truth = [{r: occupied[r][k] for r in ROOMS} for k in range(n)]
    predictions = {}
    for name, rates in CLASSIFIERS.items():
        prng = random.Random(f"{scenario}:{seed}:{name}")
        series = []
        for k in range(n):
            row = {}
            for r in ROOMS:
                pa, pi, pu = rates["occupied" if truth[k][r] else "empty"]
                x = prng.random()
                state = "ACTIVE" if x < pa else "INACTIVE" if x < pa + pi else "UNKNOWN"
                row[r] = {"state": state, "score": {"ACTIVE": 0.9, "INACTIVE": 0.1, "UNKNOWN": None}[state],
                          "reason": f"benchmark classifier {name}", "model_version": name}
            series.append(row)
        predictions[name] = series
    return Timeline(scenario, seed, steps, truth, predictions)


# ---- policies (identical inputs; only ML policies read predictions; only oracle reads truth) ----

def requested_mask(step: Step) -> int:
    return 0b111 | sum(1 << ROOM_BIT[r] for r in step.booked)


def _greedy(order, step):
    cap, avail = step.capacity_w, dict(step.feeders)
    req, mask = requested_mask(step), 0
    for bit in order:
        if req & (1 << bit) and feasible(mask | (1 << bit), SERVICE_CATALOG, cap, LIMITS, avail):
            mask |= 1 << bit
    return mask


class FixedPriority:
    name, deployable = "fixed_priority", True

    def decide(self, k, step, timeline, previous):
        return fixed_priority_mask(SERVICE_CATALOG, step.capacity_w, LIMITS, dict(step.feeders), requested_mask(step))


class EssentialsFirstNoML:
    """Critical circuits, then booked classrooms in room order (their essentials), then the pump."""
    name, deployable = "essentials_first_no_ml", True

    def decide(self, k, step, timeline, previous):
        return _greedy((0, 1, 3, 4, 5, 2), step)


class RoundRobin:
    """Critical first; optional services rotate so the least recently served goes first."""
    name, deployable = "round_robin", True

    def __init__(self):
        self.last_served = {b: -1 for b in (2, 3, 4, 5)}

    def decide(self, k, step, timeline, previous):
        optional = sorted((2, 3, 4, 5), key=lambda b: (self.last_served[b], b))
        mask = _greedy((0, 1, *optional), step)
        for b in optional:
            if mask & (1 << b):
                self.last_served[b] = k
        return mask


class Proposed:
    """The deployed path: classifier output -> ActivityGuard (#22) -> RankDwell -> exact allocator.

    dwell=False is the previous path without rank hysteresis, kept as an ablation.
    """
    deployable = True

    def __init__(self, classifier: str | None, dwell: bool = True):
        self.classifier = classifier
        base = f"proposed[{classifier}]" if classifier else "proposed[no_ml_unknown]"
        self.name = base if dwell or classifier is None else base.replace("proposed[", "proposed_no_dwell[")
        self.guard = ActivityGuard()
        self.dwell = RankDwell(RANK_DWELL_READINGS) if dwell else None

    def decide(self, k, step, timeline, previous):
        if self.classifier is None:
            activity = {r: {"state": "UNKNOWN"} for r in ROOMS}
        else:
            raw = timeline.predictions[self.classifier][k]
            activity = {r: self.guard.update(r, raw[r], k) for r in ROOMS}
            if self.dwell:
                activity = {r: self.dwell.update(r, activity[r], k) for r in ROOMS}
        return allocate(SERVICE_CATALOG, step.capacity_w, LIMITS, dict(step.feeders), requested_mask(step), activity, previous)


class Oracle:
    """Upper bound only: reads true occupancy, which no deployable policy can."""
    name, deployable = "oracle_occupancy_upper_bound", False

    def decide(self, k, step, timeline, previous):
        truth = timeline.occupied[k]
        activity = {r: {"state": "ACTIVE" if truth[r] else "INACTIVE"} for r in ROOMS}
        return allocate(SERVICE_CATALOG, step.capacity_w, LIMITS, dict(step.feeders), requested_mask(step), activity, previous)


def all_policies():
    return [FixedPriority(), EssentialsFirstNoML(), RoundRobin(), Proposed(None),
            *(Proposed(c) for c in CLASSIFIERS), *(Proposed(c, dwell=False) for c in CLASSIFIERS), Oracle()]


# ---- execution with the shared restoration gate --------------------------------------------

def run_policy(policy, timeline: Timeline) -> list[int]:
    clock = [0.0]
    gate = RestorationGate(lambda: clock[0])
    applied_masks, previous = [], 0b111111
    gate.update(0b111111, None, range(6))
    for k, step in enumerate(timeline.steps):
        clock[0] = step.t
        proposed = policy.decide(k, step, timeline, previous)
        signature = (step.capacity_w, step.feeders, step.booked)
        applied = gate.update(proposed, signature, range(6)) & requested_mask(step)
        applied_masks.append(applied)
        previous = applied
    return applied_masks


# ---- evaluator (the only place true occupancy is used) -------------------------------------

def evaluate(timeline: Timeline, masks: list[int]) -> dict:
    dt_h = STEP_S / 3600.0
    crit_unmet = ess_unmet = served_wh = 0.0
    occupied_served_s = occupied_requested_s = 0.0
    switches = violations = 0
    starvation = {r: 0.0 for r in ROOMS}
    room_requested_s = {r: 0.0 for r in ROOMS}
    room_served_s = {r: 0.0 for r in ROOMS}
    worst = 0.0
    recovery = []  # one entry per return to normal supply: step it returned, step all requests were served
    prev = None
    disturbed = False
    for k, (step, mask) in enumerate(zip(timeline.steps, masks)):
        avail = dict(step.feeders)
        if not feasible(mask, SERVICE_CATALOG, step.capacity_w, LIMITS, avail):
            violations += 1
        req = requested_mask(step)
        for b in CRITICAL_BITS:
            if req & (1 << b) and not mask & (1 << b):
                crit_unmet += SERVICE_CATALOG[b]["watts"] * dt_h
        for r in step.booked:
            if not mask & (1 << ROOM_BIT[r]):
                ess_unmet += ROOM_ESSENTIAL_W * dt_h
        served_wh += sum(s["watts"] for i, s in enumerate(SERVICE_CATALOG) if mask & (1 << i)) * dt_h
        for r in ROOMS:
            if r in step.booked and timeline.occupied[k][r]:
                occupied_requested_s += STEP_S
                room_requested_s[r] += STEP_S
                if mask & (1 << ROOM_BIT[r]):
                    occupied_served_s += STEP_S
                    room_served_s[r] += STEP_S
                    starvation[r] = 0.0
                else:
                    starvation[r] += STEP_S
                    worst = max(worst, starvation[r])
            else:
                starvation[r] = 0.0
        if prev is not None:
            switches += bin(prev ^ mask).count("1")
        prev = mask
        normal = step.capacity_w >= NORMAL_CAPACITY_W and all(v for _, v in step.feeders)
        if not normal:
            disturbed = True
        elif disturbed:
            disturbed = False
            recovery.append({"start": k, "end": None})
        if recovery and recovery[-1]["end"] is None and normal and mask == req:
            recovery[-1]["end"] = k
    latencies = [(r["end"] - r["start"]) * STEP_S for r in recovery if r["end"] is not None]
    unrecovered = sum(1 for r in recovery if r["end"] is None)
    room_fractions = {r: room_served_s[r] / room_requested_s[r] if room_requested_s[r] else None for r in ROOMS}
    # Compare service fractions, excluding rooms with no occupied demand; all-zero service is undefined.
    gini = _equity_distribution_metrics([v for v in room_fractions.values() if v is not None])["equity_gini_benefit"]
    return {"critical_unmet_wh": round(crit_unmet, 3), "essential_unmet_wh": round(ess_unmet, 3),
            "occupied_service_fraction": round(occupied_served_s / occupied_requested_s, 4) if occupied_requested_s else None,
            "occupied_requested_s": occupied_requested_s,
            "occupied_service_by_room": {r: {"requested_s": room_requested_s[r], "served_s": room_served_s[r],
                                             "fraction": round(room_fractions[r], 4) if room_fractions[r] is not None else None}
                                         for r in ROOMS},
            "occupied_service_gini": round(gini, 4) if gini is not None else None,
            "worst_room_starvation_s": worst, "switching_count": switches,
            "recovery_latency_s_max": max(latencies) if latencies else None,
            "recoveries": len(recovery), "unrecovered": unrecovered,
            "constraint_violations": violations, "served_wh": round(served_wh, 3), "steps": len(masks)}


def run_benchmark(scenarios=None, seeds=range(5)) -> dict:
    scenarios = list(scenarios or SCENARIOS)
    runs = []
    for scenario in scenarios:
        for seed in seeds:
            timeline = make_timeline(scenario, seed)
            digest = timeline.input_digest()
            for policy in all_policies():
                masks = run_policy(policy, timeline)
                runs.append({"scenario": scenario, "seed": seed, "policy": policy.name,
                             "deployable": policy.deployable, "input_digest": digest,
                             **evaluate(timeline, masks)})
    return {"benchmark_version": BENCHMARK_VERSION, "safety_policy_version": SAFETY_POLICY_VERSION,
            "step_s": STEP_S, "duration_s": DURATION_S, "seeds": list(seeds), "scenarios": scenarios,
            "classifiers": {k: {"occupied (A,I,U)": [round(x, 4) for x in v["occupied"]],
                                "empty (A,I,U)": [round(x, 4) for x in v["empty"]]} for k, v in CLASSIFIERS.items()},
            "runs": runs}
