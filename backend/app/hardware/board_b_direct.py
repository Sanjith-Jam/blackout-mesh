"""Board B on USB with no board A: a software stand-in for board A's side of contract v2.

The gateway bridge speaks board A's USB JSON protocol. This transport answers that protocol itself
(hello, sync, ping) and turns `radio_sync` / `set_loads` into board B radio frames sent as
"F <hex>" lines over B's USB bench interface. Only B's own ACK becomes a CONFIRMED `radio_state`,
so the website still shows nothing as confirmed that board B did not report. There is no card
reader and no buttons in this mode; the website's controls drive the LEDs.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
from radio_protocol import KINDS, Packet  # noqa: E402

ACK_TIMEOUT_S = 1.0
ONLINE_S = 1.5
STAND_IN_BOOT = 1


class BoardBDirectTransport:
    def __init__(self, port, baud=115200, clock=time.monotonic, serial_port=None):
        if serial_port is None:
            import serial  # pyserial
            serial_port = serial.Serial(port, baud, timeout=0, write_timeout=0.2)
            serial_port.reset_input_buffer()
        self.ser, self.clock = serial_port, clock
        self.buffer = b""
        self.out: list[str] = []
        self.epoch = 0
        self.floor = 0
        self.ctx = None              # {"boot", "epoch", "session"} the host synced
        self.b_boot = 0
        self.b_heard = None
        self.b_seq = 0
        self.pending = None          # {"host_seq", "kind", "b_seq", "sent"}

    # ---- host side (what the bridge writes) ----
    def write_line(self, line: str):
        msg = json.loads(line)
        kind = msg.get("type")
        if kind == "hello":
            self.epoch += 1
            self.ctx = None
            self._hello()
        elif kind == "sync":
            if msg["session"] <= self.floor:
                self._status("sync_rejected")
                return
            self.ctx = {k: msg[k] for k in ("boot", "epoch", "session")}
            self.floor = msg["session"]
            self.pending = None
            self._status("host_synced")
        elif not self.ctx or any(msg.get(k) != v for k, v in self.ctx.items()):
            self._status("stale_context")
        elif kind == "ping":
            self._status("pong")
        elif kind in ("radio_sync", "set_loads") and msg.get("target") == self.b_boot:
            self.b_seq += 1
            radio_kind = KINDS["SYNC"] if kind == "radio_sync" else KINDS["SET_LOADS"]
            mask = 0 if kind == "radio_sync" else msg["mask"]
            self._to_b(Packet(radio_kind, self.ctx["session"], self.b_seq, self.b_boot, mask=mask))
            self.pending = {"host_seq": msg["seq"], "kind": kind, "b_seq": self.b_seq, "sent": self.clock()}
            self._emit("queued", seq=msg["seq"])

    def read_lines(self):
        self._poll_b()
        if self.pending and self.clock() - self.pending["sent"] > ACK_TIMEOUT_S:
            self._radio_state(self.pending["host_seq"], result=3, confirmed=False, mask=0)
            self.pending = None
        out, self.out = self.out, []
        return out

    # ---- board B side ----
    def _to_b(self, packet):
        self.ser.write(("F " + packet.encode().hex() + "\n").encode("ascii"))

    def _poll_b(self):
        self.buffer += self.ser.read(4096)
        while b"\n" in self.buffer:
            raw, self.buffer = self.buffer.split(b"\n", 1)
            line = raw.decode("ascii", "replace").strip()
            if line.startswith("F ") and len(line) == 54:
                try:
                    self._from_b(Packet.decode(bytes.fromhex(line[2:])))
                except ValueError:
                    pass
        if len(self.buffer) > 4096:
            self.buffer = b""
        if self.b_heard is not None and self.clock() - self.b_heard > ONLINE_S:
            self.b_heard = None
            self._hello()  # tell the bridge B went quiet

    def _from_b(self, p):
        first = self.b_heard is None
        self.b_heard = self.clock()
        if p.boot != self.b_boot:  # first contact or B rebooted: report the new boot so the bridge re-binds
            self.b_boot, self.pending = p.boot, None
            self._hello()
        elif first:
            self._hello()
        if p.kind == KINDS["ACK"] and self.pending and p.ack == self.pending["b_seq"]:
            pending, self.pending = self.pending, None
            if p.status != 0:
                self._radio_state(pending["host_seq"], result=4, confirmed=False, mask=p.mask & 0x38)
            elif pending["kind"] == "radio_sync":
                self._radio_state(pending["host_seq"], result=2, confirmed=False, mask=p.mask & 0x38)
            else:
                self._radio_state(pending["host_seq"], result=1, confirmed=True, mask=p.mask & 0x38)

    # ---- messages to the bridge ----
    def _emit(self, kind, **fields):
        ctx = self.ctx or {"boot": STAND_IN_BOOT, "epoch": self.epoch, "session": 0}
        self.out.append(json.dumps({"v": 2, "type": kind, **ctx, "ms": int(self.clock() * 1000) & 0xFFFFFFFF, **fields}))

    def _status(self, code):
        self._emit("status", code=code)

    def _radio_state(self, host_seq, result, confirmed, mask):
        if self.ctx:
            self._emit("radio_state", target=self.b_boot, ack_seq=host_seq, applied_classroom_mask=mask,
                       confirmed=confirmed, result=result)

    def _hello(self):
        if self.epoch == 0:
            return  # the bridge has not said hello yet
        online = self.b_heard is not None
        self.out.append(json.dumps({"v": 2, "type": "hello", "boot": STAND_IN_BOOT, "epoch": self.epoch,
                                    "session": 0, "ms": 0, "minimum_session": self.floor,
                                    "target": self.b_boot if online else 0, "reader_ok": None,
                                    "radio_configured": True, "radio_online": online, "mode": "INPUT_GATEWAY"}))
