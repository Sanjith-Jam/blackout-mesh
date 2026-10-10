from datetime import datetime, timezone

import time
import pytest
from fastapi.testclient import TestClient

from app.core.allocator import feasible
from app.core.restoration import RestorationGate
from app.core.state import SERVICE_CATALOG, GridState
from app.main import app, get_grid_state
from app.activity.model import ActivityModel


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()



@pytest.fixture(autouse=True)
def clean_grid():
    grid = app.state.grid
    saved_model = grid.model
    with grid._lock:
        grid.source_capacity_w = 14000
        grid.feeder_limits_w = {"A": 6000, "B": 8000}
        grid.feeder_available = {"A": True, "B": True}
        grid.control_revision = 0
        grid.active_classroom_id = None
        grid.classroom_load_events = {"CR1": False, "CR2": False, "CR3": False}
        grid.software_mode = False
        grid.activity_tokens = {"CR1": 0, "CR2": 0, "CR3": 0}
        grid.activity_received_monotonic = {"CR1": None, "CR2": None, "CR3": None}
        grid.last_allocation_mask = 0
        grid.last_allocation_key = None
        grid.proposed_mask = 0
        grid.restoration_gate = RestorationGate(time.monotonic)
        grid.restoration_gate.update(0b111111, (14000, (("A", 6000), ("B", 8000)), (("A", True), ("B", True))), range(6))
        grid.activity = {cid: {"state": "UNKNOWN", "score": None, "reason": "no sensor observation",
                               "source": None, "observed_at": None, "recorded_at": None,
                               "model_version": "unavailable", "priority": "UNKNOWN",
                               "evidence": {"temperature_c": None, "humidity_pct": None,
                                            "co2_ppm": None, "humidity_ratio": None}}
                        for cid in ("CR1", "CR2", "CR3")}
    yield grid
    grid.model = saved_model


def test_activity_observation_requires_current_typed_evidence(client):
    now = datetime.now(timezone.utc).isoformat()
    payload = {"classroom_id": "CR1", "temperature_c": 22.5, "humidity_pct": 40,
               "co2_ppm": 700, "humidity_ratio": 0.007, "observed_at": now,
               "source": "SIMULATED"}
    assert client.post("/api/v1/activity/observations", json=payload).status_code == 200
    assert client.post("/api/v1/activity/observations", json={**payload, "extra": 1}).status_code == 422
    assert client.post("/api/v1/activity/observations", json={**payload, "classroom_id": "CR4"}).status_code == 422
    assert client.post("/api/v1/activity/observations", json={**payload, "co2_ppm": True}).status_code == 422
    assert client.post("/api/v1/activity/observations", json={**payload, "observed_at": "2000-01-01T00:00:00Z"}).status_code == 422
    assert client.post("/api/v1/simulation/capacity", json={"capacity_w": True}).status_code == 422
    assert client.post("/api/v1/simulation/capacity", json={"capacity_w": 0}).status_code == 200
    assert client.post("/api/v1/simulation/classroom-load", json={"classroom_id": "CR4", "active": True}).status_code == 422
    assert client.post("/api/v1/simulation/feeder", json={"feeder": "C", "available": True}).status_code == 422


def test_real_model_observation_endpoint_returns_evidence_and_prediction(clean_grid, client, monkeypatch):
    import app.main as main
    monkeypatch.setattr(clean_grid, "model", ActivityModel())
    payload = {"classroom_id": "CR2", "temperature_c": 22.0, "humidity_pct": 40.0,
               "co2_ppm": 700.0, "humidity_ratio": 0.007,
               "observed_at": datetime.now(timezone.utc).isoformat(), "source": "SIMULATED"}
    response = client.post("/api/v1/activity/observations", json=payload)
    assert response.status_code == 200
    result = response.json()["activity"]
    assert result["state"] in ("ACTIVE", "INACTIVE", "UNKNOWN")
    assert result["model_version"] == clean_grid.model.status()["model_version"]
    assert result["evidence"]["co2_ppm"] == 700.0


def test_snapshot_exposes_activity_contract_and_honest_hardware_status(client):
    snapshot = client.get("/api/v1/snapshot").json()
    assert set(snapshot["activity"]) == {"CR1", "CR2", "CR3"}
    assert {"ready", "model_type", "model_version", "features", "data_source", "evaluation", "fallback_reason"} <= set(snapshot["model"])
    assert snapshot["hardware_link"] == "NOT_CONNECTED"
    assert snapshot["indicator_confirmed_mask"] is None


def test_feasibility_matches_independent_constraint_oracle_for_all_masks(client):
    limits, capacity, feeders = {"A": 6000, "B": 8000}, 9000, {"A": True, "B": False}
    for mask in range(64):
        selected = [svc for bit, svc in enumerate(SERVICE_CATALOG) if mask & (1 << bit)]
        expected = (sum(s["watts"] for s in selected) <= capacity
                    and sum(s["watts"] for s in selected if s["feeder"] == "A") <= limits["A"]
                    and sum(s["watts"] for s in selected if s["feeder"] == "B") <= limits["B"]
                    and all(feeders[s["feeder"]] for s in selected))
        assert feasible(mask, SERVICE_CATALOG, capacity, limits, feeders) is expected


def test_restoration_sheds_immediately_then_waits_and_adds_one_per_second(client):
    now = [0.0]
    gate = RestorationGate(lambda: now[0])
    assert gate.update(0b111, (14000, "connected"), [0, 1, 2]) == 0b111
    now[0] = 1
    assert gate.update(0b011, (6000, "connected"), [0, 1, 2]) == 0b011
    now[0] = 2
    assert gate.update(0b1111, (14000, "connected"), [0, 1, 2, 3]) == 0b011
    now[0] = 6.9
    assert gate.update(0b1111, (14000, "connected"), [0, 1, 2, 3]) == 0b011
    now[0] = 7
    assert gate.update(0b1111, (14000, "connected"), [0, 1, 2, 3]) == 0b111
    now[0] = 7.9
    assert gate.update(0b1111, (14000, "connected"), [0, 1, 2, 3]) == 0b111
    now[0] = 8
    assert gate.update(0b1111, (14000, "connected"), [0, 1, 2, 3]) == 0b1111


def test_activity_prediction_updates_allocation_policy(client, monkeypatch):
    grid = app.state.grid

    class StubModel:
        def __init__(self, state):
            self.state = state

        def predict(self, _features):
            return {"state": self.state, "score": 0.9 if self.state == "ACTIVE" else 0.1,
                    "reason": "test prediction", "model_version": "test"}

        def status(self):
            return {"ready": True, "model_type": "test", "model_version": "test", "features": [],
                    "data_source": "test", "evaluation": {}, "fallback_reason": None}

    app.dependency_overrides[get_grid_state] = lambda: grid
    with grid._lock:
        grid.source_capacity_w = 5000
        grid.feeder_available = {"A": True, "B": True}
        grid.feeder_limits_w = {"A": 6000, "B": 8000}
        grid.active_sessions = {"CR1": {"source": "UI", "started_at": time.time(), "last_scan": time.time()}, "CR2": {"source": "UI", "started_at": time.time(), "last_scan": time.time()}, "CR3": {"source": "UI", "started_at": time.time(), "last_scan": time.time()}}
        grid.software_mode = True
        grid.model = StubModel("ACTIVE")
    features = {"temperature_c": 22.0, "humidity_pct": 40.0, "co2_ppm": 700.0, "humidity_ratio": 0.007}
    def send(cid):
        time.sleep(0.001)
        return client.post("/api/v1/activity/observations", json={"classroom_id": cid, **features,
                            "observed_at": datetime.now(timezone.utc).isoformat(), "source": "SIMULATED"}).json()
    print(send("CR1"))
    grid.model = StubModel("INACTIVE")
    print(send("CR2"))
    print('ACTIVITY:', grid.activity); grid.compute_allocation()
    cr1_priority_mask = grid.proposed_mask
    assert cr1_priority_mask & (1 << 3)
    assert not cr1_priority_mask & (1 << 4)
    # A changed state reorders loads only after it repeats on RANK_DWELL_READINGS readings.
    from app.core.safety import RANK_DWELL_READINGS
    for _ in range(RANK_DWELL_READINGS + 1):
        grid.model = StubModel("ACTIVE")
        send("CR2")
        grid.model = StubModel("INACTIVE")
        send("CR1")
    print('ACTIVITY:', grid.activity); grid.compute_allocation()
    cr2_priority_mask = grid.proposed_mask
    assert cr2_priority_mask & (1 << 4)
    assert not cr2_priority_mask & (1 << 3)
    assert grid.activity["CR2"]["state"] == "ACTIVE"


def test_failed_inference_and_stale_evidence_become_unknown(clean_grid, client, monkeypatch):
    class BrokenModel:
        def predict(self, _features):
            raise RuntimeError("model failed")
        def status(self):
            return {"ready": False, "model_type": "test", "model_version": "test", "features": [],
                    "data_source": "test", "evaluation": {}, "fallback_reason": "model failed"}
    grid = clean_grid
    app.dependency_overrides[get_grid_state] = lambda: grid
    monkeypatch.setattr(grid, "model", BrokenModel())
    now = datetime.now(timezone.utc).isoformat()
    payload = {"classroom_id": "CR1", "temperature_c": 22.0, "humidity_pct": 40.0,
               "co2_ppm": 700.0, "humidity_ratio": 0.007, "observed_at": now,
               "source": "SIMULATED"}
    response = client.post("/api/v1/activity/observations", json=payload)
    assert response.json()["activity"]["state"] == "UNKNOWN"
    grid.activity_received_monotonic["CR1"] = time.monotonic() - 601
    grid.tick()  # staleness is applied by the control loop, not by reads
    assert client.get("/api/v1/snapshot").json()["activity"]["CR1"]["reason"] == "sensor evidence stale"


def test_replay_start_is_single_owner_and_pause_reset_invalidate(clean_grid, monkeypatch):
    import app.main as main

    class ReplayModel:
        calls = 0
        def predict(self, _features):
            self.calls += 1
            return {"state": "ACTIVE", "score": 0.8, "reason": "replay test", "model_version": "test"}
        def status(self):
            return {"ready": True, "model_type": "test", "model_version": "test", "features": [],
                    "data_source": "test", "evaluation": {}, "fallback_reason": None}

    row = {"temperature_c": 22.0, "humidity_pct": 40.0, "co2_ppm": 700.0,
           "humidity_ratio": 0.007, "observed_at": "2016-01-01T00:00:00Z"}
    model = ReplayModel()
    app.state.replay_data = {cid: [row] for cid in ("CR1", "CR2", "CR3")}
    app.state.grid.replay_length = 1
    with TestClient(app) as replay_client:
        app.state.grid.model = model
        started = replay_client.post("/api/v1/replay", json={"action": "start"}).json()
        assert started["running"] is True and started["length"] == 1
        replay_client.post("/api/v1/replay", json={"action": "start"})
        time.sleep(0.1)
        assert model.calls == 3
        assert app.state.grid.replay_index == 0  # one-row stream wraps without exceeding its length
        assert app.state.grid.activity["CR1"]["source"] == "RECORDED_REPLAY"
        assert app.state.grid.activity["CR1"]["recorded_at"] == row["observed_at"]
        paused = replay_client.post("/api/v1/replay", json={"action": "pause"}).json()
        assert paused["running"] is False
        reset = replay_client.post("/api/v1/replay", json={"action": "reset"}).json()
        assert reset["index"] == 0 and reset["running"] is False
        assert clean_grid.activity["CR1"]["state"] == "UNKNOWN"
