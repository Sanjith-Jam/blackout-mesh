import uuid
"""Joint switch/load recovery: oracle agreement, refusals, proposals and the evidence gate."""
import itertools
import random
from datetime import datetime, timedelta, timezone

import pytest

from app.api.district import DistrictAction, DistrictActionName, DistrictObservation
from app.district import recovery
from app.district.authority import DistrictAuthority
from app.district.profile import DistrictProfile
from app.district.recovery import config_problem, evaluate, optimize


def passed(*args, **kwargs):
    return {"status": "PASSED", "reason": "test double", "violations": []}


def line(edge_id, a, b, limit_w=10_000, kind="branch", normally_open=False):
    return {"id": edge_id, "from": a, "to": b, "kind": kind, "component_type": "DistributionBranchBase",
            "voltage_v": 400, "length_m": 30.0, "rating_a": 100, "limit_w": limit_w, "normally_open": normally_open}


def case(loads, edges, capacity, critical):
    """loads: {node_id: watts}. Every load node is its own building."""
    nodes = [{"id": "S", "role": "source", "voltage_v": 400}]
    named = {edge[key] for edge in edges for key in ("from", "to")} - {"S"}
    nodes += [{"id": item, "role": "load" if item in loads else "junction", "voltage_v": 400,
               **({"building_id": item} if item in loads else {})} for item in sorted(named)]
    profile = DistrictProfile.model_validate({
        "schema_version": "district-profile-v1", "id": "fixture", "provenance": "CONFIGURED_SIMULATED_ASSUMPTION",
        "source_capacity_w": capacity, "demand_basis": "hourly_trace_weights", "local_supply_mode": "grid_following",
        "buildings": [{"building_id": item, "tier": "critical" if item in critical else "noncritical",
                       "rationale": "fixture", "demand_weight": watts} for item, watts in sorted(loads.items())]})
    total = sum(loads.values())
    trace = {"provenance": "FIXTURE", "profile": [{"demand_w": total, "grid_import_w": total}]}
    return {"nodes": nodes, "edges": edges}, profile, trace


def first_benefit(topology, profile, trace, faults):
    """The previous heuristic: first tie by ID that increases served W."""
    _, base, _ = evaluate(topology, profile, trace, 0, faults, frozenset())
    for tie in sorted(edge["id"] for edge in topology["edges"] if edge["kind"] == "tie"):
        if config_problem(topology, faults, frozenset({tie})):
            continue
        _, loads, _ = evaluate(topology, profile, trace, 0, faults, frozenset({tie}))
        if sum(load["served_w"] for load in loads) > sum(load["served_w"] for load in base):
            return frozenset({tie}), loads
    return frozenset(), base


def oracle(topology, profile, trace, faults):
    """Independent: networkx forest test + min-cost max-flow per tie subset."""
    nx = pytest.importorskip("networkx")
    nx = pytest.importorskip("networkx")
    critical = {row.building_id for row in profile.buildings if row.tier == "critical"}
    demand = {row.building_id: row.demand_weight for row in profile.buildings}
    ties = sorted(edge["id"] for edge in topology["edges"] if edge["kind"] == "tie")
    best = None
    for size in range(len(ties) + 1):
        for combo in itertools.combinations(ties, size):
            closed = [edge for edge in topology["edges"] if edge["id"] not in faults
                      and (not edge["normally_open"] or edge["id"] in combo)]
            graph = nx.Graph()
            graph.add_nodes_from(node["id"] for node in topology["nodes"])
            graph.add_edges_from((edge["from"], edge["to"]) for edge in closed)
            if graph.number_of_edges() != len(closed) or not nx.is_forest(graph):
                continue
            flow = nx.DiGraph()
            flow.add_edge("SUPER", "S", capacity=profile.source_capacity_w, weight=0)
            for edge in closed:
                flow.add_edge(edge["from"], edge["to"], capacity=edge["limit_w"], weight=0)
                flow.add_edge(edge["to"], edge["from"], capacity=edge["limit_w"], weight=0)
            for building, watts in demand.items():
                flow.add_edge(building, "SINK", capacity=watts, weight=-1000 if building in critical else -1)
            result = nx.max_flow_min_cost(flow, "SUPER", "SINK")
            served = {building: result[building]["SINK"] for building in demand}
            key = (-sum(served[b] for b in critical), -sum(served.values()), size, list(combo))
            best = min(best, key) if best else key
    return best


def objective_key(result):
    o = result["objective"]
    return (-o["critical_served_w"], -o["served_w"], o["switching_actions"], result["candidate_edge_ids"])


def two_tie_case():
    edges = [line("e1", "S", "J1"), line("e2", "J1", "L1"), line("e3", "S", "J2"), line("e4", "J2", "L2"),
             line("tie:a", "L2", "J1", kind="tie", normally_open=True),
             line("tie:b", "L1", "J2", kind="tie", normally_open=True),
             line("tie:c", "J1", "J2", kind="tie", normally_open=True)]
    return case({"L1": 800, "L2": 800}, edges, 1000, critical={"L1"})


def test_optimizer_beats_first_benefit_and_matches_independent_oracle():
    topology, profile, trace = two_tie_case()
    faults = {"e2", "e4"}
    heuristic, heuristic_loads = first_benefit(topology, profile, trace, faults)
    result = optimize(topology, profile, trace, 0, faults, frozenset(), None, passed)
    assert heuristic == {"tie:a"} and recovery.critical_served_w(profile, heuristic_loads) == 0
    assert result["candidate_edge_ids"] == ["tie:a", "tie:b"]
    assert result["objective"] == {"critical_served_w": 800, "served_w": 1000, "switching_actions": 2}
    assert result["solver_status"] == "OPTIMAL"
    assert objective_key(result) == oracle(topology, profile, trace, faults)
    assert {"edge_ids": ["tie:c"], "reason": "closing ['tie:c'] creates a loop; radial operation is required"} in result["refused_configs"]
    assert result["switching_sequence"] == [{"operation": "close", "edge_id": "tie:a"}, {"operation": "close", "edge_id": "tie:b"}]


@pytest.mark.parametrize("seed", range(40))
def test_random_small_graphs_match_the_exhaustive_oracle(seed):
    rng = random.Random(seed)
    count = rng.randint(3, 6)
    names = [f"L{i}" for i in range(count)]
    edges = []
    for index, name in enumerate(names):
        parent = "S" if index == 0 or rng.random() < .3 else names[rng.randrange(index)]
        edges.append(line(f"e{index}", parent, name, limit_w=rng.choice([300, 600, 1000, 5000])))
    for index in range(rng.randint(1, 3)):
        a, b = rng.sample(names, 2)
        edges.append(line(f"tie:{index}", a, b, limit_w=rng.choice([200, 500, 5000]), kind="tie", normally_open=True))
    loads = {name: rng.randint(50, 600) for name in names}
    critical = set(rng.sample(names, rng.randint(1, 2)))
    topology, profile, trace = case(loads, edges, rng.randint(400, 2500), critical)
    faults = set(rng.sample([f"e{i}" for i in range(count)], rng.randint(0, 2)))
    result = optimize(topology, profile, trace, 0, faults, frozenset(), None, passed)
    assert result["solver_status"] == "OPTIMAL"
    assert objective_key(result) == oracle(topology, profile, trace, faults)
    for state_edge, state in evaluate(topology, profile, trace, 0, faults, frozenset(result["candidate_edge_ids"]))[0].items():
        if state["faulted"]:
            assert state["flow_w"] == 0  # nothing is served across a known open edge


def test_ac_rejection_falls_back_and_never_claims_optimal():
    topology, profile, trace = two_tie_case()

    def reject_top(topology, params, served, states, capacity):
        both = states["tie:a"]["closed"] and states["tie:b"]["closed"]
        return {"status": "REJECTED" if both else "PASSED", "reason": "undervoltage" if both else "ok",
                "violations": [{"limit": "voltage", "component_id": "L2", "value": .91, "limit_value": .94, "unit": "pu"}] if both else []}
    result = optimize(topology, profile, trace, 0, {"e2", "e4"}, frozenset(), None, reject_top)
    assert result["evaluations"][0]["edge_ids"] == ["tie:a", "tie:b"] and result["evaluations"][0]["ac_status"] == "REJECTED"
    assert result["candidate_edge_ids"] == ["tie:b"]
    assert result["solver_status"] == "FEASIBLE"
    assert result["bound_objective"]["served_w"] > result["objective"]["served_w"]


def test_real_ac_engine_rejects_a_watt_feasible_long_tie():
    pytest.importorskip("power_grid_model")
    from app.district import electrical
    from pathlib import Path
    params = electrical.load_params(Path(electrical.__file__).with_name("data") / "gnitc_electrical.json")
    edges = [line("e1", "S", "J1", limit_w=60_000), line("e2", "J1", "L1", limit_w=60_000),
             line("e3", "S", "L2", limit_w=60_000),
             {**line("tie:long", "L2", "L1", limit_w=60_000, kind="tie", normally_open=True), "length_m": 1500.0}]
    topology, profile, trace = case({"L1": 30_000, "L2": 1_000}, edges, 50_000, critical={"L1"})
    result = optimize(topology, profile, trace, 0, {"e2"}, frozenset(), params, electrical.check)
    top = result["evaluations"][0]
    assert top["edge_ids"] == ["tie:long"] and top["objective"]["critical_served_w"] == 30_000
    assert top["ac_status"] == "REJECTED" and any(v["limit"] == "voltage" for v in top["violations"])
    assert result["candidate_edge_ids"] == [] and result["solver_status"] == "FEASIBLE"


def test_engine_absence_and_truncation_are_explicit(monkeypatch):
    topology, profile, trace = two_tie_case()
    unavailable = optimize(topology, profile, trace, 0, {"e2", "e4"}, frozenset(), None,
                           lambda *a: {"status": "UNAVAILABLE", "reason": "absent", "violations": []})
    assert unavailable["solver_status"] == "UNVALIDATED" and unavailable["candidate_edge_ids"] is None
    monkeypatch.setattr(recovery, "MAX_CONFIGS", 2)
    truncated = optimize(topology, profile, trace, 0, {"e2", "e4"}, frozenset(), None, passed)
    assert truncated["truncated"] and truncated["solver_status"] == "FEASIBLE"


def test_incompatible_voltage_and_faulted_ties_are_never_permitted():
    topology, profile, trace = two_tie_case()
    topology["edges"][4]["voltage_v"] = 11000
    assert "incompatible voltages" in config_problem(topology, set(), frozenset({"tie:a"}))
    assert "known open" in config_problem(topology, {"tie:b"}, frozenset({"tie:b"}))


# --- authority: proposals, staleness and the restoration evidence gate ---

def act(name, component_id=None, fault_kind=None, observation=None):
    return DistrictAction(action_id=str(uuid.uuid4()), run_id="t", expected_revision=1, action=name, component_id=component_id,
                          fault_kind=fault_kind, observation=observation)


def observe(district, healthy=True, seconds=0.0, sequence=None):
    at = district.now + timedelta(seconds=seconds)
    sequence = sequence or (district.last_observation[0] + 1 if district.last_observation else 1)
    return district.apply_action(act(DistrictActionName.record_observation, observation=DistrictObservation(
        sequence=sequence, observed_at=at.isoformat(), healthy=healthy, source="SIMULATED_OBSERVATION_ADAPTER")))


def gnitc_outage():
    district = DistrictAuthority()
    district.now = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
    district.clock = lambda: district.now
    district.hour = 20
    tie = next(edge for edge in district.topology["edges"] if edge["kind"] == "tie")
    for edge in district.topology["edges"]:
        if edge["kind"] == "tie":
            continue
        trial = DistrictAuthority()
        trial.hour, trial.faults = 20, {edge["id"]}
        _, base = trial._electrical_state()
        _, closed = trial._electrical_state(frozenset({tie["id"]}))
        if sum(l["served_w"] for l in closed) > sum(l["served_w"] for l in base) and not config_problem(trial.topology, trial.faults, frozenset({tie["id"]})):
            assert district.apply_action(act(DistrictActionName.inject_fault, edge["id"], "line_open"))
            return district, tie["id"], edge["id"]
    raise AssertionError("no beneficial GNITC outage")


def test_restoration_requires_distinct_fresh_samples_over_the_dwell():
    pytest.importorskip("power_grid_model")
    district, tie, _ = gnitc_outage()
    assert district.apply_action(act(DistrictActionName.propose_recovery))
    assert district.proposal["candidate_edge_ids"] == [tie] and district.proposal["ac"]["status"] == "PASSED"
    assert not district.apply_action(act(DistrictActionName.apply_recovery))
    assert observe(district)
    assert not observe(district, sequence=1)                      # duplicate never counts twice
    assert not observe(district, seconds=-1, sequence=5)          # reordered timestamp
    assert not observe(district, seconds=-60)                     # stale sample
    district.now += timedelta(seconds=2)
    assert observe(district)
    assert not district._evidence_ready()                         # two samples, 2 s apart < 5 s dwell
    assert not district.apply_action(act(DistrictActionName.apply_recovery))
    district.now += timedelta(seconds=4)
    assert observe(district, healthy=False)                       # unhealthy resets the gate
    assert district.evidence == []
    for _ in range(2):
        district.now += timedelta(seconds=6)
        assert observe(district)
    district.now += timedelta(seconds=31)
    assert not district._evidence_ready()                         # newest sample went stale
    district.now -= timedelta(seconds=31)
    assert district.apply_action(act(DistrictActionName.apply_recovery))
    restoration = district.snapshot()["state"]["restoration"]
    assert restoration["applied_edge_ids"] == [tie] and restoration["physical_confirmation"] is None


def test_hour_steps_never_satisfy_the_gate_and_make_proposals_stale():
    pytest.importorskip("power_grid_model")
    district, _, _ = gnitc_outage()
    assert district.apply_action(act(DistrictActionName.propose_recovery))
    for _ in range(3):
        assert district.apply_action(act(DistrictActionName.advance_hour))
    assert district.evidence == []
    for _ in range(2):
        district.now += timedelta(seconds=6)
        assert observe(district)
    assert not district.apply_action(act(DistrictActionName.apply_recovery))
    assert "stale" in district.snapshot()["state"]["restoration"]["reason"]


def test_missing_engine_blocks_validated_application(monkeypatch):
    from app.district import electrical
    monkeypatch.setattr(electrical, "version", lambda name: (_ for _ in ()).throw(electrical.PackageNotFoundError(name)))
    district, _, _ = gnitc_outage()
    assert district.apply_action(act(DistrictActionName.propose_recovery))
    assert district.proposal["solver_status"] == "UNVALIDATED" and district.proposal["candidate_edge_ids"] is None
    assert "not installed" in district.snapshot()["state"]["restoration"]["reason"]
    assert not district.apply_action(act(DistrictActionName.apply_recovery))


def test_hidden_transformer_scenarios_do_not_change_the_plan():
    district, _, _ = gnitc_outage()
    assert district.apply_action(act(DistrictActionName.propose_recovery))
    before = {key: district.proposal[key] for key in ("candidate_edge_ids", "objective", "solver_status", "digest")}
    for transformer in (n["id"] for n in district.topology["nodes"] if n["role"] == "transformer"):
        assert district.apply_action(act(DistrictActionName.transformer_scenario, transformer, "overload"))
    assert district.apply_action(act(DistrictActionName.propose_recovery))
    assert {key: district.proposal[key] for key in before} == before


def test_weak_tie_rehearsal_is_watt_feasible_but_refused_by_the_ac_check():
    pytest.importorskip("power_grid_model")
    district, tie, _ = gnitc_outage()
    assert district.apply_action(act(DistrictActionName.weak_tie_rehearsal, tie, "weak"))
    assert district.apply_action(act(DistrictActionName.propose_recovery))
    top = district.proposal["evaluations"][0]
    assert top["edge_ids"] == [tie] and top["ac_status"] == "REJECTED"
    assert any(v["limit"] == "line_loading" and v["component_id"] == tie for v in top["violations"])
    assert not district.proposal["candidate_edge_ids"]
    assert district.apply_action(act(DistrictActionName.weak_tie_rehearsal, tie, "clear"))
    assert district.apply_action(act(DistrictActionName.propose_recovery))
    assert district.proposal["candidate_edge_ids"] == [tie]
