"""Pure district evaluation: no candidate is scored by mutating live switch state."""
from __future__ import annotations

import copy

from app.district.appliances import dispatch
from app.district.profile import apportion

_DISPATCH_CACHE: dict = {}


def edge_states(topology, faults, closed_ties):
    return {edge["id"]: {"id": edge["id"], "closed": not edge["normally_open"] or edge["id"] in closed_ties,
                         "faulted": edge["id"] in faults, "energized": False, "flow_w": 0}
            for edge in topology["edges"]}


def source_tree(topology, states):
    """BFS from the first source over closed, unfaulted edges; returns (source, parent, parent_edge)."""
    adjacency = {}
    for edge in topology["edges"]:
        state = states[edge["id"]]
        if state["closed"] and not state["faulted"]:
            adjacency.setdefault(edge["from"], []).append((edge["to"], edge["id"]))
            adjacency.setdefault(edge["to"], []).append((edge["from"], edge["id"]))
    sources = sorted(node["id"] for node in topology["nodes"] if node["role"] == "source")
    source = sources[0] if sources else None
    parent, parent_edge = ({source: None}, {}) if source else ({}, {})
    queue = [source] if source else []
    for current in queue:
        for neighbor, edge_id in sorted(adjacency.get(current, [])):
            if neighbor not in parent:
                parent[neighbor], parent_edge[neighbor] = current, edge_id
                queue.append(neighbor)
    return source, parent, parent_edge


def evaluate(topology, profile, energy_trace, hour, faults, closed_ties, *, source_budget_w=None):
    """Return (edge states, building loads) for one declared switch configuration."""
    budget_w = profile.source_capacity_w - profile.loss_reserve_w if source_budget_w is None else source_budget_w
    edge_by_id = {edge["id"]: edge for edge in topology["edges"]}
    states = edge_states(topology, faults, closed_ties)
    source, parent, parent_edge = source_tree(topology, states)

    def mark(flows):
        for edge in topology["edges"]:
            state = states[edge["id"]]
            state.update(flow_w=flows[edge["id"]], provenance="MODEL_DERIVED",
                         energized=edge["from"] in parent and edge["to"] in parent and state["closed"] and not state["faulted"])

    if profile.demand_basis == "appliance_inventory":
        key = (profile.config_hash, budget_w, tuple(sorted(parent_edge.items())),
               tuple((edge["id"], edge["limit_w"]) for edge in topology["edges"]))
        if key not in _DISPATCH_CACHE:
            if len(_DISPATCH_CACHE) > 256:  # ponytail: clear-all bound, LRU if configs grow
                _DISPATCH_CACHE.clear()
            _DISPATCH_CACHE[key] = dispatch(profile, topology, parent, parent_edge, source, budget_w)
        flows, loads, decision = copy.deepcopy(_DISPATCH_CACHE[key])
        mark(flows)
        return states, loads, decision

    # Divisible aggregate loads: critical-first greedy maximizes served critical W, then total W,
    # because single-source tree capacity constraints form a polymatroid.
    loads = []
    flows = {edge_id: 0 for edge_id in states}
    grid_served_total = 0
    policies = {row.building_id: row for row in profile.buildings}
    requested = sorted((node for node in topology["nodes"] if node["role"] == "load"),
                       key=lambda node: (policies[node.get("building_id", node["id"])].tier != "critical", node["id"]))
    row = energy_trace["profile"][hour]
    demands = apportion(row["demand_w"], {key: item.demand_weight for key, item in policies.items()})
    imports = apportion(row["grid_import_w"], demands)
    for node in requested:
        path, cursor = [], node["id"]
        while cursor in parent_edge:
            path.append(parent_edge[cursor])
            cursor = parent[cursor]
        connected = bool(source) and cursor == source
        policy = policies[node.get("building_id", node["id"])]
        requested_w = demands[policy.building_id]
        grid_requested_w = imports[policy.building_id]
        # Configured grid-following PV/storage cannot energize an isolated building.
        local_supply_w = requested_w - grid_requested_w if connected else 0
        path_capacity = min((edge_by_id[edge_id]["limit_w"] - flows[edge_id] for edge_id in path), default=budget_w)
        grid_served_w = min(grid_requested_w, budget_w - grid_served_total, max(0, path_capacity)) if connected else 0
        if grid_served_w:
            grid_served_total += grid_served_w
            for edge_id in path:
                flows[edge_id] += grid_served_w
        served_w = local_supply_w + grid_served_w
        loads.append({"building_id": node.get("building_id", node["id"]), "tier": policy.tier,
                      "requested_w": requested_w, "local_supply_w": local_supply_w,
                      "grid_requested_w": grid_requested_w, "grid_served_w": grid_served_w,
                      "served_w": served_w, "unmet_w": requested_w - served_w,
                      "demand_provenance": energy_trace["provenance"],
                      "tier_provenance": "CONFIGURED_SIMULATED_ASSUMPTION",
                      "tier_rationale": policy.rationale,
                      "local_supply_provenance": "MODEL_DERIVED",
                      "local_supply_basis": "CITYLEARN_DISTRICT_ENERGY_BALANCE_RESIDUAL_ALLOCATED_PER_BUILDING",
                      "local_supply_semantics": "CONFIGURED_GRID_FOLLOWING_REQUIRES_SOURCE_REACHABILITY",
                      "grid_service_provenance": "MODEL_DERIVED", "unmet_provenance": "MODEL_DERIVED", "appliances": []})
    mark(flows)
    return states, loads, {"solver": "integer weighted dispatch", "status": "MODEL_DERIVED",
                           "validation": "WATT_BUDGET_ONLY", "physical_confirmation": None}
