import pytest

from app.core.appliances import APPLIANCES
from app.district.appliances import dispatch, validate_mapping
from app.district.authority import DATA, DistrictAuthority
from app.district.profile import load_profile


def mapped_dispatch(district, profile):
    edges = {edge["id"]: edge for edge in district.topology["edges"]}
    adjacency = {}
    for edge in edges.values():
        if not edge["normally_open"] and edge["id"] not in district.faults:
            adjacency.setdefault(edge["from"], []).append((edge["to"], edge["id"]))
            adjacency.setdefault(edge["to"], []).append((edge["from"], edge["id"]))
    parent, parent_edge, pending = {"source": None}, {}, ["source"]
    for node in pending:
        for neighbor, edge_id in adjacency.get(node, []):
            if neighbor not in parent:
                parent[neighbor], parent_edge[neighbor] = node, edge_id
                pending.append(neighbor)
    return dispatch(profile, district.topology, parent, parent_edge, "source")


def test_integrated_dispatch_conserves_leaf_building_edge_and_source_totals():
    district = DistrictAuthority()
    profile = load_profile(DATA / "gnitc_appliance_profile.json", district.topology)
    for capacity in (14000, 6000, 0):
        limited = profile.model_copy(update={"source_capacity_w": capacity})
        flows, loads, decision = mapped_dispatch(district, limited)
        leaves = [leaf for load in loads for leaf in load["appliances"]]
        assert len(leaves) == len(APPLIANCES) == 31
        assert sum(load["requested_w"] for load in loads) == sum(leaf["requested_w"] for leaf in leaves) == 14000
        served = sum(leaf["served_w"] for leaf in leaves)
        assert served <= capacity
        assert served == sum(load["served_w"] for load in loads)
        for edge in district.topology["edges"]:
            assert flows[edge["id"]] == sum(leaf["served_w"] for leaf in leaves if edge["id"] in leaf["path_edge_ids"])
            assert flows[edge["id"]] <= edge["limit_w"]
        assert decision["status"] == "OPTIMAL" and decision["validation"] == "PASSED"
        assert decision["physical_confirmation"] is None


def test_open_graph_path_sheds_mapped_appliances_without_local_island_supply():
    district = DistrictAuthority()
    profile = load_profile(DATA / "gnitc_appliance_profile.json", district.topology)
    district.faults.update(edge["id"] for edge in district.topology["edges"] if edge["from"] == "source" or edge["to"] == "source")
    flows, loads, _ = mapped_dispatch(district, profile)
    assert not any(flows.values())
    assert sum(load["requested_w"] for load in loads) == 14000
    assert all(load["served_w"] == load["local_supply_w"] == 0 for load in loads)


def test_mapping_rejects_missing_rooms_and_overrated_requests():
    district = DistrictAuthority()
    profile = load_profile(DATA / "gnitc_appliance_profile.json", district.topology)
    with pytest.raises(ValueError, match="every configured appliance room"):
        validate_mapping(profile.model_copy(update={"buildings": profile.buildings[1:]}))
    requests = dict(profile.appliance_requests_w)
    requests[APPLIANCES[0].id] += 1
    with pytest.raises(ValueError, match="rated maximum"):
        validate_mapping(profile.model_copy(update={"appliance_requests_w": requests}))
