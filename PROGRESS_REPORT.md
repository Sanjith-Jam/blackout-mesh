# Blackout Mesh — progress report

Updated 2026-10-09. Repository synchronization combines remote main through `f2edb91` with local ESP32 A work through `0aa4210`. The histories are merged without rebasing or discarding either implementation. This is a component-level prototype; end-to-end readiness is not established.

## Restore of main and #4 + #19 integration — 2026-10-10

`main` was force-pushed three times on 2026-10-09/10 (19:05, 19:21, 19:31 UTC), which removed the merges of #27, #28 and #29 and Sanjith's planning docs. This restore merges them back on top of current `main`, together with #4 (telemetry diagnosis), #20 (allocation benchmark) and #18 (diagnosis benchmark). The two diagnosis layers are combined: `app/diagnosis` validates envelopes, keeps the rolling window, applies staleness and two-reading confirmation and separates shared upstream loss from a local supply loss using peer transformers; each reading is evaluated by the `app/diagnostics` multi-hypothesis engine (#19). Statuses are `NORMAL` / `FAULT_DETECTED` / `ALARM` / `ABSTAINED`. The campus diagnosis is telemetry-only, so a configured capacity limit is reported as `supply_constraint`, not as a `GRID_CAPACITY_SHORTFALL` hypothesis (the #19 campus test was updated accordingly). The diagnosis benchmark protocol moved to version 2 for the renamed outputs; held-out is still sealed.

## Simultaneous fault diagnosis & hypothesis ranking (BM-17 / #19) — 2026-10-10

Delivered the modular telemetry-derived diagnosis system in `backend/app/diagnostics/` resolving Issue #19:
- **Independent rule evaluators**: Overload, cooling failure, thermal stress, upstream loss, branch interruption run concurrently without an `if-elif` waterfall.
- **Simultaneous faults**: Overload and cooling failure co-occur in candidate hypotheses; shared-cause physical explanation attached without double-counting correlated temperature readings.
- **Deterministic ranking**: Severity tier primary (`CRITICAL` > `HIGH` > `MEDIUM` > `LOW`), heuristic evidence score $[0.0, 1.0]$ secondary. Explicitly labeled as an uncalibrated heuristic score, not a probability.
- **Diagnostic abstention**:
  - `CONTRADICTORY_EVIDENCE`: catches powerless current ($V=0\text{V}, I>10\text{A}$) and physical temperature limits ($T<-30^\circ\text{C}$ or $T>250^\circ\text{C}$).
  - `INSUFFICIENT_TELEMETRY`: scoped evaluation ensures missing current does not silence valid cooling failure evidence; complete absence abstains with enumerated missing sensors.
  - `INDISTINGUISHABLE_CAUSES`: normal input with zero output and zero current returns candidate set (`SECONDARY_BREAKER_OPEN`, `PRIMARY_FUSE_BLOWN`, `SEVERED_DOWNSTREAM_CONDUCTOR`) with actionable `next_check_needed` instead of guessing.
- **Campus & hospital integration**: Hospital visualizer delegates to the new engine; campus `GridState` emits structured candidate hypotheses without plain string concatenation.
- **Frontend UI**: `HospitalDemo.tsx` renders multi-hypothesis badges with heuristic scores and explicit abstention warning callouts.
- **Verification**: 42 backend tests pass (`backend/tests/test_diagnostics.py` and existing test suite); frontend production build succeeds cleanly.

## Diagnosis benchmark infrastructure (#18) — 2026-10-10

- `backend/benchmarks/diagnosis/PROTOCOL.md` (`diag-bench-protocol-1`) was written before any evaluation: 12 families (normal, demand-change and hot-ambient distractors, overload, cooling failure, simultaneous overload + cooling, shared upstream loss, local branch interruption, sensor dropout, stuck sensor, delay/reorder, recovery chatter), metrics and sealing rules. Process label: **developer-held-out**, because there is no independent custodian.
- `fixtures.py` generates dev / calibration / held-out bundles (48 scenarios each, 32 steps x 3 transformers) from disjoint parameter regimes (overload level, hot temperature, noise, delay, seeds) — never random rows of one trajectory. Observation bundles and truth are separate committed files with SHA-256 hashes in `data/manifest.json` (stored without line-ending conversion). Bundles contain no label fields or family names; IDs are opaque hashes.
- `runner.py` feeds envelopes in arrival order to a detector and asks for a diagnosis every step; an audit hook raises `LeakageError` if a truth file is opened while a detector runs. `evaluate.py` joins predictions to truth afterwards: per-family recall, precision, false alarms and rate, time to detect, location errors, coverage, correct abstentions, safety violations, and the list of missed scenarios, all with denominators. Held-out truth is not read without `--unseal`, and unsealing is logged to `data/UNSEALED.log`. **Held-out has not been run.**
- Development runs only (`results/diagnosis_dev.md`, `diagnosis_calibration.md`) with the #4 telemetry detector: every fault family is detected on dev except `stuck_sensor` (a frozen current reading hides a real overload: 0/4 dev, 2/4 calibration, with 78 / 69 safety-violation steps). Calibration noise adds a few safety-violation steps on hot-ambient and cooling-failure. These are kept in the report.
- Validation: 6 tests in `test_diagnosis_benchmark.py` (fixtures match the manifest and regenerate identically; no labels in bundles; regimes and seeds disjoint; an oracle-contaminated detector is stopped by the leakage guard and a label-sniffing one finds no labels; held-out stays sealed; the evaluator keeps misses and counts safety violations, and a perfect predictor scores full recall).
- Limits: synthetic telemetry; one detector adapter so far (the #19 multi-hypothesis engine can be added as a second adapter once the two diagnosis layers are merged); calibration has now been used, so it is development data.

## Allocation benchmark against fair baselines (#20) — 2026-10-10

- `backend/benchmarks/allocation.py` + `run_allocation.py` (`alloc-bench-2026-10-10.1`). Seeded 40-minute timelines at 5 s steps for 7 scenarios (6 kW and 4 kW shortage, feeder A loss, feeder B loss, 2 kW insufficient-critical supply, zero supply, 6 kW recovery chatter) x 5 seeds. Rooms are booked in 5–20 minute blocks; about 30% of booked sessions are actually empty, which is what activity evidence can distinguish.
- Policies on identical inputs, feasibility limits and restoration gate: fixed priority, essentials-first without ML, round-robin, the proposed path (classifier -> ActivityGuard -> exact allocator) with perfect / validation-rate / heavy-error classifiers, an always-UNKNOWN no-ML ablation, and an oracle-occupancy upper bound that is labelled not deployable. Classifier error rates come from the validation confusion matrix in `backend/models/manifest.json`.
- Outcome metrics are computed by an evaluator that alone sees true occupancy: critical and essential unmet Wh (power integrated over simulated time), occupied-room service fraction, worst-room starvation, switching count, recovery latency, constraint violations, with step and second denominators. The report includes paired per-seed differences against every policy.
- Result (`backend/benchmarks/results/allocation_report.md`, 280 runs, 0 constraint violations): under the 6 kW shortage the proposed policy with validation-rate errors serves occupied rooms 85.4% of the time vs 84.9% for essentials-first/no-ML and 61.8% for fixed priority (oracle 85.8%), but switches loads ~3x more (20.6 vs 6.6 per run) and leaves more booked-room essential demand unmet (220 vs 205 Wh) because it deprioritises booked-but-empty rooms. With heavy classifier errors it falls to 81.3% and 59 switches. In 4 kW shortage, feeder loss and zero supply all policies tie: there is nothing left to rank. Critical shortfall under feeder A loss / 2 kW / zero supply is counted, identical across policies.
- Validation: 5 tests in `test_allocation_benchmark.py` (hand-computed Wh fixture, deployable policies never read truth and share one input digest, allocator optimal for protected service on 300 random small cases, zero unsafe allocations with unavoidable critical shortfall counted, determinism and denominators).
- Limits: synthetic occupancy and bookings; classifier errors are sampled per reading from aggregate rates, so temporal error correlation is not modelled; the switching cost of ML ranking suggests adding hysteresis on optional changes.

## Telemetry-derived fault diagnosis (#4) — 2026-10-10

- New boundary: `app/simulation/sensors.py` is the only code that knows scenario names and fixture values; it turns hidden truth into timestamped observation envelopes. `app/diagnosis/` (`observations.py`, `infer.py`) accepts only those envelopes plus configured ratings/topology. A test parses the diagnosis package and fails on any import of simulation, state, site, visualizer or app modules.
- Envelopes carry asset, quantity, unit, value/None, observed/received time, sequence, quality and provenance. Unknown assets, unknown quantities, wrong units, non-finite or out-of-range values, naive or future timestamps are rejected; out-of-order samples are dropped.
- Hypotheses (overload, shared upstream loss vs local branch interruption, cooling failure, high temperature) are INFERRED only after two consecutive agreeing readings; one reading is an observation ALARM; missing or stale (> 3 s) evidence makes the result ABSTAINED with the reason. Results list supporting and contradicting evidence, missing/stale sensors and affected assets, in likely-cause language.
- Campus: `GridState.compute_fault_diagnosis` now samples bus/feeder telemetry each tick and diagnoses from that window, instead of reading `source_capacity_w` / `feeder_available`. A configured capacity limit is reported as `supply_constraint` ("operating constraint, not a diagnosed fault"), never as fault evidence.
- Hospital zone view: transformer sensors are synthesized from served zone load and diagnosed through the same pipeline (previously hard-coded NORMAL). The scenario fixtures (`hospital_snapshot`, `HospitalTelemetry`) keep a rolling window and remain available for tests/benchmarks.
- Validation: 69 backend tests pass, including 18 in `test_diagnosis.py`: import boundary; relabelled scenarios with identical telemetry give identical diagnoses; same label with different telemetry follows the telemetry; cooling failure at normal current; overload without heat; hot with cooling OK is not called cooling failure; plausible demand rise within rating stays NORMAL; shared vs local supply loss; single-sample alarm; dropout, missing upstream voltage and stale abstention; envelope validation; out-of-order samples; campus feeder trip alarm-then-confirm; capacity limit is not a fault. Frontend build passes.
- Limits: threshold rules, not a trained diagnostic model; voltage/current/temperature cannot uniquely identify every fault; simultaneous-fault ranking is #19; synthetic sensors only.

## One site authority, first step (#3) — 2026-10-10

- `backend/app/core/site.py` adds `SiteAuthority`, which owns the campus `GridState`, the classroom view and the hospital fixtures. Every POST route goes through `site.command()` / `site.commit()`, which applies the change, ticks all parts in a fixed order (campus first) and returns a receipt. The control loop ticks the site, not the parts. Every projection (`/api/v1/snapshot`, both visualizers, the WebSocket) carries `site = {run_id, revision, profile, catalog_version}`, and a single command updates all three under one revision. The pages show the run and revision in their headers.
- `docs/CATALOG_MIGRATION.md` inventories every ID, load, feeder, room mapping and route command. Classroom appliances are declared as the leaves of L3/L4/L5 (2,000/2,000/4,000 W = 8,000 W = feeder B); `reconcile_catalog()` refuses to start if they disagree.
- Coupling: the classroom view allocates within `min(classroom limit, campus feeder B headroom)`, so a campus shortage or feeder B trip reaches `/classrooms` in the same revision. The slider stays a named sub-budget (`classroom_limit_w`), and the page says when the campus is the binding limit. Hospital scenario/zone globals became a `HospitalFixtures` part.
- `backend/tests/conftest.py` resets the whole site before each test, because the campus singleton previously leaked state between test files.
- Validation: 51 backend tests pass, including `test_site.py` (leaf reconciliation, one-command cross-route identity, feeder B trip, shortage bound, multi-scan shortage, slider still binding, hospital revision, reads never bump the revision). Frontend build passes. Live check: campus capacity 9,000 W showed "Classroom supply 6,000 W · Limited by campus feeder B" with the same run/revision on all three pages.
- Remaining for #3 (listed in the migration doc): L3–L5 are still decided as whole rooms by the campus allocator while the classroom view decides appliances (same budget, two decisions); campus RFID/load sessions and classroom scans are separate stores (#21); hospital transformer fixtures are not mapped to L0–L2; `GridState` is still a singleton (#11).

## Hard safety limits on occupancy predictions (#22) — 2026-10-10

- `backend/app/core/safety.py` (policy `safety-2026-10-10.1`) defines protected demand independent of ML output and RFID: campus L0/L1 critical circuits and each classroom's lighting + computers. Predictions only reorder optional service.
- `ActivityGuard` turns failed, missing, malformed or out-of-range inference into UNKNOWN with a visible reason, and requires two consecutive distinct INACTIVE readings before a room is ranked INACTIVE; upgrades apply immediately and any non-INACTIVE reading restarts confirmation. Stale campus evidence (> 600 s) is UNKNOWN with a guard reason.
- The campus allocator no longer sheds a requested room only because it is predicted INACTIVE: INACTIVE ranks last but is served whenever capacity allows (this replaces the previous "inactive rooms can be deliberately left unserved" behaviour).
- Both authorities report `safety` with `FEASIBLE` / `PROTECTED_SHORTFALL`, requested/served/shortfall watts and the declared fallback order. The classrooms page shows the status and each room's guard reason.
- Validation: 44 backend tests pass. `test_safety.py` checks all 27 activity combinations x 29 capacities x 4 feeder states x 8 room-request sets for the campus (protected served whenever feasible; no fitting room left unserved) and 27 x 8 scan sets x 41 capacities for the classroom demo (essentials always served at >= 2,100 W, quantified shortfall below). The two campus property tests fail against the previous allocator. Frontend build passes.
- Limits: campus classroom services are still indivisible 2/2/4 kW aggregates, so their essential minimum can only be protected by not shedding the whole room; decomposing them is #3. No manual override path exists yet, so none can bypass limits. Modeled policy only, not certified protection.

## Background control loop and read-only reads (#9, #10) — 2026-10-10

- One `ControlLoop` (`backend/app/core/control_loop.py`), started and awaited in the FastAPI lifespan, ticks the campus `GridState` and the classroom demo every 250 ms whether or not any browser is connected. It counts overrun (skipped, not replayed) ticks and errors; `GET /api/v1/health` reports `control_loop` health.
- `GridState.tick()` and `ClassroomDemo.tick()` are the only places where evidence freshness, replay cursor, inference cache, allocation and staged restoration advance. `build_snapshot()` / `snapshot()` return a copy of the last published state. Unchanged state keeps the same `generated_at` and `published_revision`; socket messages add a separate `sent_at`.
- Commands tick immediately, so protective shedding appears in the same response; restoration still waits for the 5 s stability / 3 s dwell / one-load-per-second gate.
- Validation: 35 backend tests pass (`PYTHONPATH=backend .venv/Scripts/python -m pytest backend/tests -q --ignore=backend/tests/test_activity_model.py`; that file imports the Unix-only `resource` module and is not collectable on Windows). New tests fingerprint domain state across 100 reads of every route, compare a 10-second virtual-time shortage/recovery timeline with 0 and 100 readers per tick, check loop single-ownership, overrun counting, error survival and lifespan shutdown. Frontend production build passes with the existing large-bundle warning.
- Limits: `GridState` is still a process-wide singleton (#11), and campus, classroom and hospital remain separate authorities (#3). The hospital route is a pure function of its selected scenario, so it has no time-based state to tick.

## Pending implementation backlog — 2026-10-10

Created an exhaustive [implementation plan](PENDING_IMPLEMENTATION_PLAN.md) for the 24 requested software problems: 7 P0, 14 P1 and 3 P2. It records the inspected baseline `d1c58d7`, six delivery phases, a checked acyclic dependency graph, acceptance criteria and verification instructions. Library roles cover SQLModel/SQLite, NetworkX, TanStack Query, Zustand and an evidence-based pandapower/Power Grid Model comparison; OR-Tools is conditional on allocator scale. GitHub issue links are in the plan. This documentation update does not resolve those issues or add physical hardware evidence.

## Classroom and hospital visualizers — 2026-10-09

This update preserves the original light graph-paper theme and supersedes earlier descriptions of the demo routes. Three Luna workers implemented the initial endpoints/views; a further Luna worker replaced the rejected classroom node graph with a physical floor-plan renderer under parent review.

- Classroom: after user feedback, replaced the large stacked blueprint drawings with one compact tiled game-style map: three rooms, small equipment sprites, shared amber supply bus and bright moving current pulses. Cut branches are gray and stop. The separate catalog requests 8,000 W. After scanning CR1 and applying the 3,400-W preset, CR1 receives all 2,000 W and each other room receives 700 W of essential computers/lighting. Optional devices are shed with stopped paths. Restoration uses the existing time gate; unmet demand stays visible.
- Hospital: separate three-transformer topology, current/temperature/input/output/cooling readings and evidence-based likely-cause explanations. Overload/cooling/missing-sensor fixtures affect TX2; upstream loss affects all three. No invented transformer model accuracy; diagnosis is threshold-based and reads only sensor observations.
- Original dashboard: explicit React Flow dimensions fix hidden nodes; browser inspection confirms 9 visible nodes and 8 edges.
- Validation: 26 backend tests pass, including request validation, allocation behavior, diagnosis, isolation and time-based restoration. Production build passes with the existing large-bundle warning (~1.54 MB JS). Browser scenario checks and responsive-verification limits are recorded locally under `/home/bread/blackout-mesh-local/visualizers/`.

No new physical hardware evidence or transport integration. Local plans/reuse recommendations remain private and unchanged.

## UI correction — 2026-10-09

The user rejected the visual redesign. Restored the original landing page, dashboard, routes and styles from `aafaebc`. ML training artifacts, APIs, allocation and tests remain intact; model/replay presentation is available through the API, pending user-defined classifier visuals. The frontend build passes with the original large-bundle warning. The software delivery UI descriptions below are historical.

## Software delivery update — 2026-10-09

Hardware is paused at the user's request. This update supersedes the historical software status below; historical firmware evidence is retained and has not been rerun.

| Area | Delivered | Limit |
|---|---|---|
| Classifier | Trained StandardScaler/logistic model, manifest hash, independent date groups, RF/TabICL/rule comparison, measured CPU latency | Office occupancy proxy; later-day test exploratory and generalization weak |
| API | Validated observations, model status, start/pause/reset replay, live snapshots | Local single-worker demo; no production authentication |
| Allocation | All 64 masks searched for six services; critical protection, feeder/source limits, UNKNOWN handling | Explicit software policy places ACTIVE/UNKNOWN classrooms before water pump |
| Restoration | Immediate shedding; stable capacity/feeders for 5s, 3s off dwell, at most one new ON/sec | Simulated only |
| Website | Landing page, animated topology, sensor evidence, priority trace, model metrics, policy comparison and fault controls | Three virtual rooms reuse observations from a single office dataset |
| Physical hardware | NOT_CONNECTED and null confirmed outputs | A/B transport and physical acceptance remain unresolved |

The six-service catalog remains L0/L1 critical 2/1 kW, L2 water 3 kW, L3/L4 classrooms 2/2 kW, L5 classroom 4 kW, 14-kW source and 6/8-kW feeders. Historical nine-load and bench catalogs are separate configurations.

Current software verification: **21 backend/model tests passed**, frontend production build passed (217.42-kB JS / 70.07-kB gzip), real-model HTTP/WebSocket flow, 5-kW active-room allocation, feeder trip/recovery, zero-capacity shortfall and responsive browser checks at 375/1440 pixels passed. Full evidence is documented in the local delivery report. See `backend/models/MODEL_REPORT.md` for exact ML denominators and reproducible commands. No hardware commands were run for this update.

## Historical synchronization evidence

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
2. **The catalogs and masks are different configurations.** Web backend: six services, 14 kW source, 6/8-kW feeders, separate hospital/classroom indicator mapping. B classroom bench: 6/6/4-kW rooms, 16-kW normal / 6-kW shortage. Earlier required-ML plan: nine services, 84-kW demand, 100-kW normal. Do not combine their arithmetic or service masks. Agree one application catalog and explicit physical projection before connecting the controller. The software update now implements exact enumeration for the six-service catalog; physical catalog reconciliation remains pending.
3. **RFID semantics differ.** Web app tracks one selected classroom plus a separate load event; unknown cards clear selection (covered by current API tests). Hardware bench retains multiple registered rooms and ignores unknown cards. Neither behavior should be silently substituted for the other. Align selection, registration and simulated load-event behavior with the intended judge script, then update shared tests.
4. **Historical ML blocker (software implementation now delivered).** Train/evaluate the small tabular classifier with independent labels and grouped splits; expose ACTIVE/INACTIVE/UNKNOWN and provenance. Preserve fixed critical priorities and hard constraints. The remote remaining plan does not remove the user's explicit trained-ML requirement. Adapt features/catalog IDs after item 2; do not describe the prediction-file hook as a trained classifier.
5. **One live authority is still missing.** The web GridState and B bench controller own separate state. Connect hardware events and confirmed ACKs to the backend rather than running competing controllers. Backend currently reports hardware NOT_CONNECTED and unconfirmed outputs honestly.
6. **Physical acceptance remains.** Verify A flashing, reader/cards/buttons, B LED wiring, paired radio, boot/reconnect/loss recovery and current-session ACK identity. The prior B USB log verifies reported masks, not visible light output. Then perform three mounted end-to-end rehearsals.

## Next practical milestones

- Freeze one shared protocol and resolve catalog/interaction choices; add a cross-implementation fixture test before another firmware handoff.
- Bring up A locally and enroll cards privately; wire B's classroom LEDs with individual resistors and verify 8/16/32/24/56.
- Connect the single backend authority through A to B and record a real card → simulated load → matching physical ACK flow.
- Train and integrate required ML, validate constrained decisions and recovery, then rehearse the judge demo.

Detailed two-person physical phases remain local at `/home/bread/blackout-mesh-local/HARDWARE_IMPLEMENTATION_PLAN.md`. Reuse research, judge critique, notice drafts, device credentials and historical plan archives remain outside the uploaded document set. No connected-device queries, flashing, browser QA or fresh physical tests were performed during this sync.
