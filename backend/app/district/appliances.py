"""Bounded campus mapping onto the district graph using the existing solver and validator."""
from app.core.appliance_allocator import Item, Problem, solve, validate
from app.core.appliances import APPLIANCES, CLASS_ORDER, UNKNOWN


def validate_mapping(profile):
    rooms = {row.room_id for row in profile.buildings if row.room_id is not None}
    if rooms != {item.room_id for item in APPLIANCES}:
        raise ValueError("integrated profile must map every configured appliance room exactly once")
    if set(profile.appliance_requests_w) != {item.id for item in APPLIANCES}:
        raise ValueError("integrated profile must explicitly request every configured appliance")
    for item in APPLIANCES:
        requested = profile.appliance_requests_w[item.id]
        if not 0 <= requested <= item.demand_w:
            raise ValueError(f"{item.id}: requested W exceeds the configured rated maximum")


def dispatch(profile, topology, parent, parent_edge, source, budget_w=None):
    budget_w = profile.source_capacity_w if budget_w is None else budget_w
    validate_mapping(profile)
    nodes = {node.get("building_id", node["id"]): node for node in topology["nodes"] if node["role"] == "load"}
    by_room = {row.room_id: row.building_id for row in profile.buildings if row.room_id is not None}
    paths, reachable = {}, {}
    for building_id, node in nodes.items():
        path, cursor = [], node["id"]
        while cursor in parent_edge:
            path.append(parent_edge[cursor])
            cursor = parent[cursor]
        paths[building_id], reachable[building_id] = tuple(path), cursor == source
    # Graph-edge paths replace the original A/B feeder budgets at this adapter only.
    items = tuple(Item(item.id, profile.appliance_requests_w[item.id], "district", item.room_id,
                       item.static_class() or UNKNOWN, requested=profile.appliance_requests_w[item.id] > 0,
                       reachable=reachable[by_room[item.room_id]], path=paths[by_room[item.room_id]],
                       group=item.indivisible_group, requires=item.requires) for item in APPLIANCES)
    limits = {edge["id"]: edge["limit_w"] for edge in topology["edges"]}
    problem = Problem(items, budget_w, {"district": budget_w},
                      {"district": True}, class_order=CLASS_ORDER["activity_first"], edge_limits_w=limits)
    plan = solve(problem)
    violations = validate(problem, plan.served)
    if violations:
        raise ValueError(f"district appliance dispatch failed independent validation: {violations}")
    flows = {key: sum(item.watts for item in items if item.id in plan.served and key in item.path) for key in limits}
    loads = []
    for policy in profile.buildings:
        leaves = [item for item in APPLIANCES if item.room_id == policy.room_id]
        appliances = [{"id": item.id, "service_id": item.service_id, "room_id": item.room_id,
                       "rated_max_w": item.demand_w, "requested_w": profile.appliance_requests_w[item.id],
                       "served_w": profile.appliance_requests_w[item.id] if item.id in plan.served else 0,
                       "priority_class": item.static_class() or UNKNOWN,
                       "reachable": reachable[policy.building_id], "path_edge_ids": list(paths[policy.building_id])}
                      for item in leaves]
        requested = sum(item["requested_w"] for item in appliances)
        served = sum(item["served_w"] for item in appliances)
        loads.append({"building_id": policy.building_id, "tier": policy.tier,
                      "requested_w": requested, "local_supply_w": 0, "grid_requested_w": requested,
                      "grid_served_w": served, "served_w": served, "unmet_w": requested - served,
                      "demand_provenance": profile.provenance, "tier_provenance": profile.provenance,
                      "tier_rationale": policy.rationale, "local_supply_provenance": profile.provenance,
                      "local_supply_basis": "NO_DER_PLACEMENT_CONFIGURED", "local_supply_semantics": "DISABLED",
                      "grid_service_provenance": "MODEL_DERIVED", "unmet_provenance": "MODEL_DERIVED",
                      "appliances": appliances})
    return flows, loads, {"solver": plan.solver, "status": plan.status,
                           "validation": "PASSED", "physical_confirmation": None}


def inventory_energy(profile):
    """Inventory requests are their own profile; the cached CityLearn trace is never rescaled."""
    demand = sum(profile.appliance_requests_w.values())
    return {"engine": "Configured appliance inventory; no PV or storage placement", "provenance": profile.provenance,
            "battery": {"round_trip_efficiency": 1.0},
            "profile": [{"hour": hour, "demand_w": demand, "pv_w": 0, "baseline_grid_w": demand,
                "dispatch_grid_w": demand, "battery_soc_wh": 0, "pv_used_w": 0, "battery_charge_w": 0,
                "battery_discharge_w": 0, "grid_import_w": demand, "loss_wh": 0} for hour in range(24)],
            "totals": {"demand_wh": 24*demand, "baseline_import_wh": 24*demand,
                       "dispatch_import_wh": 24*demand, "battery_loss_wh": 0, "pv_curtailed_wh": 0}}
