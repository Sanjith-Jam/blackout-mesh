"""Local enrollment only: flash esp32-a-enroll first, then tap A, B, C in order."""
import argparse
import json
import os
from pathlib import Path
import re
import time
import serial


def collect(port, output):
    cards = []
    deadline = time.monotonic() + 120
    print("LOCAL ENROLLMENT: tap Room A, remove it, then B, remove it, then C.")
    with serial.Serial(port, 115200, timeout=0.2, write_timeout=0.2) as connection:
        connection.write(b'{"v":2,"type":"hello"}\n')
        while len(cards) < 3 and time.monotonic() < deadline:
            line = connection.read_until(b"\n", 513)
            if len(line) > 512 or not line.endswith(b"\n"):
                continue
            try:
                message = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                continue
            if not isinstance(message, dict) or type(message.get("v")) is not int or message["v"] != 2 or message.get("type") != "enroll_uid":
                continue
            uid = message.get("uid", "")
            if not isinstance(uid, str) or not re.fullmatch(r"(?:[0-9A-F]{8}|[0-9A-F]{14}|[0-9A-F]{20})", uid):
                continue
            if uid in cards:
                print("Duplicate card ignored; present the next room's card.")
                continue
            cards.append(uid)
            print(f"Room {chr(64 + len(cards))} captured; UID kept local.")
    if len(cards) != 3:
        raise SystemExit("Enrollment timed out; configuration unchanged.")
    content = '#pragma once\nconstexpr const char* CARD_UIDS[3] = {'
    content += ", ".join(json.dumps(card) for card in cards) + '};\n'
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves any existing map; rename it deliberately to re-enroll.
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as destination:
        destination.write(content)
    print(f"Saved {output}. Rebuild and flash esp32-a (normal mode).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    args = parser.parse_args()
    collect(args.port, Path(__file__).resolve().parents[1] / "firmware/include/cards.local.h")
