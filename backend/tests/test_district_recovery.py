import pytest

from benchmarks.district_recovery import act, assert_safe, radial_fixture


def prepared():
    district = radial_fixture()
    for edge in ("a", "load-4"):
        assert act(district, "inject_fault", edge)
        assert_safe(district)
    assert act(district, "propose_recovery")
    assert district.candidate_tie == "tie-ab" and district.closed_tie is None
    assert not act(district, "apply_recovery")
    for _ in range(2):
        assert act(district, "advance_hour")
    return district


def test_two_faults_restore_only_reachable_island_and_keep_proposal_separate():
    district = prepared()
    assert act(district, "apply_recovery")
    assert district.closed_tie == "tie-ab" and district.candidate_tie is None
    assert_safe(district)
    loads = district.snapshot()["state"]["loads"]
    assert next(load for load in loads if load["building_id"] == "L4")["grid_served_w"] == 0
    assert district.snapshot()["state"]["unmet_w"] == 1000


@pytest.mark.parametrize("change", ["source", "line", "topology"])
def test_changed_limits_or_topology_require_new_evidence(change):
    district = prepared()
    if change == "source":
        district.source_capacity_w = 4000
    elif change == "line":
        next(edge for edge in district.topology["edges"] if edge["id"] == "tie-ab")["limit_w"] = 1000
    else:
        district.topology["edges"] = [edge for edge in district.topology["edges"] if edge["id"] != "tie-ab"]
    assert not act(district, "apply_recovery")
    assert district.closed_tie is None and district.stable_evidence_count == 0
    for _ in range(2):
        act(district, "advance_hour")
    assert not act(district, "apply_recovery")
    assert_safe(district)


def test_fresh_apply_rejects_no_longer_beneficial_demand():
    district = prepared()
    district.energy_trace["profile"][district.hour]["grid_import_w"] = 0
    assert not act(district, "apply_recovery")
    assert "does not increase" in district.snapshot()["state"]["restoration"]["reason"]
    assert district.closed_tie is None


def test_protective_fault_resets_gate_and_snapshot_reads_do_not_supply_evidence():
    district = prepared()
    assert act(district, "inject_fault", "b")
    assert district.stable_evidence_count == 0
    for _ in range(3):
        district.snapshot()
    assert not act(district, "apply_recovery")
    assert_safe(district)


def test_clear_revalidates_source_and_restarts_gate_after_each_clear():
    district = prepared()
    district.source_capacity_w = 4000
    assert not act(district, "clear_fault", "a")
    for _ in range(2):
        act(district, "advance_hour")
    assert not act(district, "clear_fault", "a")
    assert "capacity" in district.restoration_reason.lower()
    assert "a" in district.faults
    district.source_capacity_w = 6000
    for _ in range(2):
        act(district, "advance_hour")
    assert act(district, "clear_fault", "a")
    assert not act(district, "clear_fault", "load-4")
    assert_safe(district)

def test_restoration_contract_keeps_physical_confirmation_unknown():
    import json
    from pathlib import Path
    from app.api.district import DistrictRestoration, DistrictSnapshot
    district = prepared()
    assert act(district, "apply_recovery")
    snapshot = DistrictSnapshot.model_validate(district.snapshot())
    restoration = snapshot.state.restoration
    assert restoration.candidate_edge_id is None
    assert restoration.applied_edge_id == "tie-ab"
    assert restoration.physical_confirmed_edge_id is None
    fixture = Path(__file__).resolve().parents[2] / "frontend/src/test/fixtures/district_restoration.json"
    assert DistrictRestoration.model_validate_json(fixture.read_text()).model_dump() == restoration.model_dump()
    with pytest.raises(ValueError):
        DistrictRestoration.model_validate({**json.loads(fixture.read_text()),
                                            "physical_confirmed_edge_id": "tie-ab"})


def test_topology_generation_cannot_bypass_fault_repair_gate(monkeypatch):
    import asyncio
    import json
    from pathlib import Path
    from app.api import district as api

    district = prepared()
    assert act(district, "apply_recovery")
    district.generation_task_id = "current"
    previous = district.topology
    result = radial_fixture("chain").topology

    class Process:
        returncode = 0

        async def communicate(self):
            return b"", b""

    async def subprocess(*args, **kwargs):
        Path(args[args.index("--output") + 1]).write_text(json.dumps(result))
        return Process()

    monkeypatch.setattr(api.asyncio, "create_subprocess_exec", subprocess)
    request = api.GenerationRequest(run_id=district.run_id, expected_revision=district.revision,
                                    cluster_count=3, secondary_strategy="RadialStrategy")
    asyncio.run(api._run_generation(district, Path("python"), Path("script"), request,
                                   district.run_id, "current", district.revision))
    assert district.topology == previous
    assert district.faults == {"a", "load-4"} and district.closed_tie == "tie-ab"
    assert district.generation["status"] == "FAILED"
    assert_safe(district)


def test_new_fault_isolates_immediately_after_an_applied_tie():
    district = prepared()
    assert act(district, "apply_recovery")
    assert act(district, "inject_fault", "b")
    states, loads = district._electrical_state()
    assert states["b"]["flow_w"] == 0 and not states["b"]["energized"]
    assert all(load["grid_served_w"] == 0 for load in loads if load["building_id"] in ("L0", "L1", "L2", "L3"))
    assert district.stable_evidence_count == 0
    assert_safe(district)


def test_clear_rejects_branch_overload_after_fresh_intervals():
    district = prepared()
    next(edge for edge in district.topology["edges"] if edge["id"] == "a")["limit_w"] = 1000
    for _ in range(2):
        act(district, "advance_hour")
    assert not act(district, "clear_fault", "a")
    assert "Line capacity" in district.restoration_reason and "a" in district.faults
    assert_safe(district)


def test_generation_endpoint_rejects_active_fault_study():
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        district = app.state.district
        edge = next(edge["id"] for edge in district.topology["edges"] if edge["kind"] != "tie")
        assert act(district, "inject_fault", edge)
        response = client.post("/api/v1/district/generation", json={
            "run_id": district.run_id, "expected_revision": district.revision,
            "cluster_count": 3, "secondary_strategy": "RadialStrategy"})
        assert response.status_code == 409
        assert "Repair or reset" in response.json()["detail"]
        assert district.faults == {edge}
