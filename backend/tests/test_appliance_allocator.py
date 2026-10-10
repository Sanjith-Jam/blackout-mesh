"""Appliance-level optimizer: catalog integrity, CP-SAT vs exhaustive oracle, hard constraints."""
import random

import pytest

from app.core import appliances as cat
from app.core.appliance_allocator import (GroupRestorationGate, Item, Problem, exhaustive, objective, solve,
                                          validate)


def test_catalog_has_every_configured_appliance_once_in_six_rooms():
    assert cat.catalog_problems() == []
    assert len(cat.APPLIANCES) == 31
    assert [r["id"] for r in cat.ROOMS] == ["ICU", "Theatre", "Wards", "CR1", "CR2", "CR3"]
    by_room = {r["id"]: [a for a in cat.APPLIANCES if a.room_id == r["id"]] for r in cat.ROOMS}
    assert {k: len(v) for k, v in by_room.items()} == {"ICU": 5, "Theatre": 5, "Wards": 5, "CR1": 5, "CR2": 5, "CR3": 6}
    assert all(a.feeder == "A" for a in cat.APPLIANCES if a.zone == "hospital")
    assert all(a.feeder == "B" for a in cat.APPLIANCES if a.zone == "classroom")
    # Hospital essentials are exactly the equipment on T1 services; nothing was invented or re-rated.
    assert all(a.essential == (a.service_tier == "T1") for a in cat.APPLIANCES if a.zone == "hospital")
    assert sum(a.demand_w for a in cat.APPLIANCES) == 14000


def test_every_appliance_path_uses_configured_edges_only():
    edge_ids = {e["id"] for e in cat.edges()}
    for a in cat.APPLIANCES:
        hops = list(zip(cat.path(a), cat.path(a)[1:]))
        assert hops[0][0] == cat.SOURCE_ID and hops[-1][1] == a.id
        assert all(f"{s}>{d}" in edge_ids for s, d in hops)
    # One branch per appliance, no extra or decorative wires.
    assert sum(1 for e in cat.edges() if e["kind"] == "branch") == len(cat.APPLIANCES)


def _random_problem(rng, n):
    feeders = ["A", "B"]
    classes = ("c0", "c1", "c2", "c3")
    items = []
    for i in range(n):
        items.append(Item(id=f"x{i}", watts=rng.choice([50, 100, 200, 300, 500, 700, 1000]), feeder=rng.choice(feeders),
                          zone=rng.choice(["hospital", "classroom"]), cls=rng.choice(classes),
                          requested=rng.random() > 0.1, reachable=rng.random() > 0.1))
    if n >= 4 and rng.random() < 0.5:  # an indivisible group and a dependency
        items[0] = Item(**{**items[0].__dict__, "group": "g"})
        items[1] = Item(**{**items[1].__dict__, "group": "g"})
        items[2] = Item(**{**items[2].__dict__, "requires": (items[3].id,)})
    total = sum(it.watts for it in items)
    return Problem(items=tuple(items), source_capacity_w=rng.randint(0, total),
                   feeder_limits_w={"A": rng.randint(0, total), "B": rng.randint(0, total)},
                   feeder_available={"A": rng.random() > 0.2, "B": rng.random() > 0.2},
                   zone_limits_w={"hospital": rng.randint(0, total)}, class_order=classes,
                   previous=frozenset(it.id for it in items if rng.random() < 0.5))


@pytest.mark.parametrize("seed", range(150))
def test_cp_sat_matches_the_exhaustive_oracle_on_small_models(seed):
    rng = random.Random(seed)
    problem = _random_problem(rng, rng.randint(1, 11))
    plan = solve(problem)
    assert plan.status == "OPTIMAL" and plan.violations == []
    assert all(stage["status"] == "OPTIMAL" for stage in plan.stages)
    oracle = exhaustive(problem)
    assert objective(problem, plan.served) == objective(problem, oracle)
    assert plan.served == oracle  # the tie-break makes the optimum unique


def _items(*rows, cls="opt"):
    return tuple(Item(id=i, watts=w, feeder=f, zone=z, cls=c) for i, w, f, z, c in rows)


def test_essential_kept_and_optional_shed_in_the_same_room():
    items = _items(("icu.vent", 300, "A", "hospital", "crit"), ("icu.ac", 900, "A", "hospital", "opt"),
                   ("icu.mon", 100, "A", "hospital", "crit"))
    plan = solve(Problem(items, 500, {"A": 6000}, {"A": True}, class_order=("crit", "opt")))
    assert plan.served == {"icu.vent", "icu.mon"}  # the room is not shed as one block


def test_source_feeder_and_zone_limits_hold():
    items = _items(("a", 600, "A", "hospital", "c"), ("b", 600, "B", "classroom", "c"), ("c", 600, "B", "classroom", "c"))
    p = Problem(items, 1500, {"A": 6000, "B": 700}, {"A": True, "B": True}, class_order=("c",))
    assert solve(p).served == {"a", "b"}
    p = Problem(items, 9999, {"A": 9999, "B": 9999}, {"A": True, "B": True}, {"classroom": 600}, ("c",))
    assert solve(p).served == {"a", "b"}


def test_open_feeder_serves_nothing_downstream_and_validator_catches_it():
    items = _items(("a", 100, "A", "hospital", "c"), ("b", 100, "B", "classroom", "c"))
    p = Problem(items, 9999, {"A": 9999, "B": 9999}, {"A": False, "B": True}, class_order=("c",))
    assert solve(p).served == {"b"}
    assert validate(p, {"a", "b"}) == ["a: served across open feeder A"]


def test_priority_order_is_lexicographic_not_weighted():
    # One 1,000 W low-class load never beats a 100 W high-class load.
    items = _items(("hi", 100, "A", "hospital", "hi"), ("lo", 1000, "A", "hospital", "lo"))
    plan = solve(Problem(items, 1000, {"A": 9999}, {"A": True}, class_order=("hi", "lo")))
    assert plan.served == {"hi"}


def test_indivisible_group_and_dependency_are_respected():
    items = (Item("pump", 300, "A", "hospital", "c", group="g"), Item("valve", 100, "A", "hospital", "c", group="g"),
             Item("monitor", 100, "A", "hospital", "c", requires=("hub",)), Item("hub", 100, "A", "hospital", "c"))
    p = Problem(items, 350, {"A": 9999}, {"A": True}, class_order=("c",))
    served = solve(p).served
    assert not validate(p, served)
    assert ("pump" in served) == ("valve" in served)
    assert "monitor" not in served or "hub" in served


def test_infeasible_request_is_shortfall_not_failure():
    items = _items(("vent", 300, "A", "hospital", "crit"))
    plan = solve(Problem(items, 0, {"A": 6000}, {"A": True}, class_order=("crit",)))
    assert plan.status == "OPTIMAL" and plan.served == frozenset()


def test_unproven_plan_is_never_applied(monkeypatch):
    import app.core.appliance_allocator as alloc

    class Broken:
        def __init__(self):
            self.parameters = type("P", (), {})()

        def Solve(self, model):
            return alloc.cp_model.UNKNOWN

        def StatusName(self, status):
            return "UNKNOWN"

    monkeypatch.setattr(alloc.cp_model, "CpSolver", Broken)
    items = _items(("a", 600, "A", "hospital", "c"), ("b", 600, "A", "hospital", "c"))
    p = Problem(items, 700, {"A": 9999}, {"A": True}, class_order=("c",), previous=frozenset({"a", "b"}))
    plan = solve(p)
    assert plan.status == "FALLBACK" and plan.violations == ["solver did not prove optimality"]
    assert validate(p, plan.served) == []  # the fallback is validated, not the unproven result


def test_group_restoration_sheds_at_once_and_restores_one_group_per_second():
    t = [0.0]
    gate = GroupRestorationGate(lambda: t[0])
    everything = frozenset({"a", "b", "c"})
    assert gate.update(everything, "s0", [["a"], ["b", "c"]]) == everything
    t[0] = 1
    assert gate.update(frozenset({"a"}), "s1", [["a"], ["b", "c"]]) == {"a"}  # protective shed is immediate
    t[0] = 2
    assert gate.update(everything, "s0", [["a"], ["b", "c"]]) == {"a"}  # constraints just changed
    for t[0] in (3, 5, 6.9):
        assert gate.update(everything, "s0", [["a"], ["b", "c"]]) == {"a"}
    t[0] = 7.0
    assert gate.update(everything, "s0", [["a"], ["b", "c"]]) == everything  # whole group in one step
