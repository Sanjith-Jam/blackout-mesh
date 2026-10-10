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
