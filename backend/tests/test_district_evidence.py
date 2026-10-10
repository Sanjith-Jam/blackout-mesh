from app.district.authority import DistrictAuthority, diagnose_transformer


def test_transformer_diagnosis_uses_only_observations_and_abstains_on_missing_or_stale():
    observation = {"oil_temperature_c": 105.0, "voltage_v": 380.0, "current_a": 60.0,
                   "cooling_ok": False, "status": "SIMULATED"}
    assert diagnose_transformer({**observation, "scenario": "overload"}) == diagnose_transformer(
        {**observation, "scenario": "cooling_failure"})
    assert diagnose_transformer(observation)["suspected_part"] == "cooling_system"
    for status in ("MISSING", "STALE"):
        stale = {**observation, "status": status}
        assert diagnose_transformer(stale)["status"] == "UNKNOWN"
    assert diagnose_transformer({**observation, "oil_temperature_c": None})["status"] == "UNKNOWN"


def test_energy_exposes_period_totals_and_one_hour_network_energy_without_claiming_import_delivery():
    district = DistrictAuthority()
    district.hour = 12
    snapshot = district.snapshot()
    energy, loads = snapshot["energy"], snapshot["state"]["loads"]
    totals, interval = energy["totals"], energy["network_interval"]
    assert totals["period_hours"] == 24
    assert totals["demand_wh"] == sum(row["demand_w"] for row in energy["profile"])
    assert totals["dispatch_import_scheduled_wh"] == sum(row["grid_import_w"] for row in energy["profile"])
    assert totals["grid_export_wh"] == 0
    assert totals["battery_loss_wh"] == district.energy_trace["totals"]["battery_loss_wh"]
    assert interval["duration_hours"] == 1
    assert interval["grid_import_requested_wh"] == sum(load["grid_requested_w"] for load in loads)
    assert interval["grid_served_wh"] == sum(load["grid_served_w"] for load in loads)
    assert interval["served_wh"] + interval["unmet_wh"] == interval["requested_wh"]
    assert interval["unmet_fraction_of_requested"] == interval["unmet_wh"] / interval["requested_wh"]


def test_open_feeder_blocks_grid_following_pv_and_storage():
    district = DistrictAuthority()
    district.hour = 12
    topology = district.topology
    source = next(node["id"] for node in topology["nodes"] if node["role"] == "source")
    candidate = None
    for edge in topology["edges"]:
        if edge["kind"] == "tie":
            continue
        trial = DistrictAuthority()
        trial.hour = 12
        trial.faults.add(edge["id"])
        state = trial.snapshot()["state"]
        load_nodes = {node.get("building_id", node["id"]): node["id"]
                      for node in trial.topology["nodes"] if node["role"] == "load"}
        adjacency = {}
        for item, item_state in zip(trial.topology["edges"], state["edges"]):
            if item_state["closed"] and not item_state["faulted"]:
                adjacency.setdefault(item["from"], set()).add(item["to"])
                adjacency.setdefault(item["to"], set()).add(item["from"])
        reachable, pending = {source}, [source]
        while pending:
            for neighbor in adjacency.get(pending.pop(), ()):
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    pending.append(neighbor)
        islanded = [load for load in state["loads"] if load_nodes[load["building_id"]] not in reachable]
        if islanded:
            candidate = edge["id"], state, islanded
            break
    assert candidate
    fault_id, state, islanded = candidate
    assert next(edge for edge in state["edges"] if edge["id"] == fault_id)["flow_w"] == 0
    assert all(load["grid_served_w"] == 0 for load in islanded)
    assert all(load["served_w"] == load["local_supply_w"] for load in islanded)
    assert all(load["served_w"] == load["local_supply_w"] == 0 for load in islanded)
    assert all(load["local_supply_semantics"] == "CONFIGURED_GRID_FOLLOWING_REQUIRES_SOURCE_REACHABILITY"
               and load["local_supply_basis"] == "CITYLEARN_DISTRICT_ENERGY_BALANCE_RESIDUAL_ALLOCATED_PER_BUILDING"
               and load["local_supply_provenance"] == "MODEL_DERIVED"
               for load in islanded)
