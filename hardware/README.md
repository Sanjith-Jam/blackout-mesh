# Person B: output station (board B + laptop bench controller)

## What's here

| Path | What it is |
|---|---|
| `firmware/BoardB_Output/BoardB_Output.ino` | Board B firmware. Boots OFF, syncs with the laptop, validates every command, drives the classroom LEDs and ACKs the applied mask. The link LED is solid when synced, blinks at 1 Hz when unsynced and at 4 Hz when stale. |
| `firmware/BoardB_FixtureTest/` | Phase 2 LED test sketch: type a mask on Serial and the LEDs follow. |
| `host/controller.py` | Laptop bench controller. Tracks registration, shortage/restore (staged), END/RESET, the BENCH/RULES or LIVE MODEL label, and shows registered / activity / commanded / ACKed per room. |
| `host/link.py` | Laptop ↔ B link: sync, reboot detection, one command in flight, retries, ACK validation, stale display. Also includes `SimBoardB`, a Python copy of the firmware rules used for testing. |
| `host/protocol.py`, `host/allocator.py` | 26-byte frame encode/decode with CRC, and the CLASSROOM BENCH allocator (6/6/4 kW, 16 kW normal / 6 kW shortage). |
| `host/test_person_b.py` | 16 unit and end-to-end tests (simulated B). |
| `host/hw_check.py`, `hw_check_output.txt` | Scripted run against the real board B, and its output: 15/15 passed on 2026-10-09. |
| `PROTOCOL.md` | The contract **Person A** must implement on board A. |

## Pins (proposed, ESP32 DevKit, confirm before wiring)

Each LED connects to its GPIO through its own 220–330 Ω resistor, with the LED's short leg to GND.

| Output | GPIO |
|---|---|
| Room A | 25 |
| Room B | 26 |
| Room C | 27 |
| Link LED | 33 |

## Run it

Needs Python 3 and `pyserial` (`python -m pip install --user pyserial`).

Run these from the `host/` folder:

```
python -m unittest test_person_b          # 16 tests, no hardware
python controller.py --sim                # try the controller with a simulated board B
python controller.py --port COM3          # drive the real board B directly over USB
python hw_check.py COM3                   # scripted bench + fault-injection check
```

Controller keys: `a` / `b` / `c` scan a card, `x` unknown card, `sel a` select a room, `end`, `short`, `restore`, `reset`, `fault` / `ok` for reader fault, `q` quit.

Once board A bridges to the radio, use `--port <A's COM port>`. Board A's `EV ...` lines then drive the same controller.

Flash board B with **Upload Speed 115200** (921600 fails on this board).

## Status against the plan

| Phase | Person B item | State |
|---|---|---|
| 1 | Inspect board B, pick pins, fixtures | Board identified (ESP32-D0WDQ6, CP2102, MAC <board B MAC, shared privately>). Pins proposed. Fixtures 0/8/16/32/24/56 defined and tested. |
| 2 | LED bring-up, 60 s stability | **You:** wire the 4 LEDs and run the fixture sketch. Firmware logic is verified via ACKs, but the LEDs are not yet physically wired. |
| 3 | B validation, GPIO, ACK projection, laptop controller | Done. Over USB on the real board: sync, all fixtures, stale/wrong-boot/bad-mask/duplicate/corrupt rejection. |
| 3 | Radio pairing with A | **Blocked on Person A:** needs A's MAC in `PEER_A_MAC` and A's bridge per `PROTOCOL.md`. |
| 4 | Shortage selection | Done in BENCH / RULES MODE. Rank is ACTIVE > UNKNOWN > INACTIVE, then A > B > C. Unregistered rooms are never served. |
| 4 | ML hookup | Hook ready (`--model-json predictions.json` with `{"model_version": ..., "rooms": {"A": "ACTIVE", ...}}`). **No trained model exists yet**, so LIVE MODEL is pending. |
| 5 | B power cycle, radio loss, malformed/stale/duplicate | Malformed/stale/duplicate verified on hardware. Reboot and B-offline recovery verified in simulation only. Repeat them with real radio. |
| 6 | Mounting, labels, rehearsal | **You**, together with Person A. |

## Choices I made (change if the team disagrees)

- **Normal supply serves rooms immediately.** Registered rooms light up under normal supply too, because the plan's rule is served = registered AND allocator-selected, and 16 kW fits all three. A shortage then sheds down to what fits.
- **Restore is staged.** It adds one room per second in rank order. Shedding is immediate.
- **Frame layout is my reading of the plan.** The plan says "26-byte radio shape, version 2, 16-bit mask", but the repo has no frame definition. `PROTOCOL.md` is my concrete version. Agree it with Person A before they code.
