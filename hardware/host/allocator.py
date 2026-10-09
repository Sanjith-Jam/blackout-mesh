"""CLASSROOM BENCH allocation: which registered rooms get simulated power.

served = registered AND selected_by_allocator. Unregistered rooms are never eligible.
Rooms are ranked ACTIVE > UNKNOWN > INACTIVE, ties broken by the bench priority order.
The allocator picks the lexicographically best feasible set over that ranking (serve the
best-ranked room if it fits, then the next, ...), which is exact for this objective.
"""
from dataclasses import dataclass, field

ROOMS = ("A", "B", "C")
DEMAND_KW = {"A": 6, "B": 6, "C": 4}   # CLASSROOM BENCH values from the plan, not campus data
NORMAL_BUDGET_KW = 16
SHORTAGE_BUDGET_KW = 6
BENCH_PRIORITY = ("A", "B", "C")        # rules-mode tie-break, labelled BENCH / RULES MODE
ACTIVITY_RANK = {"ACTIVE": 0, "UNKNOWN": 1, "INACTIVE": 2}


@dataclass
class Allocation:
    served: tuple
    order: tuple                     # eligible rooms in rank order
    reasons: dict = field(default_factory=dict)
    used_kw: int = 0
    budget_kw: int = 0


def rank(registered, activity):
    def key(room):
        return (ACTIVITY_RANK[activity.get(room, "UNKNOWN")], BENCH_PRIORITY.index(room))
    return tuple(sorted(registered, key=key))


def allocate(registered, activity, budget_kw) -> Allocation:
    order = rank([r for r in ROOMS if r in registered], activity)
    served, used, reasons = [], 0, {}
    for room in order:
        if used + DEMAND_KW[room] <= budget_kw:
            served.append(room)
            used += DEMAND_KW[room]
            reasons[room] = f"served: rank {order.index(room) + 1}, {DEMAND_KW[room]} kW fits"
        else:
            reasons[room] = f"shed: {DEMAND_KW[room]} kW does not fit in remaining {budget_kw - used} kW"
    for room in ROOMS:
        if room not in registered:
            reasons[room] = "off: not registered"
    return Allocation(tuple(r for r in ROOMS if r in served), order, reasons, used, budget_kw)
