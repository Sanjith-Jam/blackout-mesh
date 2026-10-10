# Board B: output station

Board B drives the three classroom LEDs and a link LED. It speaks **board A's contract v2** (`contracts/serial_protocol.md`): board A forwards the laptop's LED commands to it over encrypted ESP-NOW, and board B acknowledges the mask it actually applied. The laptop side lives in `backend/app/hardware/gateway.py`.

## What's here

| Path | What it is |
|---|---|
| `firmware/BoardB_Output/BoardB_Output.ino` | Board B firmware (Arduino ESP32 core 3.3.12). Boots OFF; persisted boot counter; binds to a session on SYNC; applies `mask & 0x38` on SET_LOADS; re-ACKs duplicates; rejects stale, conflicting or wrong-session commands; heartbeat every 400 ms; keeps last LEDs and fast-blinks the link LED when board A goes quiet for 1.5 s. Also accepts the same frames as `F <hex>` lines on USB for bench tests. |
| `firmware/BoardB_Output/protocol.h` | Byte-identical copy of `firmware/include/protocol.h` (a backend test enforces this). |
| `firmware/BoardB_Output/secrets.example.h` | Copy to `secrets.h`: board A's MAC plus the shared PMK/LMK. Git-ignored. |
| `firmware/BoardB_FixtureTest/` | LED-only wiring test: type a mask on Serial and the LEDs follow. |
| `tools/check_board_b.py` | USB bench check of board B without board A: binds a session, lights A, B, C, A+B, all, off for a second each, and checks duplicate/conflict/stale/wrong-session handling. |

## Wiring

Each LED: ESP32 pin → 220–330 Ω resistor → LED long leg; LED short leg → GND rail; one jumper from an ESP32 GND pin to that rail.

| LED | GPIO |
|---|---|
| Room A | 25 |
| Room B | 26 |
| Room C | 27 |
| Link | 33 |

## Flash and check

Arduino IDE: board "ESP32 Dev Module", **Upload Speed 115200** (921600 fails on this board's USB chip). Then:

```
.venv\Scripts\python hardware\tools\check_board_b.py COM3
```

Pairing with board A, running the full demo and the test cases: [docs/ESP32_A_CONNECTION_GUIDE.md](../docs/ESP32_A_CONNECTION_GUIDE.md).

## Drive board B from the website without board A

With only board B plugged in, the backend can stand in for board A in software and send LED
commands over B's USB bench interface. No `secrets.h` is needed for this mode.

1. Flash board B (above) and start the backend and frontend.
2. On the Classrooms page, open **Physical boards**, enter B's port (for example `COM3`), choose
   **Board B only (LEDs)** and press **Connect**. Or start the backend with
   `BLACKOUT_GATEWAY_PORT=COM3` and `BLACKOUT_GATEWAY_BOARD=B`.
3. Scan rooms and change the supply. A room's LED is on when the room has a session and all its
   equipment is served, and the panel shows it confirmed only after board B's own ACK.

There is no card reader or buttons in this mode; the website's controls are the inputs.
