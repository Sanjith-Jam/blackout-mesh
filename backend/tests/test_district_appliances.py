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


def test_opt_in_profile_uses_one_revision_and_validates_the_full_api_contract(monkeypatch):
    from app.api.district import DistrictSnapshot
    from app.district import authority

    monkeypatch.setenv("DISTRICT_PROFILE", str(DATA / "gnitc_appliance_profile.json"))
    district = DistrictAuthority()
    first = DistrictSnapshot.model_validate(district.snapshot())
    assert first.profile.appliance_count == 31
    assert first.profile.id == "gnitc-appliance-14kw-v1"
    assert first.identity.profile_hash == first.profile.config_hash
    assert first.profile.catalog_version and first.profile.catalog_hash
    assert first.state.grid_requested_w == first.state.grid_served_w == 14000
    assert first.energy.grid_import_w == 14000 and first.energy.pv_used_w == 0
    assert first.profile.decision.validation == "PASSED"
    assert first.profile.decision.physical_confirmation is None
    monkeypatch.setattr(authority, "dispatch", lambda *args: pytest.fail("unchanged snapshot ran a second allocation"))
    second = DistrictSnapshot.model_validate(district.snapshot())
    assert second.identity == first.identity
    assert second.state.loads == first.state.loads


def test_district_api_dispatch_runs_outside_publication_event_loop(monkeypatch):
    import asyncio
    from fastapi.testclient import TestClient
    from app.district import authority
    from app.main import create_app

    monkeypatch.setenv("DISTRICT_PROFILE", str(DATA / "gnitc_appliance_profile.json"))
    original = authority.dispatch
    calls = []

    def checked(*args):
        with pytest.raises(RuntimeError, match="no running event loop"):
            asyncio.get_running_loop()
        calls.append(True)
        return original(*args)

    monkeypatch.setattr(authority, "dispatch", checked)
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/district")
        assert response.status_code == 200
        assert response.json()["profile"]["appliance_count"] == 31
        assert calls
