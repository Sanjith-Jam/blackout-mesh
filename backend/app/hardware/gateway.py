"""Laptop side of board A's USB contract v2 (contracts/serial_protocol.md).

Board A reports card taps and buttons as JSON `event` lines and forwards radio commands to
board B. This bridge:
  * performs the HELLO -> SYNC -> ping handshake and keeps the lease alive (ping every 500 ms);
  * turns each event into a site command through `on_event` and answers with `event_ack`;
  * binds board B with `radio_sync`, then sends `set_loads` whenever the desired LED mask changes;
  * treats only `radio_state` with result 1 (CONFIRMED) as proof of what B's LEDs show.
Transport is any object with `write_line(str)` and `read_lines() -> list[str]`, so tests can use a fake A.
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque

RADIO_RESULTS = {0: "NONE", 1: "CONFIRMED", 2: "SYNCED", 3: "TIMEOUT", 4: "REJECTED", 5: "BAD_ACK", 6: "REBOOT", 7: "STALE"}
ACTIONS = ("START_SESSION", "END_SESSION", "SIMULATE_SHORTAGE", "RESTORE", "RESET_SESSION")
PING_S = 0.5
RESYNC_S = 1.0
QUIET_STATUSES = {"pong", "event_accepted", "host_synced"}


def _u32(value, minimum=1):
    return type(value) is int and minimum <= value <= 0xFFFFFFFF


class GatewayBridge:
    def __init__(self, transport, on_event, desired_mask, clock=time.monotonic, session_seed=None):
        self.t = transport
        self.on_event = on_event          # (action, room|None) -> bool accepted
        self.desired_mask = desired_mask  # () -> int full logical mask for B
        self.clock = clock
        self.session_seed = session_seed or (lambda: int(time.time()))
        self.lock = threading.RLock()
        self.context = None               # {"boot", "epoch", "session"} once synced
        self.synced = False
        self.reader_ok = None
        self.radio_configured = None
        self.radio_online = False
        self.target = 0                   # B boot as reported by A
        self.radio_ready = False
        self.seq = 0
        self.inflight = None              # {"seq", "kind", "mask", "sent"}
        self.commanded_mask = None
        self.confirmed_mask = None        # B's applied classroom mask from a CONFIRMED radio_state only
        self.last_result = None
        self.last_ping = -1e9
        self.last_hello_sent = -1e9
        self.last_rx = None
        self.events = deque(maxlen=20)
        self.statuses = deque(maxlen=20)

    # ---- outgoing ----
    def _send(self, kind, **fields):
        self.t.write_line(json.dumps({"v": 2, "type": kind, **fields}, separators=(",", ":")))

    def _send_ctx(self, kind, **fields):
        self._send(kind, **self.context, **fields)

    def _drop_context(self):
        self.context, self.synced, self.radio_ready, self.inflight = None, False, False, None
        self.last_hello_sent = -1e9  # re-handshake on the next step

    def hello(self):
        self.context, self.synced, self.radio_ready, self.inflight = None, False, False, None
        self.last_hello_sent = self.clock()
        self._send("hello")

    # ---- main step: call often (the thread does this every ~20 ms) ----
    def step(self):
        with self.lock:
            now = self.clock()
            if self.context is None and now - self.last_hello_sent >= RESYNC_S:
                self.hello()
            for line in self.t.read_lines():
                self._receive(line, now)
            if self.synced and self.context:
                if now - self.last_ping >= PING_S:
                    self.last_ping = now
                    self._send_ctx("ping")
                self._drive_radio(now)

    def _drive_radio(self, now):
        if self.inflight and now - self.inflight["sent"] > 1.5:
            self.inflight = None  # A reports TIMEOUT itself; never wait forever
            self.radio_ready = False
        if self.inflight or not (self.radio_online and self.target):
            return
        if not self.radio_ready:
            self.seq += 1
            self.inflight = {"seq": self.seq, "kind": "radio_sync", "mask": 0, "sent": now}
            self._send_ctx("radio_sync", seq=self.seq, target=self.target, mask=0)
            return
        desired = int(self.desired_mask()) & 0x01FF
        if desired != self.commanded_mask or self.confirmed_mask is None:
            self.seq += 1
            self.inflight = {"seq": self.seq, "kind": "set_loads", "mask": desired, "sent": now}
            self.commanded_mask = desired
            self._send_ctx("set_loads", seq=self.seq, target=self.target, mask=desired)

    # ---- incoming ----
    def _receive(self, line, now):
        try:
            msg = json.loads(line)
        except (ValueError, TypeError):
            return
        if not isinstance(msg, dict) or msg.get("v") != 2:
            return
        self.last_rx = now
        kind = msg.get("type")
        if kind == "hello":
            self._on_hello(msg)
            return
        if not self.context or any(msg.get(k) != v for k, v in self.context.items()):
            return  # other context: ignore
        if kind == "status":
            self._on_status(msg.get("code", ""))
        elif kind == "event":
            self._on_event(msg)
        elif kind == "radio_state":
            self._on_radio_state(msg)
        elif kind == "queued":
            pass  # acceptance into A's bridge only; not delivery

    def _on_hello(self, msg):
        if not (_u32(msg.get("boot")) and _u32(msg.get("epoch")) and _u32(msg.get("minimum_session"), 0)):
            return
        self.reader_ok = msg.get("reader_ok")
        self.radio_configured = msg.get("radio_configured")
        online = bool(msg.get("radio_online"))
        target = msg.get("target") if _u32(msg.get("target"), 0) else 0
        if target != self.target:
            self.radio_ready = False
        self.radio_online, self.target = online, target
        identity = (msg["boot"], msg["epoch"])
        if self.context and identity == (self.context["boot"], self.context["epoch"]):
            return  # periodic hello for the current context: just refreshed the radio/reader view
        if msg.get("mode") == "LOCAL_ENROLLMENT":
            self.statuses.append("board A is in enrollment mode: flash normal firmware")
            return
        session = max(int(self.session_seed()), msg["minimum_session"] + 1, 1)
        self.context = {"boot": identity[0], "epoch": identity[1], "session": session}
        self.synced, self.radio_ready, self.inflight, self.seq = False, False, None, 0
        self.commanded_mask = self.confirmed_mask = None
        self._send_ctx("sync", selected=None)

    def _on_status(self, code):
        if code == "host_synced":
            self.synced = True
        elif code in ("reader_fault", "fallback_room_a_reader_fault", "fallback_room_b_reader_fault",
                      "fallback_room_c_reader_fault"):
            self.reader_ok = False
        elif code in ("reader_recovered", "reader_initialized_unverified"):
            self.reader_ok = True
        elif code in ("reset_requires_sync", "host_stale_or_event_timeout", "event_rejected_requires_sync",
                      "event_backpressure", "sync_rejected", "stale_context"):
            self._drop_context()  # next step() starts a fresh handshake
        elif code in ("radio_timeout_unconfirmed", "radio_stale", "radio_command_rejected"):
            self.radio_ready, self.inflight = False, None
        if code not in QUIET_STATUSES:
            self.statuses.append(code)

    def _on_event(self, msg):
        action, room, event = msg.get("action"), msg.get("room"), msg.get("event")
        valid = _u32(event) and action in ACTIONS and (
            (action in ("START_SESSION", "END_SESSION") and room in ("A", "B", "C")) or
            (action not in ("START_SESSION", "END_SESSION") and room is None))
        accepted = False
        if valid:
            try:
                accepted = bool(self.on_event(action, room))
            except Exception:
                accepted = False
        self.events.append({"event": event, "action": action, "room": room, "accepted": accepted})
        if action == "RESET_SESSION":
            self._drop_context()  # A already invalidated this context; re-handshake on next step
            return
        if _u32(event):
            self._send_ctx("event_ack", event=event, accepted=accepted)

    def _on_radio_state(self, msg):
        result = RADIO_RESULTS.get(msg.get("result"), "NONE")
        self.last_result = result
        inflight = self.inflight
        if result == "SYNCED" and inflight and inflight["kind"] == "radio_sync" and msg.get("ack_seq") == inflight["seq"]:
            self.radio_ready, self.inflight = True, None
            self.confirmed_mask = msg.get("applied_classroom_mask")  # SYNC ACK reports B's actual state
            self.commanded_mask = None  # force a fresh SET after binding
        elif result == "CONFIRMED" and msg.get("confirmed") is True and inflight and msg.get("ack_seq") == inflight["seq"]:
            self.confirmed_mask = msg.get("applied_classroom_mask")
            self.inflight = None
        elif result in ("TIMEOUT", "REJECTED", "BAD_ACK", "REBOOT", "STALE"):
            self.radio_ready, self.inflight = False, None
            if result == "REBOOT":
                self.confirmed_mask = None

    # ---- read-only view for the API/UI ----
    def status(self) -> dict:
        with self.lock:
            now = self.clock()
            if self.context is None:
                link = "CONNECTING"
            elif not self.synced:
                link = "SYNCING"
            elif self.last_rx is not None and now - self.last_rx > 2.0:
                link = "STALE"
            else:
                link = "CONNECTED"
            return {"link": link, "board_a": {"boot": self.context and self.context["boot"], "reader_ok": self.reader_ok,
                                              "radio_configured": self.radio_configured},
                    "board_b": {"online": self.radio_online, "boot": self.target or None, "radio_ready": self.radio_ready},
                    "session": self.context and self.context["session"],
                    "commanded_mask": self.commanded_mask, "confirmed_mask": self.confirmed_mask,
                    "led_confirmed": self.confirmed_mask is not None and self.inflight is None
                                     and self.commanded_mask is not None
                                     and self.confirmed_mask == (self.commanded_mask & 0x38),
                    "last_radio_result": self.last_result, "recent_events": list(self.events)[-5:],
                    "recent_status": list(self.statuses)[-5:]}


class SerialTransport:
    def __init__(self, port, baud=115200):
        import serial  # pyserial
        self.ser = serial.Serial(port, baud, timeout=0, write_timeout=0.2)
        self.ser.reset_input_buffer()
        self.buffer = b""

    def write_line(self, line: str):
        self.ser.write((line + "\n").encode("ascii"))

    def read_lines(self):
        self.buffer += self.ser.read(4096)
        lines = []
        while b"\n" in self.buffer:
            raw, self.buffer = self.buffer.split(b"\n", 1)
            if len(raw) <= 512:
                lines.append(raw.decode("ascii", "replace").strip())
        if len(self.buffer) > 2048:
            self.buffer = b""
        return lines


class GatewayThread:
    """Runs a bridge step loop in a daemon thread until stopped."""

    def __init__(self, bridge, period_s=0.02):
        self.bridge, self.period_s = bridge, period_s
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name="gateway", daemon=True)
        self.error = None

    def _run(self):
        while not self._stop.is_set():
            try:
                self.bridge.step()
            except Exception as exc:  # unplugged cable etc.: surface, keep trying
                self.error = f"{type(exc).__name__}: {exc}"
                time.sleep(1.0)
            self._stop.wait(self.period_s)

    def start(self):
        self.thread.start()

    def stop(self):
        self._stop.set()
        self.thread.join(timeout=2)
