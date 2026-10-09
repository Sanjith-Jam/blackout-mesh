# ESP32 A — verified software status

2026-10-09. **Software ready for bench bring-up; physical integration not verified.**
Person A scope only. No B firmware, allocator, classifier or frontend was replaced.
No device was flashed and no reader/button/radio test was observed by the agent.

## Files delivered

- `firmware/src/main.cpp`: persisted boot/session context, host handshake/events,
  reset handling, bounded queues and cooperative gateway loop.
- `firmware/include/{inputs,buttons,protocol,bridge,session,serial_protocol}.h`:
  host-tested production state machines, strict parser and 26-byte wire codec.
- `firmware/include/{reader,espnow_link,serial_bridge,config}.h`: RC522 task,
  allowlisted encrypted radio, nonblocking UART output and pin configuration.
- `firmware/include/{cards,hardware,secrets}.example.h`: local configuration templates.
- `firmware/platformio.ini`: successfully compiled normal/enrollment targets and pins.
- `firmware/test/test_*.cpp`, `tools/test_*.py`: host checks and synthetic serial tests.
- `tools/{enroll_cards,gateway_console,radio_protocol}.py`: enrollment, input-only
  console and Python wire adapter. No autonomous power decision code.
- `contracts/serial_protocol.md`, `contracts/schema_examples/esp32_a_v2.json`:
  shared wire agreement and six synthetic golden fixtures.
- `docs/ESP32_A_WIRING.md`, `docs/ESP32_A_INTEGRATION.md`,
  `docs/FIRMWARE_DEPENDENCIES.md`: wiring, commands, recovery and dependency notices.
- README, AGENTS, CONTEXT and ignore rules updated. This section records the original local handoff; see PROGRESS_REPORT.md for subsequent repository synchronization.

## Actual commands and results

```text
python3 tools/test_esp32_a.py
input/buttons/packet/radio assertions passed (all 512 mask projections)
serial/session assertions passed

python3 tools/test_radio_protocol.py
Ran 1 test — OK (six golden fixtures; all 512 mask round trips)

python3 tools/test_host_tools.py
Ran 3 tests — OK (fake serial enrollment, duplicate events/A+B, invalid host input)

pio run -d firmware -e esp32-a -e esp32-a-enroll
esp32-a         SUCCESS   00:00:07.061
esp32-a-enroll  SUCCESS   00:00:03.543
2 succeeded in 00:00:10.603
```

C++ production logic ran with `-Wall -Wextra -Werror` and address/undefined-behavior
sanitizers. Framework: Arduino ESP32 2.0.17; platform 7.1.3; ArduinoJson 7.4.3;
MFRC522 1.4.12. Versions were pinned only after successful installation/build.
Default normal image: radio disabled until local provisioning. Enrollment image:
no radio or synchronized application events. Full encrypted-radio path was also
compiled with a temporary synthetic peer MAC and randomly generated local keys:
exit 0, RAM 48,688 bytes, flash 761,461 bytes. It was never flashed; temporary
provisioning was removed and both default images rebuilt. Raw local logs remain
under ignored `firmware/.local/` and `/tmp/blackout-mesh-build.log`.

The first build attempt installed dependencies but failed because source was not
written yet. The first serial-parser check exposed a deprecated ArduinoJson API;
that was corrected before committing. The final checks above pass.

## Functional coverage and limits

| Requirement | Verified locally |
|---|---|
| Boot unsynchronized; host-selected room restored | Native state tests |
| Known-card event; held-card suppression; removal/re-tap; unknown preserves selection | Native input samples; actual RC522 reads pending |
| Room B retains Room A registration | Fake-serial host console test; A never owns registrations |
| END/no-selection; distinct shortage/restore | Native input tests |
| Button bounce; short reset ignored; 2-second hold once | Simulated-clock native tests; real switches pending |
| Reconnect discards obsolete work; fresh epoch; no stale event ACK | Native session tests |
| Bounded/malformed/oversized/trailing serial data, bad IDs/types | Native parser tests |
| Retry identity, one in flight, latest unsent coalescing, timeout | Native bridge tests |
| Duplicate command, stale session/boot/ACK, wrong projection | Native bridge tests |
| Full 16-bit mask; 8/16/32/24/56; all 512 projections | C++ and Python contract checks |
| Only matching application ACK confirms SET | Native bridge tests; real B pending |
| Reader waits cannot block gateway loop | Separate bounded FreeRTOS reader task; physical timing not measured |
| Enrollment map private, complete 4/7/10-byte UID forms | Fake-serial test; actual cards pending |

## Hardware evidence and remaining work

User reports RC522 already wired: 3V3/GND, SS21, SCK18, MOSI23, MISO19, RST22;
IRQ unused. Earlier local Phase 0 records identify two classic ESP32 chips and
4-MB flash, but not the exact carrier. No new identity query succeeded here:

```text
esptool.py v4.11.0
Serial port /dev/ttyUSB0
Could not open /dev/ttyUSB0 ... Permission denied
```

Current port owner/group/mode: root:uucp, 0660. Agent process lacks uucp membership.
The query used PlatformIO's Python runtime after system Python lacked pyserial.
No administrative permissions or device ownership were changed.

Buttons are **not wired**. The guide uses END25 / SHORTAGE26 / RESTORE27 / RESET32,
switching each GPIO to GND, internal pull-up, active LOW. Verify exposed carrier
labels and tactile-switch terminals before wiring. Local card map and real peer
credentials are intentionally absent; normal firmware rejects unmapped cards and
disables unprovisioned radio. Person B must adopt the documented numeric protocol
values; compatibility with any unseen implementation is unverified.

## Exact next steps

1. Follow [the wiring guide](docs/ESP32_A_WIRING.md), including serial group access
   and a fresh login/app restart. Unplug USB while wiring the four buttons.
2. Identify the board, close other serial clients, then from repository root:

```sh
pio run -d firmware -e esp32-a-enroll -t upload --upload-port /dev/ttyUSB0
python3 -m venv .venv
.venv/bin/python -m pip install pyserial
.venv/bin/python tools/enroll_cards.py --port /dev/ttyUSB0
pio run -d firmware -e esp32-a -t upload --upload-port /dev/ttyUSB0
.venv/bin/python tools/gateway_console.py --port /dev/ttyUSB0
```

3. Verify real reads for all three cards, held-card/re-tap/unknown behavior, A+B
   retention, END/no-selection, all four buttons, bounce/hold/reset, reader fault,
   and USB reconnect. Record 60 seconds of stability. Console is INPUT ONLY.
4. Provision A/B peer credentials locally; rebuild/flash; perform
   [the integration matrix](docs/ESP32_A_INTEGRATION.md). Observe boot-OFF and actual
   LEDs for 8/16/32/24/56 and 511→56, matching ACK identity, loss/reboot/stale/duplicate
   rejection, offline END/reset unconfirmed and fresh reconciliation. Rehearse three
   times. Trained ML/classifier-policy integration remains Person B/project work.

**Integration readiness:** compile/test gates pass. Flashing, exact carrier,
card mapping, button operation, actual peer contract and end-to-end ACK gates
remain pending. A connected USB device alone is not evidence of those gates.

## Repository sync update — 2026-10-09

Board B firmware, USB bench controller and the web application now exist in the
merged repository. The earlier statements that they were unimplemented describe
the original Person A handoff. A and B use different serial/radio contracts;
real interoperation remains unverified and requires coordinated changes.
See [current progress report](PROGRESS_REPORT.md).
