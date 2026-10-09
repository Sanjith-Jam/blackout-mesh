# Blackout Mesh — progress report

Updated 2026-10-09. Repository synchronization combines remote main through `f2edb91` with local ESP32 A work through `0aa4210`. The histories are merged without rebasing or discarding either implementation. This is a component-level prototype; end-to-end readiness is not established.

## Progress so far

| Area | Delivered | Evidence and remaining limits |
|---|---|---|
| Phase 0 | Two distinct ESP32 chip/flash queries; user closed phase | Historical local verification; peripheral operation is not implied |
| Frontend | React routes `/`, `/demo`, `/hospital`, `/classrooms`; charts, topology, timeline, API/WebSocket client | Production build passes today; browser interaction and live reconnection not checked today |
| Backend | FastAPI health/snapshot, RFID, capacity/load/feeder actions, WebSocket publication, six-service state and greedy allocation | 10 API tests pass today; no physical hardware adapter or trained model wired into this authority |
| ESP32 A | RC522 task, buttons, bounded JSONL, host handshake, encrypted radio bridge, enrollment/input console | Native sanitizer checks and both firmware builds pass today; original handoff recorded serial permission failure, no successful flash/card/button/radio evidence |
| ESP32 B | Three classroom outputs/status LED, firmware, direct-USB bench controller, rules allocator and fault checks | 16 simulated tests pass today; committed USB log reports 15/15 hardware checks, not rerun today and not proof of physically wired LEDs |
| Classifier | Required model/data/evaluation plan; B controller can read a prediction JSON file | No trained artifact, causal inference pipeline or held-out metrics delivered; reading a JSON file alone does not establish LIVE MODEL readiness |
| Complete demo | Card → authority → allocation → radio → physical LED ACK design | Not demonstrated; contracts and semantics conflict as detailed below |

No percentage complete is assigned: passing individual component tests does not measure integration readiness.

## Checks rerun during this sync

All commands below run from repository root except where noted.

| Command | Actual result |
|---|---|
| `python3 tools/test_esp32_a.py` | Production C++ input/button/packet/radio and serial/session assertions passed, including all 512 projections |
| `python3 tools/test_radio_protocol.py` | 1 test passed; golden frames and all 512 mask round trips |
| `python3 tools/test_host_tools.py` | 3 fake-serial tests passed |
| `python3 -m unittest test_person_b` from `hardware/host/` | 16 tests passed using simulated B |
| `PYTHONPATH=backend uv run --no-project --with-requirements backend/requirements.txt --with pytest --with httpx python -m pytest backend/tests -q` | 10 passed; one upstream TestClient/httpx deprecation warning |
| `npm ci --no-audit --no-fund && npm run build` from `frontend/` | TypeScript/Vite build passed; large JS bundle warning (~1.53 MB minified, ~508 KB gzip) |
| `pio run -d firmware -e esp32-a -e esp32-a-enroll` | Both SUCCESS, 3.108 s / 3.014 s; build only, no upload |

Initial backend test attempts lacked system pytest, then lacked `app` on the import path. The final command above uses an isolated uv dependency environment and explicit `PYTHONPATH=backend`; no backend code changes were necessary. Frontend installation warned that esbuild's install script was blocked; the build nevertheless passed. Dependency vulnerability auditing was not part of these checks.

## Integration blockers, in order

1. **A and B do not share a wire contract.** A uses JSONL host handshake/events and magic `0xa5`, kind at offset 2, sequence at 8, persisted B boot at 12, encrypted unicast and a 1500-ms stale policy. B expects `F <hex>` / `EV ...` serial lines and magic `0xa7`, node at 2, boot at 8, sequence at 12, unencrypted radio and a 3-second stale policy. A treats boot IDs as monotonic; B uses random boot IDs. Both call their protocol v2, but they cannot interoperate unchanged. Coordinate one codec, host adapter, lifecycle and provisioning policy; update firmware, fixtures, tools and docs together. See [A contract](contracts/serial_protocol.md) and [B contract](hardware/PROTOCOL.md).
2. **The catalogs and masks are different configurations.** Web backend: six services, 14 kW source, 6/8-kW feeders, separate hospital/classroom indicator mapping. B classroom bench: 6/6/4-kW rooms, 16-kW normal / 6-kW shortage. Earlier required-ML plan: nine services, 84-kW demand, 100-kW normal. Do not combine their arithmetic or service masks. Agree one application catalog and explicit physical projection before connecting the controller. The web allocator is greedy; planned exact enumeration/CP-SAT parity is not implemented evidence.
3. **RFID semantics differ.** Web app tracks one selected classroom plus a separate load event; unknown cards clear selection (covered by current API tests). Hardware bench retains multiple registered rooms and ignores unknown cards. Neither behavior should be silently substituted for the other. Align selection, registration and simulated load-event behavior with the intended judge script, then update shared tests.
4. **Required ML is pending.** Train/evaluate the small tabular classifier with independent labels and grouped splits; expose ACTIVE/INACTIVE/UNKNOWN and provenance. Preserve fixed critical priorities and hard constraints. The remote remaining plan does not remove the user's explicit trained-ML requirement. Adapt features/catalog IDs after item 2; do not describe the prediction-file hook as a trained classifier.
5. **One live authority is still missing.** The web GridState and B bench controller own separate state. Connect hardware events and confirmed ACKs to the backend rather than running competing controllers. Backend currently reports hardware NOT_CONNECTED and unconfirmed outputs honestly.
6. **Physical acceptance remains.** Verify A flashing, reader/cards/buttons, B LED wiring, paired radio, boot/reconnect/loss recovery and current-session ACK identity. The prior B USB log verifies reported masks, not visible light output. Then perform three mounted end-to-end rehearsals.

## Next practical milestones

- Freeze one shared protocol and resolve catalog/interaction choices; add a cross-implementation fixture test before another firmware handoff.
- Bring up A locally and enroll cards privately; wire B's classroom LEDs with individual resistors and verify 8/16/32/24/56.
- Connect the single backend authority through A to B and record a real card → simulated load → matching physical ACK flow.
- Train and integrate required ML, validate constrained decisions and recovery, then rehearse the judge demo.

Detailed two-person physical phases remain local at `/home/bread/blackout-mesh-local/HARDWARE_IMPLEMENTATION_PLAN.md`. Reuse research, judge critique, notice drafts, device credentials and historical plan archives remain outside the uploaded document set. No connected-device queries, flashing, browser QA or fresh physical tests were performed during this sync.
