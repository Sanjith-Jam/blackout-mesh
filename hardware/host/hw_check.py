"""Scripted check against the real board B over USB: python hw_check.py COM3

Runs the bench scenarios through the real controller + link, then injects stale,
wrong-boot, malformed and duplicate frames and prints board B's verdicts.
"""
import sys
import time

import protocol as p
from controller import Controller, RulesActivity
from link import BLink, SerialTransport

port = sys.argv[1] if len(sys.argv) > 1 else "COM3"
tr = SerialTransport(port)
link = BLink(tr, session=int(time.time()) & 0x7FFFFFFF)
ctl = Controller(link, RulesActivity())
board_log = []


def run(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        for line in link.tick():
            board_log.append(line)
        ctl.recompute()
        for n in link.notes:
            print(f"    note: {n}")
        link.notes.clear()
        time.sleep(0.02)


def step(title, *events, wait=1.0, expect=None):
    for e in events:
        ctl.handle(*e)
    t0 = time.monotonic()
    run(wait)
    ok = link.confirmed() and (expect is None or link.applied == expect)
    print(f"{'PASS' if ok else 'FAIL'}  {title}: commanded 0x{link.desired:03x}, "
          f"B ACK applied 0x{(link.applied or 0):03x}, link {link.link_state()}")
    return ok


results = []
print("waiting for board B HELLO and sync ...")
tr.ser.dtr = False
tr.ser.rts = True; time.sleep(0.15); tr.ser.rts = False  # reset B so the run starts from boot
run(4.0)
print(f"board B boot id 0x{link.boot:08x}, link {link.link_state()}")
results.append(step("reset, then shortage -> all OFF", ("RESET",), ("SHORTAGE",), expect=0))
results.append(step("scan A, shortage fits A -> only A", ("SCAN", "A"), expect=8))
results.append(step("reset; scan B under shortage -> only B", ("RESET",), ("SHORTAGE",), ("SCAN", "B"), wait=2.0, expect=16))
results.append(step("reset; scan C under shortage -> only C", ("RESET",), ("SHORTAGE",), ("SCAN", "C"), wait=2.0, expect=32))
results.append(step("reset; A+B with normal supply -> A+B", ("RESET",), ("SCAN", "A"), ("SCAN", "B"), wait=2.0, expect=24))
results.append(step("A+B, shortage fits one -> A (bench rank)", ("SHORTAGE",), expect=8))
results.append(step("END selected A -> B reallocated", ("SELECT", "A"), ("END",), expect=16))
results.append(step("unknown card -> no change", ("UNKNOWN_CARD",), expect=16))
results.append(step("register A, C; restore (staged) -> all three", ("SCAN", "A"), ("SCAN", "C"), ("RESTORE",), wait=4.0, expect=56))

print("\nfault injection straight at board B:")
sess, boot = link.session, link.boot
cases = [
    ("older session", p.set_mask_frame(sess - 1, boot, 900001, 9999, 0), p.REJ_SESSION),
    ("wrong boot id", p.set_mask_frame(sess, boot ^ 1, 900002, 9999, 0), p.REJ_BOOT),
    ("stale state_rev", p.set_mask_frame(sess, boot, 900003, 0, 0), p.REJ_STALE_REV),
    ("mask outside catalog", p.set_mask_frame(sess, boot, 900004, 9999, 0x0200), p.REJ_BAD),
]
for name, frame, want in cases:
    board_log.clear()
    tr.send_line(p.to_line(frame))
    time.sleep(0.3)
    for line in tr.poll_lines():
        raw = p.from_line(line)
        if raw:
            f = p.decode(raw)
            if f.type == p.ACK:
                cmd, applied, status, _ = f.ack()
                ok = status == want and applied == 56
                results.append(ok)
                print(f"{'PASS' if ok else 'FAIL'}  {name}: B said {p.STATUS_NAMES[status]}, LEDs still 0x{applied:03x}")

# duplicate: replay the last command the controller sent
last = link.seq
tr.send_line(p.to_line(p.set_mask_frame(sess, boot, 900010, 10000, 8)))
time.sleep(0.3)
tr.poll_lines()
tr.send_line(p.to_line(p.set_mask_frame(sess, boot, 900010, 10000, 8)))
time.sleep(0.3)
for line in tr.poll_lines():
    raw = p.from_line(line)
    if raw and p.decode(raw).type == p.ACK:
        cmd, applied, status, _ = p.decode(raw).ack()
        ok = status == p.DUP_REPLAY and applied == 8
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  duplicate cmd id: B said {p.STATUS_NAMES[status]}, applied 0x{applied:03x}")

corrupt = bytearray(p.set_mask_frame(sess, boot, 900020, 10001, 56)); corrupt[21] ^= 0xFF
tr.send_line(p.to_line(bytes(corrupt)))
time.sleep(0.3)
lines = tr.poll_lines()
dropped = any("drop: bad" in l for l in lines) and not any(
    (r := p.from_line(l)) and p.decode(r).type == p.ACK for l in lines)
results.append(dropped)
print(f"{'PASS' if dropped else 'FAIL'}  corrupted CRC: dropped without ACK or output change")

print(f"\n{sum(results)}/{len(results)} checks passed")
