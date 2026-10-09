"""Input-only acceptance console. It acknowledges events; it never commands LEDs."""
import argparse
import json
import time
import serial


def uint32(value, minimum=1):
    return type(value) is int and minimum <= value <= 0xffffffff


def valid_context(message):
    return all(uint32(message.get(key)) for key in ("boot", "epoch", "session"))


def valid_event(message):
    action = message.get("action")
    if not uint32(message.get("event")):
        return False
    if action in ("START_SESSION", "END_SESSION"):
        return message.get("room") in ("A", "B", "C")
    return action in ("SIMULATE_SHORTAGE", "RESTORE", "RESET_SESSION") and "room" not in message


def run(port, session):
    context = None
    next_ping = 0.0
    last_event = 0
    registered = set()
    with serial.Serial(port, 115200, timeout=0.05, write_timeout=0.2) as connection:
        def send(kind, **fields):
            connection.write((json.dumps({"v": 2, "type": kind, **fields}) + "\n").encode())
        send("hello")
        while True:
            line = connection.read_until(b"\n", 513)
            if line.endswith(b"\n") and len(line) <= 512:
                try:
                    message = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    continue
                if not isinstance(message, dict) or type(message.get("v")) is not int or message["v"] != 2:
                    continue
                kind = message.get("type")
                if kind == "hello":
                    if not all(uint32(message.get(key)) for key in ("boot", "epoch")) or not uint32(message.get("minimum_session"), 0):
                        continue
                    if message.get("mode") == "LOCAL_ENROLLMENT":
                        raise SystemExit("Flash normal esp32-a firmware before the input console.")
                    identity = (message["boot"], message["epoch"])
                    if context is None or identity != (context["boot"], context["epoch"]):
                        session = max(session, message["minimum_session"] + 1, 1)
                        if session > 0xffffffff:
                            raise SystemExit("Session counter exhausted; deliberate reprovisioning required.")
                        last_event = 0
                        context = {"boot": identity[0], "epoch": identity[1], "session": session}
                        send("sync", **context, selected=None)
                        registered.clear()
                        print("Fresh input session; no physical output confirmed.")
                elif context and valid_context(message) and all(message.get(key) == value for key, value in context.items()):
                    if kind == "event":
                        if not valid_event(message):
                            continue
                        event = message["event"]
                        if event > last_event:
                            last_event = event
                            action = message["action"]
                            room = message.get("room")
                            if action == "START_SESSION":
                                registered.add(room)
                            elif action == "END_SESSION":
                                registered.discard(room)
                            elif action == "RESET_SESSION":
                                registered.clear()
                                session += 1
                            print(action, room or "", "registered:", sorted(registered))
                        send("event_ack", **context, event=event, accepted=True)
                    elif kind == "status" and message.get("code") != "pong":
                        print(message["code"])
                elif kind == "status":
                    print(message.get("code"))
            now = time.monotonic()
            if context and now >= next_ping:
                send("ping", **context)
                next_ping = now + 0.5


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--session", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.session <= 0xffffffff:
        parser.error("session must be a positive uint32")
    try:
        run(args.port, args.session)
    except KeyboardInterrupt:
        pass
