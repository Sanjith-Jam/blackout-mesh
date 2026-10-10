"""Allocation benchmark harness (#20)."""
import random

import pytest

from benchmarks import allocation as bench
from benchmarks.run_allocation import markdown, summarize
from app.core.allocator import allocate, feasible
from app.core.state import SERVICE_CATALOG


def test_energy_integration_matches_a_hand_computed_fixture():
    steps = [bench.Step(t * bench.STEP_S, 2000, (("A", True), ("B", True)), ("CR1",)) for t in range(3)]
    timeline = bench.Timeline("fixture", 0, steps, [{"CR1": True, "CR2": False, "CR3": False}] * 3, {})
    masks = [0b000001] * 3  # only L0 (2,000 W) served
    out = bench.evaluate(timeline, masks)
    hours = 3 * bench.STEP_S / 3600
    assert out["critical_unmet_wh"] == pytest.approx(1000 * hours, abs=1e-3)       # L1 unmet
    assert out["essential_unmet_wh"] == pytest.approx(bench.ROOM_ESSENTIAL_W * hours, abs=1e-3)  # CR1 booked, unserved
    assert out["served_wh"] == pytest.approx(2000 * hours, abs=1e-3)
    assert out["occupied_service_fraction"] == 0.0 and out["worst_room_starvation_s"] == 3 * bench.STEP_S


@pytest.mark.parametrize("masks, expected_gini", [([11, 11, 3], .5), ([11, 27, 19], 0), ([3, 3, 3], None)])
def test_citylearn_service_equity_uses_per_room_fractions_and_preserves_unknown(masks, expected_gini):
    bookings = [("CR1",), ("CR1", "CR2"), ("CR2",)]
    steps = [bench.Step(k * bench.STEP_S, 14000, (("A", True), ("B", True)), rooms)
             for k, rooms in enumerate(bookings)]
    truth = [{r: r in rooms for r in bench.ROOMS} for rooms in bookings]
    result = bench.evaluate(bench.Timeline("fixture", 0, steps, truth, {}), masks)
    assert result["occupied_service_gini"] == expected_gini
    assert result["occupied_service_by_room"]["CR1"]["requested_s"] == 2 * bench.STEP_S
    assert result["occupied_service_by_room"]["CR2"]["requested_s"] == 2 * bench.STEP_S
    assert result["occupied_service_by_room"]["CR3"] == {"requested_s": 0, "served_s": 0, "fraction": None}


def test_citylearn_no_occupied_demand_remains_unknown_and_reports_render():
    result = bench.evaluate(bench.Timeline("fixture", 0, [], [], {}), [])
    assert result["occupied_service_gini"] is None
    assert all(room["fraction"] is None for room in result["occupied_service_by_room"].values())
    report = bench.run_benchmark(scenarios=["zero_supply"], seeds=[0])
    for run in report["runs"]:
        run["occupied_service_gini"] = None
    derived = summarize(report)
    assert all("occupied_service_gini" in row for row in derived["summary"].values())
    assert all(row["occupied_service_gini_defined_runs"] == 0 for row in derived["summary"].values())
    assert "Room service Gini" in markdown(report, derived, "test")
    assert "— (0/1)" in markdown(report, derived, "test")


class TruthTrap(list):
    def __getitem__(self, item):
        raise AssertionError("deployable policy read true occupancy")


def test_deployable_policies_never_read_truth_and_all_get_identical_inputs():
    timeline = bench.make_timeline("shortage_6kw", 3)
    digest = timeline.input_digest()
    trapped = bench.Timeline(timeline.scenario, timeline.seed, timeline.steps, TruthTrap(timeline.occupied), timeline.predictions)
    for policy in bench.all_policies():
        if policy.deployable:
            bench.run_policy(policy, trapped)
        assert trapped.input_digest() == digest
    with pytest.raises(AssertionError):
        bench.run_policy(bench.Oracle(), trapped)


def test_allocator_is_optimal_for_protected_service_on_small_cases():
    rng = random.Random(7)
    limits = {"A": 6000, "B": 8000}
    for _ in range(300):
        cap = rng.choice(range(0, 14001, 500))
        avail = {"A": rng.random() > 0.2, "B": rng.random() > 0.2}
        requested = 0b111 | (rng.randrange(8) << 3)
        activity = {r: {"state": rng.choice(("ACTIVE", "UNKNOWN", "INACTIVE"))} for r in bench.ROOMS}
        mask = allocate(SERVICE_CATALOG, cap, limits, avail, requested, activity)
        assert feasible(mask, SERVICE_CATALOG, cap, limits, avail)
        best_critical = max(bin(m & 0b11).count("1") for m in range(64)
                            if not m & ~requested and feasible(m, SERVICE_CATALOG, cap, limits, avail))
        assert bin(mask & 0b11).count("1") == best_critical


def test_no_unsafe_allocations_and_impossible_critical_demand_is_counted():
    report = bench.run_benchmark(scenarios=["zero_supply", "insufficient_critical_2kw", "feeder_a_loss"], seeds=range(2))
    assert all(r["constraint_violations"] == 0 for r in report["runs"])
    for scenario in report["scenarios"]:
        unmet = {r["critical_unmet_wh"] for r in report["runs"] if r["scenario"] == scenario}
        assert len(unmet) == 1 and unmet.pop() > 0  # unavoidable, identical across policies, never hidden


def test_benchmark_is_deterministic_and_reports_denominators():
    a = bench.run_benchmark(scenarios=["shortage_6kw"], seeds=[0])
    b = bench.run_benchmark(scenarios=["shortage_6kw"], seeds=[0])
    assert a == b
    run = a["runs"][0]
    assert run["steps"] == int(bench.DURATION_S / bench.STEP_S) and run["occupied_requested_s"] > 0
    assert {r["policy"] for r in a["runs"]} >= {"fixed_priority", "essentials_first_no_ml", "round_robin",
                                               "proposed[no_ml_unknown]", "proposed[validation_rates]",
                                               "oracle_occupancy_upper_bound"}
