"""Blackout Mesh laptop bench controller (Person B).

Keeps three separate values per room: registered (card session), activity (model or
UNKNOWN in rules mode) and served (allocator choice confirmed by board B's ACK).

Run:
  python controller.py --sim                 # no hardware, simulated board B
  python controller.py --port COM3           # board B directly over USB (bench)
  python controller.py --port COMx           # board A's port once it bridges to B by radio
Keys: a / b / c = scan card, x = unknown card, sel a|b|c, end, short, restore,
      reset, fault / ok (reader), q = quit.  Board A can send the same as "EV <id> ..." lines.
"""
import argparse
import json
import os
import sys
import threading
import time

import allocator as al
import protocol as p
from link import BLink, SerialTransport, SimBoardB

RESTORE_STEP_S = 1.0


class RulesActivity:
    mode = "BENCH / RULES MODE (model pending)"

    def get(self):
        return {r: "UNKNOWN" for r in al.ROOMS}


class LiveModelActivity:
    """Reads the classifier's latest prediction file: {"model_version": ..., "rooms": {"A": "ACTIVE", ...}}."""

    def __init__(self, path):
        self.path = path
        self.mode = f"LIVE MODEL MODE ({path})"

    def get(self):
        try:
            with open(self.path) as fh:
                data = json.load(fh)
            self.mode = f"LIVE MODEL MODE (version {data.get('model_version', '?')})"
            rooms = data.get("rooms", {})
            return {r: rooms.get(r, "UNKNOWN") if rooms.get(r) in al.ACTIVITY_RANK else "UNKNOWN" for r in al.ROOMS}
        except (OSError, ValueError):
            self.mode = "LIVE MODEL MODE: prediction file unreadable, using UNKNOWN"
            return {r: "UNKNOWN" for r in al.ROOMS}


class Controller:
    def __init__(self, link, activity, clock=time.monotonic):
        self.link = link
        self.activity = activity
        self.clock = clock
        self.log = []
        self.seen_events = set()
        self._reset_state()

    def _reset_state(self):
        self.registered = []        # registration order
        self.selected = None
        self.shortage = False
        self.reader_fault = False
        self.staged = None          # rooms currently allowed during staged restore
        self.last_stage = 0.0
        self.alloc = al.allocate([], {}, al.NORMAL_BUDGET_KW)

    def say(self, msg):
        self.log.append(msg)
        print(f"  > {msg}")

    # ---- inputs ----
    def handle(self, kind, arg=None, event_id=None):
        if event_id is not None:
            if event_id in self.seen_events:
                return  # duplicate event from board A
            self.seen_events.add(event_id)
        kind = kind.upper()
        if kind == "SCAN":
            room = (arg or "").upper()
            if self.reader_fault:
                self.say("reader fault: new registrations blocked")
            elif room not in al.ROOMS:
                self.say(f"unknown card rejected; registrations unchanged")
            else:
                if room not in self.registered:
                    self.registered.append(room)
                    self.say(f"room {room} session registered")
                self.selected = room
        elif kind in ("UNKNOWN_CARD", "UNKNOWN"):
            self.say("unknown card rejected; registrations unchanged")
        elif kind == "SELECT":
            room = (arg or "").upper()
            if room in self.registered:
                self.selected = room
        elif kind == "END":
            if self.selected is None:
                self.say("END ignored: no room selected")
            else:
                room = self.selected
                self.registered.remove(room)
                self.selected = self.registered[-1] if self.registered else None
                self.say(f"room {room} session ended; power OFF requested")
        elif kind == "SHORTAGE":
            self.shortage = True
            self.staged = None
            self.say(f"supply shortage: budget {al.SHORTAGE_BUDGET_KW} kW")
        elif kind == "RESTORE":
            if self.shortage:
                self.shortage = False
                self.staged = list(self.alloc.served)
                self.last_stage = self.clock()
                self.say(f"supply restored to {al.NORMAL_BUDGET_KW} kW; staged restoration")
        elif kind == "RESET":
            self._reset_state()
            self.link.set_desired(0)
            self.link.new_session(self.link.session + 1)
            self.say(f"reset: all sessions cleared, new session {self.link.session}")
        elif kind == "READER_FAULT":
            self.reader_fault = True
            self.say("reader fault: existing registrations kept, no new ones")
        elif kind == "READER_OK":
            self.reader_fault = False
        self.recompute()

    def recompute(self):
        budget = al.SHORTAGE_BUDGET_KW if self.shortage else al.NORMAL_BUDGET_KW
        target = al.allocate(self.registered, self.activity.get(), budget)
        if self.staged is not None:
            # Shedding is immediate; restoring adds one room per step in rank order.
            self.staged = [r for r in self.staged if r in target.served]
            missing = [r for r in target.order if r in target.served and r not in self.staged]
            if missing and self.clock() - self.last_stage >= RESTORE_STEP_S:
                self.staged.append(missing[0])
                self.last_stage = self.clock()
            if not missing:
                self.staged = None
            else:
                served = tuple(r for r in al.ROOMS if r in self.staged)
                target = al.Allocation(served, target.order, target.reasons, sum(al.DEMAND_KW[r] for r in served), budget)
        self.alloc = target
        mask = 0
        for room in target.served:
            mask |= 1 << p.ROOM_BITS[room]
        self.link.set_desired(mask)

    # ---- output ----
    def status(self):
        act = self.activity.get()
        lk = self.link
        lines = [f"[{self.activity.mode}] [CLASSROOM BENCH] supply "
                 f"{'SHORTAGE ' + str(al.SHORTAGE_BUDGET_KW) if self.shortage else 'NORMAL ' + str(al.NORMAL_BUDGET_KW)} kW"
                 f"{' (restoring)' if self.staged is not None else ''}"
                 f"{'  READER FAULT' if self.reader_fault else ''}",
                 f"  board B link: {lk.link_state()}  session {lk.session}  selected: {self.selected or '-'}"]
        for room in al.ROOMS:
            bit = 1 << p.ROOM_BITS[room]
            cmd = "ON " if lk.desired & bit else "off"
            if lk.applied is None:
                led = "?"
            else:
                led = "ON" if lk.applied & bit else "off"
            lines.append(f"  room {room}: registered={'yes' if room in self.registered else 'no ':3}"
                         f"  activity={act[room]:8} commanded={cmd} LED(B ACK)={led:3}  {self.alloc.reasons.get(room, '')}")
        if lk.inflight:
            lines.append(f"  PENDING: cmd {lk.inflight['cmd_id']} mask 0x{lk.inflight['mask']:03x} awaiting ACK")
        elif lk.confirmed():
            lines.append(f"  CONFIRMED: commanded 0x{lk.desired:03x}, B applied classrooms 0x{lk.applied:03x}")
        else:
            lines.append(f"  NOT CONFIRMED: commanded 0x{lk.desired:03x}, last ACKed "
                         f"{'none' if lk.acked is None else hex(lk.acked)}")
        return "\n".join(lines)


def parse_event_line(line):
    """'EV <id> <KIND> [arg]' from board A."""
    parts = line.split()
    if len(parts) >= 3 and parts[0] == "EV":
        return parts[2], (parts[3] if len(parts) > 3 else None), parts[1]
    return None


KEYS = {"a": ("SCAN", "A"), "b": ("SCAN", "B"), "c": ("SCAN", "C"), "x": ("UNKNOWN_CARD", None),
        "end": ("END", None), "short": ("SHORTAGE", None), "restore": ("RESTORE", None),
        "reset": ("RESET", None), "fault": ("READER_FAULT", None), "ok": ("READER_OK", None)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--model-json", help="classifier prediction file; omit for BENCH / RULES MODE")
    ap.add_argument("--log", default="controller_log.jsonl")
    args = ap.parse_args()
    if not args.port and not args.sim:
        ap.error("give --port COMx or --sim")

    if args.sim:
        board = SimBoardB()
        transport = board
    else:
        transport = SerialTransport(args.port)
    link = BLink(transport, session=int(time.time()) & 0x7FFFFFFF)
    activity = LiveModelActivity(args.model_json) if args.model_json else RulesActivity()
    ctl = Controller(link, activity)
    logf = open(args.log, "a")

    keyq = []
    def keyboard():
        for line in sys.stdin:
            keyq.append(line.strip().lower())
        keyq.append("q")
    threading.Thread(target=keyboard, daemon=True).start()

    print(__doc__)
    last_status, last_print, last_sim_beat = "", 0, 0
    while True:
        for line in link.tick():
            ev = parse_event_line(line)
            if ev:
                ctl.handle(ev[0], ev[1], ev[2])
            elif not line.startswith("#"):
                pass
            logf.write(json.dumps({"t": time.time(), "rx": line}) + "\n")
        while keyq:
            k = keyq.pop(0)
            if k == "q":
                return
            if k.startswith("sel "):
                ctl.handle("SELECT", k[4:])
            elif k in KEYS:
                ctl.handle(*KEYS[k])
            elif k:
                print("  keys: a b c x | sel a | end short restore reset | fault ok | q")
        ctl.recompute()
        for note in link.notes:
            ctl.say(note)
        link.notes.clear()
        if args.sim and time.monotonic() - last_sim_beat > 1:
            last_sim_beat = time.monotonic()
            board.heartbeat()
        st = ctl.status()
        if st != last_status:
            print(st)
            logf.write(json.dumps({"t": time.time(), "status": st}) + "\n")
            logf.flush()
            last_status, last_print = st, time.monotonic()
        time.sleep(0.02)


if __name__ == "__main__":
    main()
