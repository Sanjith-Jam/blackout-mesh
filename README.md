# Blackout Mesh

Keep critical services first when available power falls, and show when evidence is insufficient.

A hackathon prototype combining ML-based lab-activity estimation, constrained power allocation, a simulated campus network and real ESP32 radio/LED feedback. “Mesh” is a working name; multi-hop routing is outside scope.

## Project documents

- [Implementation plan](PRIORITYGRID_UNIFIED_IMPLEMENTATION_PLAN.md): authoritative scope, architecture, contracts, delivery gates and acceptance checks.
- [Required lab activity ML plan](LAB_ACTIVITY_ML_PLAN.md): model, data, nine-load catalog, priority policy and phased implementation.
- [Agent instructions](AGENTS.md): implementation workflow and invariants.
- [Context](CONTEXT.md): project status and next action.

## Status

ESP32 A firmware compiles and passes host checks. Application/ML and physical integration remain pending.

Commands:
- `python3 tools/test_esp32_a.py` — run host assertions.
- `pio run -d firmware -e esp32-a` — compile the gateway (radio requires private provisioning).
- `python3 tools/test_radio_protocol.py` — synthetic wire fixtures and all 512 mask round trips.

- `pio run -d firmware -e esp32-a -e esp32-a-enroll` — build normal/enrollment firmware.
- `pio run -d firmware -e esp32-a-enroll -t upload --upload-port /dev/ttyUSB0` — flash local enrollment mode.
- `pio run -d firmware -e esp32-a -t upload --upload-port /dev/ttyUSB0` — flash normal gateway.
- `pio device monitor --port /dev/ttyUSB0 --baud 115200` — raw JSON output (no host sync).
- `python3 tools/test_host_tools.py` — simulated console/enrollment checks.
- `.venv/bin/python tools/enroll_cards.py --port /dev/ttyUSB0` — capture A/B/C to an ignored map.
- `.venv/bin/python tools/gateway_console.py --port /dev/ttyUSB0` — input-only synchronized acceptance console.

For utility dependencies: `python3 -m venv .venv`, then `.venv/bin/python -m pip install pyserial`.
Run `pio pkg install -d firmware` before host C++ checks on a fresh checkout.

The main demo has nine circuits with 84 kW total configured demand: three labs plus six other services. A required classifier estimates lab activity; a fixed policy prioritizes active labs below protected critical services, and the optimizer enforces capacity/feeder limits. Inputs are simulated or explicitly emulated; no real-campus occupancy accuracy is claimed. Two ESP32s handle Lab-ID RFID cards, four buttons and nine load indicators. Old seven/six-load examples remain separate regression fixtures.

Review notes, reuse research, notices drafts and historical plans are maintained locally outside this repository. Preserve applicable third-party license notices whenever code is incorporated.
