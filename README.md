# Blackout Mesh

A hackathon prototype for simulated power allocation, RFID classroom interaction and ESP32 LED feedback. “Mesh” is a working name; multi-hop routing is outside scope.

## Current progress

Software demo now includes a trained local occupancy classifier, recorded-data replay, exact six-service allocation and the original website interface. Hardware work is paused; ESP32 A/B contracts still conflict and physical ACKs remain unconfirmed. The model uses office observations as a proxy and does not establish campus accuracy.
See [the current progress report](PROGRESS_REPORT.md) for evidence, limitations and next steps.

## Documents

- [Exhaustive pending implementation plan](PENDING_IMPLEMENTATION_PLAN.md): 24 issues, dependency order, technology choices and release gates.
- [Remaining application plan v2.0](PRIORITYGRID_HACKATHON_REMAINING_PLAN.md) and [blueprint](PRIORITYGRID_FINAL_IMPLEMENTATION_BLUEPRINT.md).
- [Required ML plan](LAB_ACTIVITY_ML_PLAN.md): training/evaluation requirement; catalog must be reconciled with the current application.
- [Context](CONTEXT.md) and [agent instructions](AGENTS.md).
- [A wiring](docs/ESP32_A_WIRING.md), [A status](ESP32_A_STATUS.md), [A serial/radio contract](contracts/serial_protocol.md).
- [B bench guide](hardware/README.md) and [B contract](hardware/PROTOCOL.md). Contracts are currently incompatible.

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

Routes: `/`, `/demo`, `/hospital`, `/classrooms`. The classroom route contains physical floor plans, component wiring and powered/shed appliance states. Reset, scan CR1, then choose overload: CR1 stays fully on while CR2/CR3 retain computers and lighting. Its separate catalog is 8,000 W normal and 3,400 W shortage. The hospital route shows three virtual transformers and sensor-derived likely causes, including missing evidence. These are synthetic demonstrations; the fault rules are not a trained transformer model or certified protection. Open `/demo` for the original controls. The UI redesign and its ML/replay presentation have been reverted at the user’s request; use the API documentation at `/docs` to exercise the model and replay until the user specifies classifier visuals. The backend reports hardware disconnected. Inactive rooms can be deliberately left unserved; a lower served-watt total is not measured energy savings. Restore waits for five seconds of stable capacity/feeders and three seconds after shedding, then adds at most one service per second.

No API key, paid service, GPU or training step is needed to run the checked-in classifier. For model provenance, training commands, measured benchmark and limits, see [model report](backend/models/MODEL_REPORT.md). API documentation is at `http://127.0.0.1:8000/docs`. Keep the demo bound to localhost; deployment/authentication is outside this delivery.

## Verified checks

```sh
python3 tools/test_esp32_a.py
python3 tools/test_radio_protocol.py
python3 tools/test_host_tools.py
pio run -d firmware -e esp32-a -e esp32-a-enroll
PYTHONPATH=backend uv run --no-project --python 3.14 --with-requirements backend/requirements.txt --with-requirements backend/requirements-ml.txt --with pytest --with httpx python -m pytest backend/tests -q
```

From `hardware/host/`: `python3 -m unittest test_person_b`. From `frontend/`: `npm run build` after installing dependencies. Detailed results are in the progress report.

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

B bench commands (from `hardware/host/`): `python3 controller.py --sim`, `python3 controller.py --port <port>`, `python3 hw_check.py <port>`. Real serial needs pyserial. Board B flashing/core instructions are in its guide. Do not connect the unchanged A and B implementations expecting protocol compatibility, or run a bench controller alongside the backend authority.

Local planning/reuse research, judge critique, notice drafts, private credentials and historical archives stay outside this repository. Existing reuse recommendations remain unchanged; preserve required license notices when incorporating upstream code.
