"""Bounded synthetic SHIFT-schema fixtures; no SHIFT runtime or physical wiring inference."""
from __future__ import annotations

import copy
from types import SimpleNamespace
from enum import StrEnum

from app.district.authority import DistrictAuthority


def act(district, name, component_id=None):
    # Exercise the authority without importing FastAPI or creating another state owner.
    return district.apply_action(SimpleNamespace(action=StrEnum("Action", {name: name})(name),
        component_id=component_id, fault_kind="line_open" if "fault" in name else None))


def radial_fixture(shape="star", source_capacity_w=6000, tie_limit_w=6000):
    district = DistrictAuthority()
    district.hour = 0
    district.source_capacity_w = source_capacity_w
    topology = copy.deepcopy(district.topology)
    topology.update(engine="SYNTHETIC_SHIFT_SCHEMA_FIXTURE", secondary_strategy="RadialStrategy",
                    provenance="GENERATED_OFFLINE_TEST_GRAPH; not executed SHIFT or campus wiring",
                    equipment_stage="Declared integer-watt test ratings only", cluster_count=3,
                    group_members={})
    ids = ["S", "J", "A", "B", "C"] + [f"L{i}" for i in range(6)]
    topology["nodes"] = [{"id": node, "role": "source" if node == "S" else
                         "load" if node.startswith("L") else "junction",
                         "building_id": node if node.startswith("L") else None,
                         "lon": 78.66, "lat": 17.16} for node in ids]
    pairs = [("trunk", "S", "J"), ("a", "J", "A"),
             ("b", "A" if shape == "chain" else "J", "B"),
             ("c", "B" if shape == "chain" else "J", "C")]
    pairs += [(f"load-{i}", "ABC"[i // 2], f"L{i}") for i in range(6)]
    topology["edges"] = [{"id": name, "from": left, "to": right, "kind": "line",
                          "normally_open": False, "limit_w": 6000} for name, left, right in pairs]
    topology["edges"] += [{"id": name, "from": left, "to": right, "kind": "tie",
                           "normally_open": True, "limit_w": tie_limit_w}
                          for name, left, right in [("tie-ab", "A", "B"), ("tie-bc", "B", "C")]]
    district.topology = topology
    for row in district.energy_trace["profile"]:
        row.update(demand_w=6000, grid_import_w=6000)
    return district


def assert_safe(district):
    """Independent closed-graph connectivity/radiality and flow conservation oracle."""
    states, loads = district._electrical_state()
    nodes = {node["id"]: node for node in district.topology["nodes"]}
    adjacency = {node: [] for node in nodes}
    for edge in district.topology["edges"]:
        state = states[edge["id"]]
        assert 0 <= state["flow_w"] <= edge["limit_w"]
        if state["faulted"] or not state["closed"]:
            assert state["flow_w"] == 0 and not state["energized"]
        else:
            adjacency[edge["from"]].append((edge["to"], edge["id"]))
            adjacency[edge["to"]].append((edge["from"], edge["id"]))
    visited = set()
    for start in nodes:
        if start in visited:
            continue
        stack = [(start, None)]
        while stack:
            node, incoming = stack.pop()
            assert node not in visited, "closed graph contains a loop"
            visited.add(node)
            stack.extend((other, edge) for other, edge in adjacency[node] if edge != incoming)
    source = next(node for node in nodes if nodes[node]["role"] == "source")
    paths, queue = {source: []}, [source]
    for node in queue:
        for other, edge in adjacency[node]:
            if other not in paths:
                paths[other] = paths[node] + [edge]
                queue.append(other)
    expected_flows = {edge: 0 for edge in states}
    by_building = {node.get("building_id", node["id"]): node["id"]
                   for node in nodes.values() if node["role"] == "load"}
    for load in loads:
        node = by_building[load["building_id"]]
        assert 0 <= load["grid_served_w"] <= load["grid_requested_w"]
        assert load["requested_w"] == load["served_w"] + load["unmet_w"]
        if node not in paths:
            assert load["grid_served_w"] == 0
        for edge in paths.get(node, []):
            expected_flows[edge] += load["grid_served_w"]
    assert sum(load["grid_served_w"] for load in loads) <= district.source_capacity_w
    assert {edge: state["flow_w"] for edge, state in states.items()} == expected_flows
