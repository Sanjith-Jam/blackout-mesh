# Blackout Mesh

A hackathon prototype for simulated power allocation, RFID classroom interaction and ESP32 LED feedback. “Mesh” is a working name; multi-hop routing is outside scope.

## Current progress

Software demo now includes a trained local occupancy classifier, recorded-data replay, exact six-service allocation and the original website interface. Board A (RFID reader + five buttons, including an RFID-fail fallback for room A) and board B (room LEDs) now share one contract, and the backend bridges board A to the website; physical end-to-end acceptance with both boards is still to be recorded. The model uses office observations as a proxy and does not establish campus accuracy.
See [the current progress report](PROGRESS_REPORT.md) for evidence, limitations and next steps.

## Documents

- [Exhaustive pending implementation plan](PENDING_IMPLEMENTATION_PLAN.md): 24 issues, dependency order, technology choices and release gates.
- [Remaining application plan v2.0](PRIORITYGRID_HACKATHON_REMAINING_PLAN.md) and [blueprint](PRIORITYGRID_FINAL_IMPLEMENTATION_BLUEPRINT.md).
- [Required ML plan](LAB_ACTIVITY_ML_PLAN.md): training/evaluation requirement; catalog must be reconciled with the current application.
- [Context](CONTEXT.md) and [agent instructions](AGENTS.md).
- [A wiring](docs/ESP32_A_WIRING.md), [A status](ESP32_A_STATUS.md), [A serial/radio contract](contracts/serial_protocol.md).
- [Board A connection guide](docs/ESP32_A_CONNECTION_GUIDE.md), [B guide](hardware/README.md); both boards use the [A serial/radio contract](contracts/serial_protocol.md).

## Application

From repository root:

```sh
uv run --no-project --python 3.14 --with-requirements backend/requirements.txt --with-requirements backend/requirements-ml.txt python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm ci --no-audit --no-fund
npm run dev
```

Routes: `/`, `/demo`, `/hospital`, `/classrooms`. The classroom route contains physical floor plans, component wiring and powered/shed appliance states. Reset, scan CR1, then choose overload: CR1 stays fully on while CR2/CR3 retain computers and lighting. Its separate catalog is 8,000 W normal and 3,400 W shortage. The hospital route shows three virtual transformers and sensor-derived likely causes, including missing evidence. These are synthetic demonstrations; the fault rules are not a trained transformer model or certified protection. Open `/demo` for the original controls. The UI redesign and its ML/replay presentation have been reverted at the user’s request; use the API documentation at `/docs` to exercise the model and replay until the user specifies classifier visuals. The backend reports hardware disconnected. An INACTIVE prediction only lowers a room's rank: it never sheds a room while capacity allows, never switches off protected lighting/computers or hospital critical circuits, and only counts after two consecutive INACTIVE readings (`backend/app/core/safety.py`). A lower served-watt total is not measured energy savings. Restore waits for five seconds of stable capacity/feeders and three seconds after shedding, then adds at most one service per second.

No API key, paid service, GPU or training step is needed to run the checked-in classifier. For model provenance, training commands, measured benchmark and limits, see [model report](backend/models/MODEL_REPORT.md). API documentation is at `http://127.0.0.1:8000/docs`. Keep the demo bound to localhost; deployment/authentication is outside this delivery.

## Verified checks

```sh
python3 tools/test_esp32_a.py
python3 tools/test_radio_protocol.py
python3 tools/test_host_tools.py
pio run -d firmware -e esp32-a -e esp32-a-enroll
PYTHONPATH=backend uv run --no-project --python 3.14 --with-requirements backend/requirements.txt --with-requirements backend/requirements-ml.txt --with pytest --with httpx python -m pytest backend/tests -q
```

From `frontend/`: `npm run build` after installing dependencies. Detailed results are in the progress report.

## Hardware utilities

A enrollment/input commands (from repository root; board identity/wiring/access must be verified first):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install pyserial
pio run -d firmware -e esp32-a-enroll -t upload --upload-port /dev/ttyUSB0
.venv/bin/python tools/enroll_cards.py --port /dev/ttyUSB0
pio run -d firmware -e esp32-a -t upload --upload-port /dev/ttyUSB0
.venv/bin/python tools/gateway_console.py --port /dev/ttyUSB0
```

`pio device monitor --port /dev/ttyUSB0 --baud 115200` shows raw output without host sync. Run `pio pkg install -d firmware` before native C++ checks on a fresh checkout.

Board B bench check: `python hardware/tools/check_board_b.py <port>`. Full demo with both boards: start the backend with `BLACKOUT_GATEWAY_PORT=<board A port>` or use Connect on the Classrooms page, as in the [connection guide](docs/ESP32_A_CONNECTION_GUIDE.md).

Local planning/reuse research, judge critique, notice drafts, private credentials and historical archives stay outside this repository. Existing reuse recommendations remain unchanged; preserve required license notices when incorporating upstream code.

### Evaluation and policy evidence

- [Temporal occupancy audit](backend/benchmarks/occupancy/REPORT.md): rolling-origin results and conservative adoption gate; campus generalization remains unvalidated.
- [Allocation policies](docs/ALLOCATION_POLICIES.md): versioned API configuration, per-load explanations and decision replay.
- [Electrical studies](docs/ELECTRICAL_SIMULATION.md): optional balanced AC adapter, matched engines, assumptions and failure boundaries.
