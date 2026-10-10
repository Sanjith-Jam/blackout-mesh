# Person A: wiring and bring-up

RC522 wiring below was supplied by the user on 2026-10-09 as already connected.
It has not been physically inspected or tested by this agent. Phase 0 identifies
classic ESP32 silicon with 4 MB flash, not the exact carrier board. The build
uses the generic `esp32dev` profile. Verify the printed GPIO labels on your board;
these are GPIO numbers, not physical header positions. No pinout for S2/S3/C3 is implied.

## Reader (already wired)

| RC522 marking | ESP32 marking | Purpose |
|---|---|---|
| 3.3V | 3V3 | Supply |
| GND | GND | Common ground |
| SDA / SS | GPIO21 | SPI chip select; this SDA is not an I²C connection |
| SCK | GPIO18 | SPI clock |
| MOSI | GPIO23 | SPI data from ESP32 |
| MISO | GPIO19 | SPI data to ESP32 |
| RST | GPIO22 | Reader reset |
| IRQ | Unconnected | Not used |

Use the module's documented 3.3 V supply/interface. Never connect its supply or
signals to 5 V. SPI is configured globally at 1 MHz. Keep jumpers short.

## Five buttons (not yet wired)

Step-by-step beginner version: [ESP32_A_CONNECTION_GUIDE.md](ESP32_A_CONNECTION_GUIDE.md).

| Label | GPIO | Other switch terminal |
|---|---|---|
| DEPRIVED (SIMULATE SHORTAGE) | 26 | GND |
| NORMAL (RESTORE) | 27 | GND |
| ROOM A (RFID fallback) | 33 | GND |
| ROOM B | 13 | GND |
| ROOM C | 14 | GND |

Each room button sends the same `START_SESSION` event that room's card would, so the demo runs without cards if the reader fails. Pressing it (or tapping the card) again ends that room. END and RESET are not fitted (`-1` in `config.h`); set a GPIO there to add them back.

Firmware uses `INPUT_PULLUP`: released reads HIGH, pressed connects to ground and
reads LOW. No external pull-up or button series resistor is needed for this
switch-to-ground arrangement. Do not connect a button to 3V3 or VIN.

For a four-leg tactile switch, two legs on the same electrical side are already
joined. Use one terminal from each switched side. With power removed, confirm
with continuity mode: chosen terminals must be open when released and connected
only when pressed. Place the switch across the breadboard center gap if its
geometry supports that; orientation varies. Connect all button ground leads to
the same GND rail as this ESP32 and reader.

These pins avoid the reader's SPI/CS/RST pins, UART0, flash and classic ESP32
strapping pins. Confirm your carrier exposes them without an attached peripheral.
Do not use input-only GPIO34–39 with this internal-pull-up configuration.
An alternate mapping belongs in ignored `firmware/include/hardware.local.h`.

## Power and first boot

1. Unplug USB before wiring or moving jumpers. Leave motors, relays, adapters and
   separate supply rails disconnected.
2. Verify RC522 3V3/GND and all GPIO labels; check there is no short across rails.
3. Connect USB only. A has no classroom output LEDs; B owns those indicators.
4. Resolve serial permissions and close other serial monitors. Never flash both
   boards by guessing the same port. Label the board/cable after identification.
5. Flash enrollment firmware, collect three cards locally, then flash normal
   firmware. Raw UID messages exist only in enrollment mode.

## Exact commands (from repository root)

```sh
pio run -d firmware -e esp32-a -e esp32-a-enroll
python3 tools/test_esp32_a.py
python3 tools/test_host_tools.py
pio run -d firmware -e esp32-a-enroll -t upload --upload-port /dev/ttyUSB0
```

The host utilities use pyserial. To avoid modifying system Python:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install pyserial
.venv/bin/python tools/enroll_cards.py --port /dev/ttyUSB0
pio run -d firmware -e esp32-a -t upload --upload-port /dev/ttyUSB0
.venv/bin/python tools/gateway_console.py --port /dev/ttyUSB0
```

The enrollment utility waits up to 120 seconds: tap A, remove for at least 250 ms,
then B, remove, then C. Use three different cards. It creates an ignored private
`cards.local.h` without overwriting an existing map. For deliberate re-enrollment,
move the old map somewhere private first. Rebuild normal firmware after any map
change. Enrollment is identification for this demo, not access authentication.
Normal firmware rejects every card until a valid local map exists.

For raw output, close the console first, then:

```sh
pio device monitor --port /dev/ttyUSB0 --baud 115200
```

A raw monitor does not perform host sync; inputs correctly report unsynchronized.
The input console starts a fresh empty **input-only** session, acknowledges
registration requests, and prints registrations. It never solves allocation,
sends radio masks or confirms classroom power. Do not run it beside the real
controller: exactly one host owns the serial connection.

## Serial access on this computer

At implementation time `/dev/ttyUSB0` was owned by `root:uucp`, mode `0660`, and
this process was not in `uucp`. Opening it failed with `Permission denied`.
An administrator can grant your login membership in the serial-port group:

```sh
sudo usermod -aG uucp "$USER"
```

Then log out and back in, and restart Codex so its process inherits membership.
This command was not executed by the agent. Group names differ on other systems
(e.g. `dialout`); inspect the actual port ownership rather than copying blindly.
Do not make the port world-writable or run the whole development environment as root.

## Acceptance — record actual outcomes

- Boot: reader initialized or visible fault; gateway unsynchronized. No power claim.
- Tap each known card: exactly one START for its room. Hold for 5 seconds: no
  additional START. Remove for 250 ms and re-tap: one new event ID.
- Tap A then B: console retains A and B; END acts on selected B.
- Unknown card: visible `unknown_card`; selection and registrations unchanged.
- END with no selection: `ignored_no_selection`. Bounce/hold each ordinary button:
  one action per press. Short RESET: no action; hold beyond 2 seconds: one reset,
  cleared registrations/selection and fresh synchronization.
- Reader unplug/fault: fault visible; existing host registrations retained.
  Reconnect the reader only after removing USB power.
- Close host for over 1.5 seconds: stale; taps are discarded. Reopen: fresh sync,
  no replay. Disconnect/reconnect USB and repeat.
- With Person B: verify masks 8, 16, 32, 24, 56; also logical 511 → physical 56.
  Sending or enqueueing is not proof: inspect LEDs and matching application ACK.
- Power B off during END/reset: show unconfirmed; on B reboot observe boot-OFF,
  state report, new SYNC and current desired mask. Test invalid/stale/duplicate
  commands. Record a 60-second stable observation and three complete runs.

## Troubleshooting

- Reader fault: check 3.3 V, GND, SS21/RST22, SPI18/19/23; model and card compatibility
  must be RC522 / supported ISO14443A. Version register 0/255 indicates no response.
  A responding version register alone does not prove reliable card operation.
- Unknown known card: enroll locally, rebuild normal target, flash normal target.
- Held card repeats: verify RF placement; removal is inferred from repeated absent
  polls for 250 ms. Marginal coupling can resemble removal; physical test is required.
- Button always pressed: wrong switch terminals, GPIO shorted to GND or wrong polarity.
- No input events in raw monitor: use the synchronized console/controller.
- Missing radio configuration: follow the integration guide; no broadcast fallback.
- Upload busy: close console/monitor. Permission denied: fix group membership above.
- Wrong boot/flash profile: stop and identify exact board; do not erase NVS casually.
