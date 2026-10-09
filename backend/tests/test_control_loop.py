"""Control loop (#9) and read-only reads (#10)."""
import asyncio
import hashlib
import json
import time

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.core.control_loop import ControlLoop
from app.core.restoration import RestorationGate
from app.core.state import GridState
from app.visualizers import ClassroomDemo


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def grid_clock(monkeypatch):
    """The singleton grid on a frozen virtual clock, reset to the normal 14 kW campus."""
    grid = GridState()
    clock = FakeClock(1000.0)
    with grid._lock:
        grid.clock = clock
        grid.source_capacity_w = 14000
        grid.feeder_available = {"A": True, "B": True}
        grid.software_mode = False
        grid.active_classroom_id = None
        grid.classroom_load_events = {"CR1": False, "CR2": False, "CR3": False}
        grid.activity_received_monotonic = {"CR1": None, "CR2": None, "CR3": None}
        grid.last_allocation_key = None
        grid.restoration_gate = RestorationGate(lambda: grid.clock())
        grid.restoration_gate.update(0b111111, (14000, (("A", 6000), ("B", 8000)), (("A", True), ("B", True))), range(6))
        grid.last_allocation_mask = 0b111111
        grid.tick()
    demo = ClassroomDemo(FakeClock(0.0))
    monkeypatch.setattr(main, "grid", grid)
    monkeypatch.setattr(main, "classroom_demo", demo)
    monkeypatch.setattr(main.site, "classroom", demo)
    yield grid, clock, demo
    grid.clock = time.monotonic
    grid.restoration_gate = RestorationGate(time.monotonic)


def grid_fingerprint(grid):
    gate = grid.restoration_gate
    state = {
        "masks": [grid.last_allocation_mask, grid.proposed_mask],
        "gate": [gate.applied_mask, gate.stable_since, gate.last_shed, gate.last_restored, repr(gate.signature)],
        "revisions": [grid.control_revision, grid.published_revision, grid.tick_count],
        "events": len(grid.events),
        "published": grid.published.model_dump_json(),
    }
    return hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()


def demo_fingerprint(demo):
    gate = demo.gate
    state = [gate.applied_mask, gate.stable_since, gate.last_shed, gate.last_restored,
             demo.replay_index(), len(demo._predictions), demo.published_revision, json.dumps(demo.published, sort_keys=True)]
    return hashlib.sha256(json.dumps(state, default=str).encode()).hexdigest()


def test_reads_never_change_domain_state(grid_clock):
    grid, clock, demo = grid_clock
    client = TestClient(main.app)  # no lifespan: nothing ticks in the background
    client.post("/api/v1/simulation/capacity", json={"capacity_w": 6000})
    client.post("/api/v1/visualizers/classrooms", json={"action": "scan", "classroom_id": "CR1"})
    clock.t += 30
    demo.gate.clock.t += 30
    before = grid_fingerprint(grid), demo_fingerprint(demo)
    first = [client.get(path).json() for path in ("/api/v1/snapshot", "/api/v1/visualizers/classrooms")]
    for _ in range(100):
        for path in ("/api/v1/snapshot", "/api/v1/visualizers/classrooms", "/api/v1/visualizers/hospital",
                     "/api/v1/model/status", "/api/v1/health"):
            assert client.get(path).status_code == 200
    assert (grid_fingerprint(grid), demo_fingerprint(demo)) == before
    # Unchanged state reads back as the identical payload, generated_at included.
    assert [client.get(path).json() for path in ("/api/v1/snapshot", "/api/v1/visualizers/classrooms")] == first


def run_timeline(grid, clock, reads_per_tick):
    """Shortage then recovery on a virtual 250 ms tick, with N reads between ticks."""
    grid.set_capacity(6000)
    grid.tick()
    grid.set_capacity(14000)
    grid.tick()
    masks = []
    for _ in range(40):  # 10 virtual seconds
        clock.t += 0.25
        grid.tick()
        for _ in range(reads_per_tick):
            grid.build_snapshot()
        masks.append(grid.published.modeled_mask)
    return masks


def test_restoration_schedule_is_independent_of_reader_count(grid_clock):
    grid, clock, _ = grid_clock
    quiet = run_timeline(grid, clock, 0)
    clock.t += 100
    busy = run_timeline(grid, clock, 100)
    assert quiet == busy
    # Shedding was immediate; restoration waited ~5 s, then added at most one load per second.
    assert quiet[0] != 0b111111
    restored_at = [i for i in range(1, len(quiet)) if quiet[i] != quiet[i - 1]]
    assert restored_at and (restored_at[0] + 1) * 0.25 >= 5
    assert all(b - a >= 4 for a, b in zip(restored_at, restored_at[1:]))
    assert quiet[-1] == 0b111111


def test_protective_shedding_applies_in_the_command_response(grid_clock):
    grid, clock, _ = grid_clock
    client = TestClient(main.app)
    client.post("/api/v1/simulation/feeder", json={"feeder": "A", "available": False})
    snap = client.get("/api/v1/snapshot").json()
    assert snap["modeled_mask"] & 0b111 == 0  # feeder A loads shed without waiting for a tick or a read


def test_socket_payload_keeps_state_time_and_adds_transport_time(grid_clock):
    grid, _, _ = grid_clock
    a = json.loads(main.socket_payload(grid.build_snapshot()))
    b = json.loads(main.socket_payload(grid.build_snapshot()))
    assert a["generated_at"] == b["generated_at"] and a["published_revision"] == b["published_revision"]
    assert "sent_at" in a


def test_loop_is_single_owner_counts_overruns_and_survives_errors():
    calls = []

    def slow():
        calls.append(1)
        time.sleep(0.03)

    def broken():
        raise ValueError("boom")

    async def scenario():
        loop = ControlLoop([slow, broken], period_s=0.01)
        loop.start()
        with pytest.raises(RuntimeError):
            loop.start()
        await asyncio.sleep(0.2)
        health = loop.health()
        await loop.stop()
        return loop, health

    loop, health = asyncio.run(scenario())
    assert health["running"] and loop.task is None
    assert health["missed_ticks"] > 0 and health["errors"] > 0 and "boom" in health["last_error"]
    count = len(calls)
    time.sleep(0.05)
    assert len(calls) == count  # stopped loop does not keep ticking


def test_lifespan_runs_exactly_one_loop_and_health_reports_it():
    with TestClient(main.app) as client:
        time.sleep(0.6)
        health = client.get("/api/v1/health").json()["control_loop"]
        assert health["running"] and health["tick_count"] >= 2 and health["errors"] == 0
    assert main.control_loop.task is None
