"""Board A gateway bridge end to end with a contract-following fake board A (+ board B)."""
import json

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.hardware.gateway import GatewayBridge
from app.visualizers import ClassroomDemo
from app.core.appliance_control import ApplianceController


class FakeBoardA:
    """Speaks contracts/serial_protocol.md v2 for the host side; simulates board B's ACKs."""

    def __init__(self, b_boot=7):
        self.boot, self.epoch, self.floor = 3, 1, 0
        self.b_boot, self.b_online, self.b_session, self.b_applied = b_boot, True, 0, 0
        self.reader_ok = True
        self.ctx = None
        self.out, self.sent = [], []
        self.counter = 0

    # transport interface (host side)
    def write_line(self, line):
        msg = json.loads(line)
        self.sent.append(msg)
        kind = msg["type"]
        if kind == "hello":
            self.epoch += 1
            self.ctx = None
            self._hello()
            return
        if kind == "sync":
            if msg["session"] <= self.floor:
                return self._status("sync_rejected")
            self.ctx = {k: msg[k] for k in ("boot", "epoch", "session")}
            self.floor = msg["session"]
            return self._status("host_synced")
        if not self.ctx or any(msg.get(k) != v for k, v in self.ctx.items()):
            return self._status("stale_context")
        if kind == "ping":
            return self._status("pong")
        if kind == "event_ack":
            return self._status("event_accepted")
        if kind in ("radio_sync", "set_loads"):
            assert msg["target"] == self.b_boot
            self._emit("queued", seq=msg["seq"])
            if kind == "radio_sync":
                self.b_session = self.ctx["session"]
                return self._emit("radio_state", target=self.b_boot, ack_seq=msg["seq"],
                                  applied_classroom_mask=self.b_applied, confirmed=False, result=2)
            self.b_applied = msg["mask"] & 0x38
            return self._emit("radio_state", target=self.b_boot, ack_seq=msg["seq"],
                              applied_classroom_mask=self.b_applied, confirmed=True, result=1)

    def read_lines(self):
        out, self.out = self.out, []
        return out

    # A's own output
    def _emit(self, kind, **fields):
        ctx = self.ctx or {"boot": self.boot, "epoch": self.epoch, "session": 0}
        self.out.append(json.dumps({"v": 2, "type": kind, **ctx, "ms": 1, **fields}))

    def _status(self, code):
        self._emit("status", code=code)

    def _hello(self):
        self.out.append(json.dumps({"v": 2, "type": "hello", "boot": self.boot, "epoch": self.epoch, "session": 0, "ms": 1,
                                    "minimum_session": self.floor, "target": self.b_boot, "reader_ok": self.reader_ok,
                                    "radio_configured": True, "radio_online": self.b_online, "mode": "INPUT_GATEWAY"}))

    def press(self, action, room=None):
        self.counter += 1
        fields = {"event": self.counter, "action": action}
        if room:
            fields["room"] = room
        self._emit("event", **fields)
        if action == "RESET_SESSION":
            self.ctx = None
            self.out.append(json.dumps({"v": 2, "type": "status", "boot": self.boot, "epoch": self.epoch, "session": 0,
                                        "ms": 1, "code": "reset_requires_sync"}))


APP = main.app


def demo():
    return APP.state.classroom_demo


@pytest.fixture
def rig(monkeypatch):
    now = [0.0]
    classroom = ClassroomDemo(lambda: now[0])
    classroom.bind_sessions(APP.state.grid.active_sessions, APP.state.grid.set_classroom_load)
    APP.state.classroom_demo = classroom
    APP.state.site.classroom = classroom
    # Restoration timing lives in the site's appliance-level controller; drive it with the same fake clock.
    APP.state.site.appliances = ApplianceController(lambda: now[0])
    fake = FakeBoardA()
    bridge = GatewayBridge(fake, lambda action, room: main.handle_gateway_event(APP, action, room),
                           lambda: main.desired_led_mask(APP), clock=lambda: now[0], session_seed=lambda: 100)

    class Thread:
        error = None

        def stop(self):
            pass

    APP.state.gateway = (bridge, Thread())

    def run(seconds=0.2):
        end = now[0] + seconds
        while now[0] < end:
            now[0] += 0.05
            APP.state.site.tick()
            bridge.step()

    run(0.5)
    yield fake, bridge, run, now
    APP.state.gateway = None


def test_handshake_binds_board_b_and_reports_connected(rig):
    fake, bridge, run, _ = rig
    status = bridge.status()
    assert status["link"] == "CONNECTED" and status["board_b"]["radio_ready"]
    kinds = [m["type"] for m in fake.sent]
    assert kinds[:2] == ["hello", "sync"] and "radio_sync" in kinds and "ping" in kinds
    assert status["confirmed_mask"] == 0  # nothing scanned: all LEDs off, confirmed


def test_fallback_button_lights_room_a_and_is_confirmed(rig):
    fake, bridge, run, _ = rig
    fake.press("START_SESSION", "A")  # the RFID-fail fallback button sends exactly this event
    run(0.3)
    assert demo().snapshot()["scanned_classroom_ids"] == ["CR1"]
    assert bridge.status()["confirmed_mask"] == 0b001000 and bridge.status()["led_confirmed"]
    campus = TestClient(APP).get("/api/v1/snapshot").json()
    assert campus["zones"]["classroom"]["active_classroom_id"] == "CR1"
    assert next(s for s in campus["services"] if s["id"] == "L3")["requested"]
    assert any(m["type"] == "event_ack" and m["accepted"] for m in fake.sent)
    hw = TestClient(APP).get("/api/v1/visualizers/classrooms").json()["hardware"]
    assert hw["link"] == "CONNECTED" and hw["confirmed_mask"] == 8


def test_deprived_and_normal_buttons_change_which_leds_are_on(rig):
    fake, bridge, run, now = rig
    fake.press("START_SESSION", "A")
    fake.press("START_SESSION", "B")
    run(0.3)
    assert bridge.status()["confirmed_mask"] == 0b011000  # normal supply: both rooms fully served
    fake.press("SIMULATE_SHORTAGE")                         # deprived of kW: 3,400 W preset
    run(0.3)
    assert demo().snapshot()["capacity_w"] == 3400
    assert bridge.status()["confirmed_mask"] == 0b001000   # only room A keeps everything
    fake.press("RESTORE")                                   # normal state
    run(8.0)                                                # staged restoration: >5 s stable, 1 load/s
    assert bridge.status()["confirmed_mask"] == 0b011000


def test_reset_re_handshakes_and_clears_rooms(rig):
    fake, bridge, run, _ = rig
    fake.press("START_SESSION", "C")
    run(0.3)
    fake.press("RESET_SESSION")
    run(1.5)
    assert demo().snapshot()["scanned_classroom_ids"] == []
    assert bridge.status()["link"] == "CONNECTED" and bridge.status()["confirmed_mask"] == 0
    assert [m["type"] for m in fake.sent].count("sync") >= 2


def test_reader_fault_is_visible_and_end_event_unscans(rig):
    fake, bridge, run, _ = rig
    fake._status("reader_fault")
    fake.press("START_SESSION", "A")
    fake.press("END_SESSION", "A")
    run(0.3)
    assert bridge.status()["board_a"]["reader_ok"] is False
    assert "reader_fault" in bridge.status()["recent_status"]
    assert demo().snapshot()["scanned_classroom_ids"] == []


def test_board_b_reboot_forces_a_fresh_radio_sync(rig):
    fake, bridge, run, _ = rig
    before = [m["type"] for m in fake.sent].count("radio_sync")
    fake.b_boot += 1
    fake._hello()  # A reports B's new boot
    run(0.3)
    assert [m["type"] for m in fake.sent].count("radio_sync") == before + 1
    assert bridge.status()["board_b"]["boot"] == fake.b_boot and bridge.status()["board_b"]["radio_ready"]


def test_campus_snapshot_reports_the_physical_link(rig):
    fake, bridge, run, _ = rig
    fake.press("START_SESSION", "A")
    run(0.3)
    snap = TestClient(APP).get("/api/v1/snapshot").json()
    assert snap["hardware_link"] == "CONNECTED" and snap["indicator_confirmed_mask"] == 8


def test_invalid_events_are_rejected_not_applied(rig):
    fake, bridge, run, _ = rig
    fake._emit("event", event=99, action="START_SESSION", room="Z")
    run(0.2)
    assert demo().snapshot()["scanned_classroom_ids"] == []
    assert any(m["type"] == "event_ack" and m["event"] == 99 and m["accepted"] is False for m in fake.sent)
