"""Shared test isolation: every test starts from the default site (campus, classroom and hospital).

The campus GridState is still a process-wide singleton (#11), and since #3 the classroom view is
bounded by campus feeder B headroom, so leftover campus state would leak between test files.
"""
import time

import pytest

import app.main as main
from app.activity.model import FEATURES
from app.core.restoration import RestorationGate


def reset_campus(grid):
    with grid._lock:
        grid.clock = time.monotonic
        grid.source_capacity_w = 14000
        grid.feeder_limits_w = {"A": 6000, "B": 8000}
        grid.feeder_available = {"A": True, "B": True}
        grid.active_classroom_id = None
        grid.recent_rfid_scan = None
        grid.last_rfid_scan_time = None
        grid.last_rfid_uid = None
        grid.classroom_load_events = {"CR1": False, "CR2": False, "CR3": False}
        grid.indicator_confirmed_mask = None
        grid.software_mode = False
        grid.replay_running = False
        grid.replay_index = 0
        grid.activity_tokens = {"CR1": 0, "CR2": 0, "CR3": 0}
        grid.activity_received_monotonic = {"CR1": None, "CR2": None, "CR3": None}
        grid.activity = {cid: {"state": "UNKNOWN", "score": None, "reason": "no sensor observation",
                               "source": None, "observed_at": None, "recorded_at": None,
                               "model_version": "unavailable", "priority": "UNKNOWN",
                               "evidence": {key: None for key in FEATURES}}
                         for cid in ("CR1", "CR2", "CR3")}
        grid.activity_guard.reset()
        from app.core.policy import AllocationPolicy
        grid.policy = AllocationPolicy()
        grid.waiting_s = {}
        grid.last_policy_tick = grid.clock()
        grid.last_allocation_key = None
        grid.proposed_mask = 0
        grid.restoration_gate = RestorationGate(lambda: grid.clock())
        grid.restoration_gate.update(0b111111, (14000, (("A", 6000), ("B", 8000)), (("A", True), ("B", True))), range(6))
        grid.last_allocation_mask = 0b111111
        grid.compute_fault_diagnosis()


@pytest.fixture(autouse=True)
def default_site():
    site = main.site
    reset_campus(site.grid)
    site.classroom.act("reset")
    site.hospital.act("reset")
    site.tick()
    yield
