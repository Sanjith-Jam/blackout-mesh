"""USB bench check for board B on contract v2, without board A or radio.

    python hardware/tools/check_board_b.py COM3

Board B accepts radio frames as "F <52 hex>" lines on USB and answers the same way. This script
binds a session, lights each fixture (A, B, C, A+B, all, off) for a second so you can watch the
LEDs, and checks duplicate, conflicting, stale and wrong-session commands. Needs pyserial.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from radio_protocol import KINDS, Packet  # noqa: E402

import serial  # noqa: E402

SESSION = int(time.time()) & 0x7FFFFFFF


def frames(port, seconds=0.6):
    end, out = time.time() + seconds, []
    while time.time() < end:
        line = port.readline().decode("ascii", "replace").strip()
        if line.startswith("F ") and len(line) == 54:
            try:
                out.append(Packet.decode(bytes.fromhex(line[2:])))
            except ValueError:
                pass
        elif line:
            print("   ", line)
    return out


def send(port, packet):
    port.write(("F " + packet.encode().hex() + "\n").encode())
    acks = [p for p in frames(port) if p.kind == KINDS["ACK"] and p.ack == packet.seq]
    return acks[-1] if acks else None


def main(name):
    results = []
    with serial.Serial(name, 115200, timeout=0.1) as port:
        port.dtr = False
        port.rts = True; time.sleep(0.15); port.rts = False  # reset B: boots with outputs OFF
        seen = frames(port, 3.0)
        if not seen:
            raise SystemExit("No frames from board B: check the port and that the new firmware is flashed.")
        boot = seen[-1].boot
        print(f"board B boot {boot}, reports mask {seen[-1].mask:#05x} (expect 0x000 after boot)")

        def check(title, ok):
            results.append(ok)
            print(f"{'PASS' if ok else 'FAIL'}  {title}")

        ack = send(port, Packet(KINDS["SYNC"], SESSION, 1, boot))
        check("SYNC binds the session", ack is not None and ack.status == 0 and ack.session == SESSION)
        seq = 1
        for label, mask in (("room A", 8), ("room B", 16), ("room C", 32), ("A + B", 24), ("all, from 511", 511), ("all off", 0)):
            seq += 1
            ack = send(port, Packet(KINDS["SET_LOADS"], SESSION, seq, boot, mask=mask))
            check(f"{label}: LEDs show {mask & 0x38:#05x}", ack is not None and ack.status == 0 and ack.mask == mask & 0x38)
            time.sleep(1.0)
        dup = send(port, Packet(KINDS["SET_LOADS"], SESSION, seq, boot, mask=0))
        check("duplicate command re-ACKs without change", dup is not None and dup.status == 0)
        conflict = send(port, Packet(KINDS["SET_LOADS"], SESSION, seq, boot, mask=8))
        check("same sequence, different mask is rejected", conflict is not None and conflict.status == 1)
        old = send(port, Packet(KINDS["SET_LOADS"], SESSION, seq - 1, boot, mask=8))
        check("older sequence is rejected", old is not None and old.status == 1)
        wrong = send(port, Packet(KINDS["SET_LOADS"], SESSION + 1, seq + 1, boot, mask=8))
        check("wrong session is rejected", wrong is not None and wrong.status == 1)
        down = send(port, Packet(KINDS["SYNC"], SESSION - 1, seq + 2, boot))
        check("older session cannot re-bind", down is not None and down.status == 1)
    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "COM3"))
