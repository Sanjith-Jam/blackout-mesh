import asyncio
import pytest
import copy
import json
from app.api.district import DistrictAction, DistrictActionName
from app.api import district as district_api
from app.district.authority import DistrictAuthority
from app.district import authority as authority_module
from fastapi.testclient import TestClient
from pathlib import Path


def action(name, component_id=None, fault_kind=None):
    return DistrictAction(run_id="test", expected_revision=1, action=name,
                          component_id=component_id, fault_kind=fault_kind)


def test_snapshot_uses_citylearn_trace_and_keeps_missing_transformer_evidence_unknown():
    district = DistrictAuthority()
    snapshot = district.snapshot()

    assert snapshot["site"]["radius_m"] == 500
    assert snapshot["map"]["radius_m"] == 3000
    assert snapshot["map"]["license"] == "ODbL-1.0"
    assert snapshot["map"]["source_sha256"]
    assert len(snapshot["energy"]["profile"]) == 24
    assert snapshot["energy"]["provenance"] == "CITYLEARN_EXECUTED_ON_SYNTHETIC_DEMO_INPUTS"
    assert snapshot["energy"]["battery_soc_wh"] == snapshot["energy"]["profile"][12]["battery_soc_wh"]
    assert any(row["battery_charge_w"] for row in snapshot["energy"]["profile"])
    assert all(item["diagnosis"]["status"] == "UNKNOWN" for item in snapshot["state"]["transformers"])
    assert all(item["sensor"]["oil_temperature_c"] is None for item in snapshot["state"]["transformers"])


def test_citylearn_demand_and_grid_import_balance_into_graph_load_state():
    district = DistrictAuthority()
    district.hour = 0
    normal = district.snapshot()
    profile = normal["energy"]["profile"][0]
    loads = normal["state"]["loads"]
    assert {load["tier_provenance"] for load in loads} == {"CONFIGURED_SIMULATED_ASSUMPTION"}
    assert all("does not represent verified building criticality" in load["tier_rationale"] for load in loads)
    assert sum(load["requested_w"] for load in loads) == profile["demand_w"]
    assert sum(load["grid_requested_w"] for load in loads) == profile["grid_import_w"]
    assert sum(load["local_supply_w"] for load in loads) == profile["demand_w"] - profile["grid_import_w"]
    assert sum(load["grid_served_w"] for load in loads) == profile["grid_import_w"]
    for load in loads:
        assert load["requested_w"] == load["local_supply_w"] + load["grid_requested_w"]
        assert load["served_w"] == load["local_supply_w"] + load["grid_served_w"]
        assert load["unmet_w"] == load["requested_w"] - load["served_w"] >= 0
        assert load["served_w"] <= load["requested_w"]

    district.hour = 20
    peak = district.snapshot()
    assert peak["energy"]["grid_import_w"] == peak["state"]["grid_requested_w"] == 6200
    # The declared 20 W loss reserve keeps AC losses inside the 6,000 W source budget.
    assert peak["state"]["grid_served_w"] == 6000 - district.profile.loss_reserve_w == 5980
    assert peak["state"]["unmet_w"] == 220
    assert sum(load["requested_w"] for load in peak["state"]["loads"]) == sum(
        load["served_w"] for load in peak["state"]["loads"]) + peak["state"]["unmet_w"]
    assert all(edge["flow_w"] <= peak["state"]["grid_served_w"] for edge in peak["state"]["edges"])

    district.hour = 0
    load_nodes = {node.get("building_id"): node for node in district.topology["nodes"] if node["role"] == "load"}
    critical_building = next(load["building_id"] for load in loads if load["tier"] == "critical")
    critical_node = load_nodes[critical_building]["id"]
    feeder_edge = next(edge for edge in district.topology["edges"]
                       if edge["kind"] != "tie" and critical_node in (edge["from"], edge["to"]))
    assert district.apply_action(action(DistrictActionName.inject_fault, feeder_edge["id"], "line_open"))
    faulted = district.snapshot()["state"]
    assert sum(load["grid_served_w"] for load in faulted["loads"]) < profile["grid_import_w"]
    assert faulted["critical_shortfall_w"] == sum(load["unmet_w"] for load in faulted["loads"] if load["tier"] == "critical")
    assert all(edge["flow_w"] <= next(item["limit_w"] for item in district.topology["edges"] if item["id"] == edge["id"])
               for edge in faulted["edges"])


def healthy_evidence(district):
    """Two distinct sequenced healthy samples six seconds apart (simulated adapter)."""
    from datetime import datetime, timedelta, timezone
    from app.api.district import DistrictObservation
    sequence, last = district.last_observation or (0, None)
    start = last + timedelta(seconds=1) if last else datetime.now(timezone.utc)
    for index in range(2):
        at = start + timedelta(seconds=6 * index)
        district.clock = lambda at=at: at
        assert district.apply_action(DistrictAction(run_id="test", expected_revision=1, action="record_observation",
            observation=DistrictObservation(sequence=sequence + index + 1, observed_at=at.isoformat(),
                                            healthy=True, source="SIMULATED_OBSERVATION_ADAPTER")))


def test_fault_disconnects_edges_and_recovery_waits_for_stable_evidence():
    pytest.importorskip("power_grid_model")
    district = DistrictAuthority()
    district.hour = 0
    tie = next(edge for edge in district.topology["edges"] if edge["kind"] == "tie")
    adjacency = {}
    for edge in district.topology["edges"]:
        if edge["kind"] == "tie":
            continue
        adjacency.setdefault(edge["from"], []).append((edge["to"], edge["id"]))
        adjacency.setdefault(edge["to"], []).append((edge["from"], edge["id"]))
    queue = [(tie["from"], [])]
    seen = set()
    path = None
    while queue:
        node, edges = queue.pop(0)
        if node == tie["to"]:
            path = edges
            break
        if node in seen:
            continue
        seen.add(node)
        queue.extend((neighbor, edges + [edge_id]) for neighbor, edge_id in adjacency.get(node, []))
    assert path

    fault_id = None
    for edge_id in path:
        trial = DistrictAuthority()
        trial.hour = 0
        trial.apply_action(action(DistrictActionName.inject_fault, edge_id, "line_open"))
        trial.apply_action(action(DistrictActionName.propose_recovery))
        if trial.snapshot()["state"]["restoration"]["candidate_edge_id"]:
            fault_id = edge_id
            break
    assert fault_id
    assert district.apply_action(action(DistrictActionName.inject_fault, fault_id, "line_open"))
    broken = district.snapshot()
    assert next(edge for edge in broken["state"]["edges"] if edge["id"] == fault_id)["energized"] is False
    assert district.apply_action(action(DistrictActionName.propose_recovery))
    assert not district.apply_action(action(DistrictActionName.apply_recovery))
    healthy_evidence(district)
    assert district.apply_action(action(DistrictActionName.apply_recovery))
    restored = district.snapshot()
    assert restored["state"]["restoration"]["applied_edge_id"] == tie["id"]
    assert all(load["served_w"] <= load["requested_w"] for load in restored["state"]["loads"])
    assert not district.apply_action(action(DistrictActionName.clear_fault, fault_id, "line_open"))
    healthy_evidence(district)
    assert district.apply_action(action(DistrictActionName.clear_fault, fault_id, "line_open"))
    assert district.snapshot()["state"]["faults"] == []


def test_transformer_scenario_is_labeled_simulated_and_clear_returns_unknown():
    district = DistrictAuthority()
    transformer_id = district.snapshot()["state"]["transformers"][0]["component_id"]
    assert district.apply_action(action(DistrictActionName.transformer_scenario, transformer_id, "cooling_failure"))
    sensor = district.snapshot()["state"]["transformers"][0]["sensor"]
    assert sensor["status"] == "SIMULATED"
    assert sensor["provenance"] == "CONFIGURED_SIMULATED_ASSUMPTION"
    assert district.snapshot()["state"]["transformers"][0]["diagnosis"]["status"] == "SUSPECTED"
    assert district.apply_action(action(DistrictActionName.transformer_scenario, transformer_id, "clear"))
    assert district.snapshot()["state"]["transformers"][0]["diagnosis"]["status"] == "UNKNOWN"


def test_district_api_can_represent_stale_transformer_observations_as_unknown():
    from app.main import create_app

    with TestClient(create_app()) as client:
        snapshot = client.get("/api/v1/district").json()
        transformer_id = snapshot["state"]["transformers"][0]["component_id"]
        response = client.post("/api/v1/district/action", json={
            "run_id": snapshot["identity"]["run_id"],
            "expected_revision": snapshot["identity"]["revision"],
            "action": "transformer_scenario", "component_id": transformer_id,
            "fault_kind": "stale_sensor"})

        assert response.status_code == 200
        transformer = next(item for item in response.json()["state"]["transformers"]
                           if item["component_id"] == transformer_id)
        assert transformer["sensor"]["status"] == "STALE"
        assert transformer["sensor"]["oil_temperature_c"] == 105.0
        assert transformer["diagnosis"]["status"] == "UNKNOWN"


def test_district_api_validates_snapshot_and_rejects_stale_actions():
    from app.main import create_app

    with TestClient(create_app()) as client:
        snapshot = client.get("/api/v1/district").json()
        identity = snapshot["identity"]
        result = client.post("/api/v1/district/action", json={"run_id": identity["run_id"],
            "expected_revision": identity["revision"], "action": "advance_hour"})
        assert result.status_code == 200
        assert result.json()["energy"]["hour"] == (snapshot["energy"]["hour"] + 1) % 24
        stale = client.post("/api/v1/district/action", json={"run_id": identity["run_id"],
            "expected_revision": identity["revision"], "action": "advance_hour"})
        assert stale.status_code == 409


def test_cached_topology_remains_available_when_shift_runtime_is_missing(monkeypatch):
    monkeypatch.setattr(authority_module, "shift_runtime_probe",
                        lambda: (False, "optional `.venv-city` SHIFT runtime is unavailable."))
    district = DistrictAuthority()
    assert district.generation["status"] == "CACHED"
    assert district.generation["available"] is False
    assert "cached topology is active" in district.generation["reason"].lower()


def test_reset_invalidates_delayed_generation_from_previous_run(monkeypatch):
    async def scenario():
        district = DistrictAuthority()
        starting_topology = copy.deepcopy(district.topology)
        run_id = district.run_id
        task_id = district.generation_task_id = "old-job"
        revision = district.revision = 2
        district.generation["status"] = "GENERATING"
        started, release = asyncio.Event(), asyncio.Event()

        class DelayedProcess:
            returncode = 0

            async def communicate(self):
                started.set()
                await release.wait()
                result = copy.deepcopy(starting_topology)
                result["engine_version"] = "stale-job-result"
                Path(output_path).write_text(json.dumps(result))
                return b"", b""

        async def fake_subprocess(*args, **kwargs):
            nonlocal output_path
            output_path = args[args.index("--output") + 1]
            return DelayedProcess()

        output_path = ""
        monkeypatch.setattr(district_api.asyncio, "create_subprocess_exec", fake_subprocess)
        request = district_api.GenerationRequest(run_id=run_id, expected_revision=revision,
            cluster_count=6, secondary_strategy="MeshSteinerStrategy")
        task = asyncio.create_task(district_api._run_generation(district, Path("python"), Path("script"),
            request, run_id, task_id, revision))
        await started.wait()
        assert district.apply_action(action(DistrictActionName.reset))
        new_run_id = district.run_id
        release.set()
        await task
        assert district.run_id == new_run_id and new_run_id != run_id
        assert district.topology == starting_topology
        assert district.generation["status"] == "CACHED"

    asyncio.run(scenario())
