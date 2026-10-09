"""Host side of the link to board B: sync, one command in flight, retries, ACK validation.

Works over any line transport: board B's own USB port (bench), board A's USB port once A
bridges "F <hex>" lines to ESP-NOW, or the in-process SimBoardB used by tests.
Only a validated ACK (current session + B's boot + cmd id + projected mask) confirms LEDs.
"""
import queue
import struct
import threading
import time

import protocol as p

RETRY_S, MAX_RETRIES, TIMEOUT_S = 0.2, 2, 0.6
HEARTBEAT_S, STALE_S, OFFLINE_S = 1.0, 3.0, 10.0
RESEND_FAILED_S = 1.0


class SerialTransport:
    def __init__(self, port, baud=115200):
        import serial  # pyserial
        self.ser = serial.Serial(port, baud, timeout=0.05)
        self.lines = queue.Queue()
        self.log = []
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        buf = b""
        while True:
            try:
                chunk = self.ser.read(256)
            except Exception as exc:  # unplugged
                self.lines.put(f"# transport error: {exc}")
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                self.lines.put(line.decode("ascii", "replace").strip())

    def send_line(self, line):
        self.ser.write((line + "\n").encode("ascii"))

    def poll_lines(self):
        out = []
        while not self.lines.empty():
            out.append(self.lines.get())
        return out


class BLink:
    def __init__(self, transport, session, clock=time.monotonic):
        self.t = transport
        self.clock = clock
        self.session = session
        self.seq = 0
        self.state_rev = 0
        self.boot = None          # B's boot id as last seen
        self.synced = False
        self.last_seen = None     # last valid frame from B
        self.last_hb_sent = -1e9
        self.desired = 0          # full commanded mask the controller wants
        self.acked = None         # commanded mask confirmed by a validated ACK
        self.applied = None       # classroom bits B reported applying
        self.inflight = None      # dict(cmd_id, mask, rev, first, last, tries)
        self.last_failed = None
        self.reboots = 0
        self.notes = []           # human-readable events for the controller log

    # ---- public ----
    def set_desired(self, mask):
        if not 0 <= mask <= p.FULL_MASK:
            raise ValueError("mask outside the nine-load catalog")
        self.desired = mask

    def new_session(self, session):
        """Reset: fresh session, nothing confirmed until B re-syncs."""
        self.session = session
        self.synced = False
        self.inflight = None
        self.acked = None
        self.state_rev = 0
        if self.boot is not None:
            self._send(p.sync_frame(self.session, self.boot, self._next_seq()))

    def link_state(self):
        if self.last_seen is None:
            return "NO CONTACT"
        age = self.clock() - self.last_seen
        if age > OFFLINE_S:
            return "OFFLINE"
        if age > STALE_S:
            return "STALE"
        return "ONLINE" if self.synced else "UNSYNCED"

    def confirmed(self):
        return self.link_state() == "ONLINE" and self.inflight is None and self.acked == self.desired

    def tick(self):
        """Process input; returns non-frame lines (events from board A, logs)."""
        other = []
        for line in self.t.poll_lines():
            raw = p.from_line(line)
            if raw is None:
                if line:
                    other.append(line)
                continue
            try:
                frame = p.decode(raw)
            except ValueError as exc:
                self.notes.append(f"dropped bad frame from B ({exc})")
                continue
            if frame.node == p.NODE_B:
                self._on_frame(frame)
        self._drive()
        return other

    # ---- internals ----
    def _next_seq(self):
        self.seq += 1
        return self.seq

    def _send(self, frame):
        self.t.send_line(p.to_line(frame))

    def _on_frame(self, f):
        now = self.clock()
        if f.boot != self.boot:
            if self.boot is not None:
                self.reboots += 1
                self.notes.append("board B rebooted: outputs restarted OFF, resyncing")
            self.boot = f.boot
            self.synced = False
            self.inflight = None
            self.acked = None
            self.applied = None
        self.last_seen = now

        if f.type == p.HELLO:
            _, _, state, mask = f.hello()
            self.applied = mask
            if f.session == self.session and state in (2, 3):
                if not self.synced:
                    self.notes.append(f"board B synced (session {self.session})")
                self.synced = True
            else:
                self.synced = False
                self._send(p.sync_frame(self.session, self.boot, self._next_seq()))
        elif f.type == p.HEARTBEAT:
            _, mask, _ = f.heartbeat()
            self.applied = mask
            if f.session != self.session:
                self.synced = False
                self._send(p.sync_frame(self.session, self.boot, self._next_seq()))
        elif f.type == p.ACK:
            self._on_ack(f)

    def _on_ack(self, f):
        cmd_id, applied, status, _ = f.ack()
        inf = self.inflight
        if inf is None or cmd_id != inf["cmd_id"] or f.session != self.session:
            return  # late or foreign ACK: never mutates current state
        self.applied = applied
        if status in (p.APPLIED, p.DUP_REPLAY):
            if applied == p.project(inf["mask"]):
                self.acked = inf["mask"]
                inf["done"] = True
            else:
                self.notes.append(f"projection mismatch: sent 0x{inf['mask']:03x}, B applied 0x{applied:03x}")
                self.acked = None
                inf["done"] = True
        else:
            self.notes.append(f"B rejected cmd {cmd_id}: {p.STATUS_NAMES[status]}")
            inf["done"] = True
            if status in (p.REJ_SESSION, p.REJ_BOOT):
                self.synced = False
                self._send(p.sync_frame(self.session, self.boot, self._next_seq()))
        if inf.get("done"):
            self.inflight = None

    def _drive(self):
        now = self.clock()
        if self.boot is None:
            return
        state = self.link_state()
        if self.synced and now - self.last_hb_sent >= HEARTBEAT_S:
            self.last_hb_sent = now
            self._send(p.host_heartbeat_frame(self.session, self.boot, self._next_seq(), int(now * 1000)))

        inf = self.inflight
        if inf is not None:
            if now - inf["first"] >= TIMEOUT_S:
                self.notes.append(f"no ACK for cmd {inf['cmd_id']} (mask 0x{inf['mask']:03x}): UNCONFIRMED")
                self.last_failed = now
                self.inflight = None
            elif now - inf["last"] >= RETRY_S and inf["tries"] <= MAX_RETRIES:
                inf["tries"] += 1
                inf["last"] = now
                self._send(inf["frame"])  # retry reuses the same command identity
            return

        if not self.synced or state in ("STALE", "OFFLINE"):
            return
        if self.acked == self.desired:
            return
        if self.last_failed is not None and now - self.last_failed < RESEND_FAILED_S:
            return
        cmd_id = self._next_seq()
        self.state_rev += 1
        frame = p.set_mask_frame(self.session, self.boot, cmd_id, self.state_rev, self.desired)
        self.inflight = dict(cmd_id=cmd_id, mask=self.desired, rev=self.state_rev,
                             first=now, last=now, tries=1, frame=frame)
        self._send(frame)


class SimBoardB:
    """In-process stand-in for board B firmware (same validation rules), for tests and --sim."""

    def __init__(self, boot=0x5A5A0001):
        self.boot = boot
        self.session = 0
        self.last_rev = 0
        self.applied = 0
        self.seq = 0
        self.cached = None  # (cmd_id, frame)
        self.out = []
        self.online = True
        self.drop_next_acks = 0
        self.hello()

    def reboot(self, boot):
        self.__init__(boot)

    def _frame(self, ftype, payload):
        self.seq += 1
        return p.encode(p.NODE_B, ftype, self.session, self.boot, self.seq, payload)

    def _state(self):
        return 2 if self.session else 1

    def hello(self):
        self._emit(self._frame(p.HELLO, struct.pack("<HBBHH", 0x0200, 2, self._state(), self.applied, 0)))

    def heartbeat(self):
        self._emit(self._frame(p.HEARTBEAT, struct.pack("<IHBB", 0, self.applied, self._state(), 0)))

    def _emit(self, frame):
        if self.online:
            self.out.append(p.to_line(frame))

    def _ack(self, cmd_id, status, cache):
        frame = self._frame(p.ACK, struct.pack("<IHBB", cmd_id, self.applied, status, self._state()))
        if cache:
            self.cached = (cmd_id, frame)
        if self.drop_next_acks:
            self.drop_next_acks -= 1
            return
        self._emit(frame)

    # transport interface (host side)
    def send_line(self, line):
        if not self.online:
            return
        raw = p.from_line(line)
        try:
            f = p.decode(raw)
        except (ValueError, TypeError):
            return
        if f.type == p.SYNC:
            expected = struct.unpack("<II", f.payload)[0]
            if expected == self.boot and f.session and f.session >= self.session:
                if f.session != self.session:
                    self.last_rev, self.cached = 0, None
                self.session = f.session
                self.hello()
            return
        if not self.session or f.session != self.session:
            if f.type == p.SET_MASK:
                self._ack(f.seq, p.REJ_SESSION, False)
            return
        if f.boot != self.boot:
            if f.type == p.SET_MASK:
                self._ack(f.seq, p.REJ_BOOT, False)
            return
        if f.type == p.SET_MASK:
            rev, mask = f.set_mask()
            if self.cached and self.cached[0] == f.seq:
                cmd_id, frame = self.cached
                self._ack(cmd_id, p.DUP_REPLAY, False)
                return
            if mask & ~p.FULL_MASK:
                self._ack(f.seq, p.REJ_BAD, False)
                return
            if rev < self.last_rev:
                self._ack(f.seq, p.REJ_STALE_REV, False)
                return
            self.last_rev = rev
            self.applied = p.project(mask)
            self._ack(f.seq, p.APPLIED, True)

    def poll_lines(self):
        out, self.out = self.out, []
        return out
