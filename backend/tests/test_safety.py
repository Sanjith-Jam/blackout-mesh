"""Hard safety constraints for uncertain occupancy predictions (#22)."""
import itertools

from fastapi.testclient import TestClient

import app.main as main
from app.core.allocator import allocate, feasible
from app.core.safety import ActivityGuard, normalize_prediction, shortfall_status
from app.core.state import SERVICE_CATALOG
from app.visualizers import ClassroomDemo

STATES = ("ACTIVE", "UNKNOWN", "INACTIVE")
ROOMS = ("CR1", "CR2", "CR3")


# ---- campus six-service allocator ---------------------------------------------------------

def test_campus_never_sheds_protected_demand_when_a_protected_plan_exists():
    limits = {"A": 6000, "B": 8000}
    checked = 0
    for states in itertools.product(STATES, repeat=3):
        activity = {cid: {"state": st} for cid, st in zip(ROOMS, states)}
        for cap in range(0, 14001, 500):
            for fa, fb in itertools.product((True, False), repeat=2):
                avail = {"A": fa, "B": fb}
                for rooms_requested in range(8):
                    requested = 0b111 | (rooms_requested << 3)
                    mask = allocate(SERVICE_CATALOG, cap, limits, avail, requested, activity)
                    checked += 1
                    assert feasible(mask, SERVICE_CATALOG, cap, limits, avail)
                    for protected in ((0, 1), (0,), (1,)):
                        plan = sum(1 << b for b in protected)
                        if feasible(plan, SERVICE_CATALOG, cap, limits, avail):
                            assert all(mask & (1 << b) for b in protected), (states, cap, avail, bin(mask))
                            break
                    # A prediction alone never cancels a requested room that still fits.
                    for bit in (3, 4, 5):
                        if requested & (1 << bit) and not mask & (1 << bit):
                            assert not feasible(mask | (1 << bit), SERVICE_CATALOG, cap, limits, avail)
    assert checked == 27 * 29 * 4 * 8


def test_false_inactive_everywhere_still_serves_rooms_with_spare_capacity():
    activity = {cid: {"state": "INACTIVE"} for cid in ROOMS}
    mask = allocate(SERVICE_CATALOG, 14000, {"A": 6000, "B": 8000}, {"A": True, "B": True}, 0b111111, activity)
    assert mask == 0b111111


# ---- evidence guard -----------------------------------------------------------------------

def test_failed_or_malformed_inference_is_unknown_with_a_reason():
    for bad in (None, {}, {"state": "MAYBE", "score": 0.5}, {"state": "ACTIVE", "score": None},
                {"state": "INACTIVE", "score": 7}, {"state": "ACTIVE", "score": True}):
        out = normalize_prediction(bad)
        assert out["state"] == "UNKNOWN" and out["reason"]
    guard = ActivityGuard()
    out = guard.update("CR1", None, 1)
    assert out["state"] == "UNKNOWN" and out["guard"].startswith("conservative fallback")


def test_inactive_needs_consecutive_distinct_readings_and_chatter_resets_it():
    guard = ActivityGuard(confirmations=2)
    inactive = {"state": "INACTIVE", "score": 0.05}
    active = {"state": "ACTIVE", "score": 0.95}
    assert guard.update("CR1", active, 1)["state"] == "ACTIVE"
    first = guard.update("CR1", inactive, 2)
    assert first["state"] == "UNKNOWN" and first["raw_state"] == "INACTIVE" and "1/2" in first["guard"]
    assert guard.update("CR1", inactive, 2)["state"] == "UNKNOWN"  # same reading is not counted twice
    assert guard.update("CR1", inactive, 3)["state"] == "INACTIVE"
    assert guard.update("CR1", active, 4)["state"] == "ACTIVE"  # upgrades apply at once
    assert guard.update("CR1", inactive, 5)["state"] == "UNKNOWN"  # chatter restarts confirmation
    assert guard.update("CR2", inactive, 1)["state"] == "UNKNOWN"  # rooms are independent


def test_shortfall_is_quantified_never_called_feasible():
    assert shortfall_status(3000, 3000)["status"] == "FEASIBLE"
    short = shortfall_status(3000, 1000)
    assert short["status"] == "PROTECTED_SHORTFALL" and short["protected_shortfall_w"] == 2000


def test_campus_snapshot_reports_protected_shortfall():
    grid = main.app.state.grid
    client = TestClient(main.app)
    try:
        client.post("/api/v1/simulation/capacity", json={"capacity_w": 0})
        safety = client.get("/api/v1/snapshot").json()["allocation"]["safety"]
        assert safety["status"] == "PROTECTED_SHORTFALL" and safety["protected_shortfall_w"] == 3000
        client.post("/api/v1/simulation/capacity", json={"capacity_w": 14000})
        client.post("/api/v1/simulation/feeder", json={"feeder": "A", "available": False})
        safety = client.get("/api/v1/snapshot").json()["allocation"]["safety"]
        assert safety["status"] == "PROTECTED_SHORTFALL" and safety["protected_shortfall_w"] == 3000
    finally:
        client.post("/api/v1/simulation/feeder", json={"feeder": "A", "available": True})
        grid.tick()


def test_campus_failed_inference_is_visible_conservative_fallback(monkeypatch):
    class Broken:
        def predict(self, _):
            raise RuntimeError("model down")

        def status(self):
            return {"ready": False, "model_version": "broken", "fallback_reason": "model down"}

    grid = main.app.state.grid
    monkeypatch.setattr(grid, "model", Broken())
    grid.activity_guard.reset()
    from datetime import datetime, timezone
    client = TestClient(main.app)
    body = {"classroom_id": "CR2", "temperature_c": 22.0, "humidity_pct": 40.0, "co2_ppm": 700.0,
            "humidity_ratio": 0.007, "observed_at": datetime.now(timezone.utc).isoformat(), "source": "SIMULATED"}
    activity = client.post("/api/v1/activity/observations", json=body).json()["activity"]
    assert activity["state"] == "UNKNOWN" and activity["guard"].startswith("conservative fallback")
    assert activity["priority"] == "MEDIUM"  # no hidden escalation above UNKNOWN


# ---- classroom demo -----------------------------------------------------------------------

class CO2Model:
    def predict(self, features):
        co2 = features["co2_ppm"]
        state = "ACTIVE" if co2 >= 800 else "INACTIVE" if co2 <= 300 else "UNKNOWN"
        return {"state": state, "score": min(co2 / 1000, 1.0), "reason": "stub", "model_version": "stub"}

    def status(self):
        return {"ready": True, "model_version": "stub"}


CO2 = {"ACTIVE": 900, "UNKNOWN": 500, "INACTIVE": 200}


def replay_for(states):
    return {cid: [{"temperature_c": 21.0, "humidity_pct": 30.0, "co2_ppm": CO2[st], "humidity_ratio": 0.004}] * 2
            for cid, st in zip(ROOMS, states)}


def test_classroom_essentials_are_protected_across_all_predictions_scans_and_supplies():
    checked = 0
    for states in itertools.product(STATES, repeat=3):
        for scanned in itertools.chain.from_iterable(itertools.combinations(ROOMS, n) for n in range(4)):
            demo = ClassroomDemo(lambda: 0.0, CO2Model(), replay_for(states))
            demo.act("replay_pause")
            demo.act("replay_step")  # second reading confirms any INACTIVE
            for cid in scanned:
                demo.act("scan", cid)
            for cap in range(8000, -1, -200):
                snap = demo.act("set_capacity", capacity_w=cap)
                checked += 1
                assert snap["served_w"] <= cap
                essential_served = sum(load["watts"] for room in snap["rooms"] for load in room["loads"]
                                       if load["essential"] and load["served"])
                safety = snap["safety"]
                assert safety["protected_requested_w"] == 2100
                assert safety["protected_served_w"] == essential_served
                if cap >= 2100:
                    assert essential_served == 2100 and safety["status"] == "FEASIBLE", (states, scanned, cap)
                else:
                    assert safety["status"] == "PROTECTED_SHORTFALL"
                    assert safety["protected_shortfall_w"] == 2100 - essential_served > 0
    assert checked == 27 * 8 * 41


def test_classroom_reports_guard_reasons_per_room():
    demo = ClassroomDemo(lambda: 0.0, CO2Model(), replay_for(("INACTIVE", "ACTIVE", "UNKNOWN")))
    rooms = {r["id"]: r["activity"] for r in demo.snapshot()["rooms"]}
    assert rooms["CR1"]["state"] == "UNKNOWN" and rooms["CR1"]["raw_state"] == "INACTIVE" and "1/2" in rooms["CR1"]["guard"]
    assert rooms["CR2"]["state"] == "ACTIVE" and rooms["CR2"]["guard"] is None
    assert rooms["CR3"]["guard"].startswith("conservative fallback")


def test_rank_dwell_holds_a_changed_state_until_it_repeats():
    from app.core.safety import RankDwell
    dwell = RankDwell(hold=3)
    active, inactive = {"state": "ACTIVE", "score": 0.9}, {"state": "INACTIVE", "score": 0.1}
    assert dwell.update("CR1", active, 1)["state"] == "ACTIVE"  # first reading sets the state at once
    held = dwell.update("CR1", inactive, 2)
    assert held["state"] == "ACTIVE" and "1/3" in held["guard"]
    assert dwell.update("CR1", inactive, 2)["state"] == "ACTIVE"  # the same reading is not counted twice
    assert dwell.update("CR1", active, 3)["state"] == "ACTIVE"  # a one-reading blip never switched anything
    assert [dwell.update("CR1", inactive, k)["state"] for k in (4, 5, 6)] == ["ACTIVE", "ACTIVE", "INACTIVE"]
    assert dwell.update("CR2", inactive, 1)["state"] == "INACTIVE"  # rooms are independent


def test_rank_dwell_never_holds_a_ranking_without_evidence():
    from app.core.safety import RankDwell
    dwell = RankDwell(hold=3)
    dwell.update("CR1", {"state": "INACTIVE", "score": 0.1}, 1)
    failed = dwell.update("CR1", normalize_prediction(None), 2)
    assert failed["state"] == "UNKNOWN" and failed["dwell"] is None
