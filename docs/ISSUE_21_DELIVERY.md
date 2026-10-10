# Issue #21 delivery — shared room sessions

## Delivered

- `GridState.active_sessions` is the canonical room-session store for the campus, classroom visualizer, software session commands and board gateway events.
- The classroom visualizer reads the shared sessions directly. Starting or ending a session there also changes the campus requested-load mask in the same site revision; RFID starts/ends are reflected in the classroom map.
- Multiple rooms remain active at once. Explicit unscan removes only its room. RFID duplicate scans are suppressed inside the existing debounce interval; an unknown UID is non-destructive.
- Every HTTP session mutation requires a bounded event ID, UTC observation time, and the current `run_id`. Repeated IDs replay their result without toggling state; conflicting ID reuse and per-room out-of-order events return 409. Events more than 30 seconds old or over 2 seconds in the future are rejected. A new run clears active sessions and the bounded in-memory event cache; requests from the previous run are rejected.
- Session presence is request/session evidence, not an occupancy-model prediction. Raw UIDs stay in the enrollment boundary and are not added to session or inference records.

## Verification

`PYTHONPATH=backend .venv-ml/bin/python -m pytest backend/tests/test_site.py backend/tests/test_api.py backend/tests/test_visualizers.py backend/tests/test_history.py backend/tests/test_gateway.py -q` — **54 passed**. Tests cover cross-route requested demand, multi-room state, explicit end, duplicate event IDs, conflicting ID reuse, stale/out-of-order timestamps, expiry, new-run reset, and previous-run rejection. Gateway fake-board events now use the same `GridState` session dictionary as the live app and assert that a START_SESSION changes campus demand.

## Semantic compatibility

| Producer | Start/end behavior | Identity and provenance | Result |
|---|---|---|---|
| Classroom visualizer | Explicit scan starts; unscan ends; multiple rooms coexist | Current site `run_id`, event UUID and UTC observation time | Same room session and requested service mask as the campus projection |
| HTTP RFID | Registered card starts; a repeated tap inside 2 s is suppressed; a later tap ends | UID resolves to a room alias before session state; only alias/source is recorded | Unknown cards leave every active session unchanged |
| Board A adapter | `START_SESSION` / `END_SESSION` map to explicit room start/end; reset clears rooms | Existing v2 fake-board boot/epoch/session/event framing; source `HARDWARE` | Gateway ACK follows the session update; campus and classroom projections read shared state |
| Process/run boundary | Expiry after 2 hours; a new run clears sessions and event IDs | Old run IDs return 409; events older than 30 s or >2 s in the future return 422 | No old room session is carried into a new run |
| Occupancy model | Independent sensor-evidence path | No card UID or session ID enters model features | Session presence is not represented as a model prediction |

These are software contract results only. ESP32 firmware has not been flashed or physically verified, and the existing A/B wire protocols still need separate reconciliation before real integration.

Issue #21 acceptance criteria are covered by the focused backend tests and the simulated gateway fixture; issue closure should follow integration of this delivery into `main`.
