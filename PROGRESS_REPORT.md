# Blackout Mesh — progress report

## GNITC synthetic district demo — 2026-10-10

Delivered `/grid` with shared SHIFT, Energy, Self-healing and Transformers views over the Python-owned district API. Generated wires and district demand, PV, storage, faults and restoration are simulated; cached geography is attributed and does not establish real feeder topology. The pinned CityLearn source was exercised in an actual run: hour 12 shows 8,900 W local PV for 7,400 W demand plus 1,500 W battery charging; hour 17 shows 1,800 W local PV, 1,500 W battery discharge, 4,300 W grid import and 7,600 W gross demand.

Focused evidence: district backend tests **12 passed**; DistrictMap frontend test **1 passed**; frontend production build passed; generated OpenAPI and TypeScript schemas are synchronized. An isolated live UI/backend rehearsal (frontend 5175, backend 8001) at hour 20 showed 6,200 W scheduled/requested, 6,000 W grid served and 200 W unmet. A simulated line fault produced 5,166 W served and 1,034 W unmet. Per-load requested = served + unmet, and edge flows remained within declared limits. These values are simulated.

The full suites and hardware/physical acceptance were not run; no held-out test was unsealed. Hardware remains paused. Next step: review district acceptance against `docs/planning/GNITC_DISTRICT_MVP_PLAN.md`, then resume physical A/B integration only when hardware work is scheduled.

## Issue #15 cleanup — 2026-10-10

Removed three empty `.gitkeep` placeholders, pinned backend runtime/test dependencies from a clean Python 3.14 install (195 passed, 2 skipped) and fixed the stale `--with httpx` test command in `AGENTS.md`. Every other script and both firmware trees have callers and stay. Inventory and evidence: [docs/ISSUE_15_DELIVERY.md](docs/ISSUE_15_DELIVERY.md).

## Person A sprint: evidence and backend — 2026-10-10

Answers to the adversarial review, in five commits on `claude/peaceful-volta-r0k5cd`:

- **One facility model (A3).** Hospital equipment are the leaves of campus feeder A: L0 2,000 W and L1 1,000 W (all essential), L2 3,000 W (optional; renamed Water Pump & HVAC). `reconcile_catalog()` checks sums and tiers at startup. The hospital view allocates within the feeder A watts the campus served, so a shortage or feeder A trip reaches `/hospital` in the same revision. The hospital limit is now 0–6,000 W (4,000 W overload preset).
- **Fault injection (A4).** `inject_fault` / `clear_fault` on `POST /api/v1/visualizers/hospital` keep an overload, cooling failure, both, upstream loss, sensor dropout or stuck sensor until cleared or reset; the old `scenario` field aliases it. Diagnosis still reads only telemetry produced by `sensors.apply_fault`.
- **Stuck sensors (A2).** A current reading repeated exactly on 3 readings while temperature moves ≥ 3 °C with cooling OK latches `SUSPECTED_STUCK_SENSOR` until the reading changes; with no other hypothesis the result abstains instead of NORMAL. Live hospital telemetry has small deterministic noise. Diagnosis benchmark stuck_sensor: dev 0/4 → 4/4 (85 → 0 safety-violation steps), calibration 0/4 → 4/4 (73 → 0). Held-out has been unsealed twice (`UNSEALED.log`): at 00:57 UTC on main (#45) with the earlier detector (stuck_sensor 2/4, 63 violation steps), and at 01:09 UTC with this frozen detector, written without seeing the earlier held-out result. Committed results are the second run: every family detected; stuck_sensor 4/4 with 0 violations; 59 violation steps remain in near-threshold overload/temperature, delay and chatter cases (`backend/benchmarks/diagnosis/results/diagnosis_heldout.md`). No retuning after unsealing.
- **ML switching (A1).** `RankDwell` holds a room's ranking state until a changed state repeats on 3 readings (value fixed before measuring). Allocation benchmark `alloc-bench-2026-10-10.2`, 385 runs, 0 constraint violations. 6 kW shortage with validation-rate classifier errors: switches 20.6 → 15.0 (no-ML 6.6), occupied service 85.4% → 85.2% (no-ML 84.9%, oracle 85.8%), essential unmet 221.9 Wh vs 205.1 Wh without ML. Heavy errors: switches 59 → 21, service 81.3% → 83.0%. Recovery chatter: 94.9% vs 91.0% without ML, 51.6 vs 48.4 switches. Interpretation: in this benchmark even perfect occupancy adds < 1 point in a steady shortage, so the pitch should lead with protected, explained allocation and treat ML as optional ranking.
- **CI (A5).** The workflow now runs the whole backend suite, not only the fixture contract test.

Verification: `PYTHONPATH=backend uv run --no-project --python 3.14 --with-requirements backend/requirements-test.txt --with-requirements backend/requirements-ml.txt python -m pytest backend/tests -q` — **173 passed, 2 skipped** (electrical engine not installed). Frontend `npm run build` and `npm test` (15 tests) pass. No browser, Playwright e2e or hardware run in this sprint. Person B's UI work (fault buttons, one-story page, simple-vs-ours panel) is not part of these commits.

## PR #38 conflict resolution — 2026-10-10

Merged current main (`6b2feaf`) into `feature/bm-fixes`. Preserved the evaluated logistic artifact and ML requirements, telemetry-derived diagnosis, protected allocation policies, read-only projections, background control loop, electrical-study boundary and evidence-backed classroom/hospital drawings. Integrated per-application lifecycle/storage, configurable inventory, generated OpenAPI/TypeScript contracts and the shared TanStack/Zustand WebSocket connection. Publication ordering uses `published_revision`; duplicate heartbeats remain fresh and older HTTP snapshots cannot replace newer same-run cached data.

SQLModel 0.0.22 failed on the project's Python 3.14 runtime; installed and tested 0.0.48. Each app owns its SQLite engine and shuts down its control/replay tasks. Simulation ACKs are saved without confirming physical LEDs; physical ACKs remain rejected until a validated command/session protocol is provisioned.

Verification: **133 backend tests passed**, including independent app instances, main route/WS envelope checks, SQLite audit records surviving restart and simulated ACK separation. Frontend production build passed; generated API schema/types are synchronized. Existing large-bundle warning remains. No browser interaction or physical hardware acceptance was run. Incident lifecycle/history replay and complete generated typing/runtime validation remain follow-up work; the PR does not establish production or hardware readiness.


Updated 2026-10-09. Repository synchronization combines remote main through `f2edb91` with local ESP32 A work through `0aa4210`. The histories are merged without rebasing or discarding either implementation. This is a component-level prototype; end-to-end readiness is not established.

## Hardware integration: board A + board B + website — 2026-10-10

- **One contract.** Board B's firmware was rewritten to board A's contract v2 (0xA5 frames, persisted boot counter, SYNC-bound session, increasing sequence numbers, cached duplicate ACKs, conflicting/stale/wrong-session rejection, 400 ms heartbeats, encrypted ESP-NOW with PMK/LMK and peer allow-list, 1.5 s stale link LED). Its `protocol.h` is a byte copy of board A's, enforced by a test. The earlier B-only bench protocol and host tools were removed.
- **Board A buttons.** A fifth button (GPIO 33) is the RFID-fail fallback: it sends the same `START_SESSION` room A event a card would, with a `fallback_room_a` status. The existing SIMULATE SHORTAGE and RESTORE buttons are the "deprived of kW" and "normal" buttons. `pio run -d firmware -e esp32-a` builds.
- **Laptop bridge.** `backend/app/hardware/gateway.py` implements the host side of the USB contract (hello → sync → 500 ms pings, event acknowledgement, radio_sync then set_loads, CONFIRMED-only LED confirmation, re-handshake after reset/stale/reboot). Events map to site commands: card/fallback → scan room, END → unscan, SHORTAGE → 3,400 W preset, RESTORE → 8,000 W, RESET → reset. Board B lights a room's LED when that room has a session and all its loads are served. Start with `BLACKOUT_GATEWAY_PORT` or POST `/api/v1/hardware/connect`; `GET /api/v1/hardware` reports state; `/demo` shows the physical link and confirmed mask.
- **Website.** The Classrooms page has a "Physical boards" panel: link, card-reader health, board B binding, per-room LED commanded vs confirmed, last input, and a connect box.
- **Guide.** `docs/ESP32_A_CONNECTION_GUIDE.md` covers parts, reader and five-button wiring, pairing secrets, card registration, flashing, running and a test table including RFID failure.
- **Validation.** 106 backend tests pass, including `test_gateway.py` (8 end-to-end tests with a contract-following fake board A and B: handshake, fallback lights room A and is confirmed, deprived/normal change the LEDs, reset re-handshakes, reader fault visible, B reboot forces resync, campus snapshot reports the link, invalid events rejected) and `test_hardware_files.py`. Both firmwares compile; the frontend builds.
- **Not yet verified on hardware.** Neither board was connected during this work, so flashing, radio pairing and the physical test table remain to be run. Board A's host C++ tests need `g++`, which this Windows machine does not have.

## Evidence-backed power-path graphics (#23) — 2026-10-10

- `backend/app/core/edges.py` defines one canonical edge per drawn wire (supply → bus → room/transformer → appliance, plus campus source → feeder → service). Each edge separates topology (`connected`), the allocator command, the modeled applied state after staged restoration, physical confirmation (`NOT_CONNECTED`, no hardware) and, for hospital transformers, observed simulated-sensor voltage with an explicit "no measured branch current" note. States: `ENERGIZED`, `PENDING_RESTORATION`, `SHED`, `OPEN` (no path from the supply) and `UNKNOWN` (diagnosis abstained or no reading). Watts carry unit `W` and provenance `MODELED`. Every edge has a reason, including why a shed load did not fit.
- The classroom and hospital views and the campus snapshot publish `edges`; view snapshots publish `generated_at`, which only changes with `published_revision`.
- Frontend: one `PowerWire` component draws every wire from its edge (`data-edge-id`, `data-state`, hover text with the evidence). Only `ENERGIZED` edges animate, and only while the live feed is connected; restoring/shed/open/unknown have distinct line styles and text labels in the legend and ledger, a stale connection is labelled, reduced motion stops all animation, and a footnote says watts are modeled and pulse speed is decorative.
- Validation: 96 backend tests (6 new in `test_edges.py`: one edge per load matching its state, no flow across an open feeder on classroom and campus, pending restoration not shown as energized, shed edges explain why, hospital observed voltage kept separate and abstained evidence is UNKNOWN, `generated_at` stable across reads). Frontend build passes. Live: 20/20 classroom wires and 19/19 hospital wires mapped to edges; a campus feeder B trip turned all 20 classroom wires OPEN with no animation.
- Limits: allocation view only; an electrical-study view with solver-derived voltage/current depends on #7. The campus React Flow graph does not yet render the new campus edges.

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

Created an exhaustive [implementation plan](docs/planning/PENDING_IMPLEMENTATION_PLAN.md) for the 24 requested software problems: 7 P0, 14 P1 and 3 P2. It records the inspected baseline `d1c58d7`, six delivery phases, a checked acyclic dependency graph, acceptance criteria and verification instructions. Library roles cover SQLModel/SQLite, NetworkX, TanStack Query, Zustand and an evidence-based pandapower/Power Grid Model comparison; OR-Tools is conditional on allocator scale. GitHub issue links are in the plan. This documentation update does not resolve those issues or add physical hardware evidence.

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
3. **Firmware contracts remain separate.** The software routes now normalize RFID, classroom-view, and simulated board events into the same multi-room `GridState.active_sessions`; duplicate event IDs, stale timestamps and old-run events are bounded/rejected. The existing A/B wire protocols still differ and have not been physically reconciled. See `docs/ISSUE_21_DELIVERY.md` for the software compatibility table and test evidence.
4. **Historical ML blocker (software implementation now delivered).** Train/evaluate the small tabular classifier with independent labels and grouped splits; expose ACTIVE/INACTIVE/UNKNOWN and provenance. Preserve fixed critical priorities and hard constraints. The remote remaining plan does not remove the user's explicit trained-ML requirement. Adapt features/catalog IDs after item 2; do not describe the prediction-file hook as a trained classifier.
5. **One live authority is still missing.** The web GridState and B bench controller own separate state. Connect hardware events and confirmed ACKs to the backend rather than running competing controllers. Backend currently reports hardware NOT_CONNECTED and unconfirmed outputs honestly.
6. **Physical acceptance remains.** Verify A flashing, reader/cards/buttons, B LED wiring, paired radio, boot/reconnect/loss recovery and current-session ACK identity. The prior B USB log verifies reported masks, not visible light output. Then perform three mounted end-to-end rehearsals.

## Next practical milestones

- Freeze one shared protocol and resolve catalog/interaction choices; add a cross-implementation fixture test before another firmware handoff.
- Bring up A locally and enroll cards privately; wire B's classroom LEDs with individual resistors and verify 8/16/32/24/56.
- Connect the single backend authority through A to B and record a real card → simulated load → matching physical ACK flow.
- Train and integrate required ML, validate constrained decisions and recovery, then rehearse the judge demo.

Detailed two-person physical phases remain local at `/home/bread/blackout-mesh-local/HARDWARE_IMPLEMENTATION_PLAN.md`. Reuse research, judge critique, notice drafts, device credentials and historical plan archives remain outside the uploaded document set. No connected-device queries, flashing, browser QA or fresh physical tests were performed during this sync.


## Updates for BM-17 and BM-19
- **BM-19**: Unified session semantics across RFID and software routes. `GridState` now uses `active_sessions` instead of a single active room. RFID unscan is fully supported.
- **BM-17**: Added support for simultaneous faults, hypothesis ranking, and diagnostic abstention. `diagnose` logic now correctly evaluates all hypotheses and ranks them by score. Ambiguous conditions explicitly return abstention.
- **BM-12**: Added Pydantic models and explicit OpenAPI schema generation (`backend/scripts/export_openapi.py`), with `openapi-typescript` for generated UI contracts. WebSocket consumers check envelope shape and revision; full runtime JSON-schema validation and complete generated typing of visualizer routes remain pending.
- **BM-11**: Relocated WebSocket subscription management into a global application shell (`useWebSocketSync`), implemented capped backoff reconnects, added strict monotonic revision validation (discarding duplicate or stale updates), integrated TanStack Query as the single source of truth for snapshots, and used Zustand strictly for UI state.
- **BM-10**: Implemented durable persistence using SQLite (WAL) and `sqlmodel`. Audit tables cover Run, Command, Decision, Transition, Incident, Acknowledgment and Observation; run/decision/transition/observation and simulated acknowledgment writes are integrated. Full telemetry-derived incident opening/resolution remains pending. Added an API endpoint for simulated ACK history; unprovisioned physical ACKs are rejected and no physical confirmation is inferred. Designed resilient writes inside the core `GridState` instance lock to preserve authoritative history synchronously, falling back to a visible `DB_DEGRADED` degraded state if disk access fails.
## Issue #5 — temporal occupancy evidence (2026-10-10)

Delivered `backend/scripts/evaluate_temporal.py`, frozen `backend/benchmarks/occupancy/PROTOCOL.md`, machine-readable results and REPORT.md. Four rolling origins hold out complete days; data have no true room-session IDs. Validation-only gates, training-only preprocessing, duplicate/conflict checks and feature/artifact fingerprints are tested. Majority/rule/logistic/tree comparisons count UNKNOWN explicitly. Four-sensor logistic covered 40.0% overall with 121/2,094 false-INACTIVE occupied rows; its first evaluation block alone had 121/268 (45.1%). No candidate adopted, no calibration or campus-validation claim. Original model, manifest and replay retained; fresh independently labeled campus data remain unavailable. Reproduce with `.venv-ml/bin/python backend/scripts/evaluate_temporal.py --data /path/to/occupancy.zip`; see the report for full denominators, provenance, versions and resources.

## Issue #6 — configurable campus allocation (2026-10-10)

Delivered two named lexicographic policies through the API, with immutable protected-first constraints, UNKNOWN ordering, bounded optional waiting credit and switching penalty. Every campus load gets requested/proposed/applied status, constraints, shortfall, score contribution and a reason/counterfactual. Optimization inputs detach from live state; restoration replay includes pre-step gate state, timestamp, signature and order. Policy changes restart stability timing. Tests cover alternative optional choices, ties, open feeders, impossible capacities, fairness/request aging, replay, validation, unchanged idle traces and policy changes during restoration. The exact 64-mask runtime remains authoritative. A real 19-leaf scale probe is recorded in `backend/benchmarks/results/allocation_profile.json`: median 11.95 s across three runs, versus 1.59 ms over 50 six-service runs. Larger dispatch needs a separately bounded solver before use in the control loop. No solver timeout path was added because no external solver was adopted. Policy scope/limits and API examples are in `docs/ALLOCATION_POLICIES.md`.

## Issue #7 — explicit electrical boundary (2026-10-10)

Delivered an optional balanced AC study endpoint and matched pandapower/Power Grid Model benchmark. The normal demo remains explicitly watt-budget accounting; electrical studies cannot change allocation or authorize restoration. Inputs validate topology version, balanced applicability, switches, demand, PF and impedance. Results expose SI units, engine/version, provenance, convergence and independently checked power-balance residual; missing/islanded/failed outputs stay null. NetworkX supplies connectivity only. Solver measurements cross the existing telemetry validation boundary; diagnosis gets observations and ratings, never switch/scenario truth. Current exceedance is a one-sample alarm; thermal/earth-fault claims remain excluded.

The installed engines agree for normal, overload and open-branch cases within 0.01 V / 0.001 A / 0.1 W. Both fail the declared nonconvergence case without flowing-current output. Source-off produces a deenergized/no-solution result. Final warm single p95 on the measured host: PGM 3.23 ms versus pandapower 310 ms. PGM is the optional runtime dependency; pandapower stays in an isolated offline benchmark environment. Strict API validation, real-engine API round trip, conservation, missing readings, timeout/busy/stale results and control independence are tested. See `docs/ELECTRICAL_SIMULATION.md` for installation, license metadata, parameters, limitations, serial-batch timing and reproduction.

### Verification of the combined #5–#7 delivery

Final backend suite: **119 passed** via `PYTHONPATH=backend .venv-ml/bin/python -m pytest backend/tests -q`. Isolated Python 3.12 electrical suite: **16 passed** via `PYTHONPATH=backend .venv-electrical/bin/python -m pytest backend/tests/test_electrical.py -q` (dependency deprecation warning only). Frontend `npm run build` passed; the existing bundle-size warning remains. All three implementation areas are committed locally, with no push. Hardware and independent campus-room validation remain untested/unavailable; the shipped model and four-feature runtime were preserved. No 19-leaf live solver or thermal/protection physics was added.

## Prior art and novelty boundaries — BM-06 / Issue #8

Added `docs/NOVELTY_AND_PRIOR_ART.md` with a comparison to established methods and explicit scope limits. It clarifies that the current project does not demonstrate multi-hop mesh routing, campus-validated occupancy accuracy, real power switching or measured energy savings. The implemented diagnosis and allocation are prototype integration work; any performance-improvement or fairness claim needs defined external baselines and independent evaluation before presentation as a result.

## Issue #25 PR #36 integration — 2026-10-10

Integrated durable server history and read-only playback with current `main` while retaining the shared WebSocket/store and later hardware/UI changes. Backend SQLite history records events, incident open/resolve transitions, decisions and 1-Hz telemetry; charts and timeline recover from server history after reload. Historical playback displays saved snapshots and disables mutating controls. Recorder failures do not stop control. Verification: full backend suite **151 passed**; frontend build passed with existing bundle-size warning; package-lock dependency tree resolves. The focused jsdom frontend test could not run because jsdom is not installed and package downloads are blocked. The browser showed history controls but the pre-existing backend on port 8000 returned 404 for the new route, so no live browser/backend rehearsal is claimed. #25 remains open while blocking #12/#14 gates and the DOM test are unresolved. See `docs/ISSUE_25_DELIVERY.md`.

## Issue #14 — generated API contract (2026-10-10)

Implemented on the active follow-up branch. All HTTP operations now export request/success/error schemas; classroom, hospital, history, hardware, policy, and campus wire types are generated for TypeScript. Stable OpenAPI export, WebSocket envelope schema/runtime validation, malformed-message assertions, route coverage tests, and CI drift/build checks are included. Full backend suite: **153 passed**; frontend build and runtime contract tests pass. The browser DOM history test remains blocked by missing local `jsdom`; no hardware behavior was checked. See `docs/ISSUE_14_DELIVERY.md`.

## Issue #12 — durable SQLite audit and recovery (2026-10-10)

Completed on the active follow-up branch. Commands, decisions, transitions, incidents and ACKs survive restarts with UUID/revision identities. Duplicate simulated ACKs are idempotent; foreign run references are rejected; both state and replay-history databases have version tracking and integrity-checked online backup support. Storage failure is visible via health status. Raw RFID UIDs remain excluded. Physical ACKs remain disabled pending protocol provisioning. Verification and limitations: `docs/ISSUE_12_DELIVERY.md`.

## Issue #16 frontend regression coverage (in progress)

Integrated useful tests from the preserved `issue-16-frontend-tests` branch while keeping the current shared WebSocket/history architecture; its obsolete duplicate socket implementation was not restored. Added Vitest coverage for both facility visualizers and evidence-backed power edges, automated axe checks, generated API-shape fixture checks, and a Playwright navigation test for the separate classroom and hospital routes. Local checks pass (15 component tests, one browser test); issue closure is pending CI and remaining acceptance review.

## Current open-issue follow-up — 2026-10-10

- **#21 session semantics:** software UI, RFID and fake-board gateway events now use one room-session store and one requested-load state. HTTP session events are bound to the current run ID, event IDs are bounded/idempotent, stale and out-of-order timestamps are rejected, and new runs clear sessions. Focused backend checks passed **53 tests**. `docs/ISSUE_21_DELIVERY.md` records the compatibility table and software-only hardware boundary.
- **#19 diagnosis:** the frozen developer-held-out split was evaluated once and its denominators are published in `backend/benchmarks/diagnosis/results/diagnosis_heldout.{md,json}`. The results include stuck-sensor misses and safety violations. Ranked top-k metrics are not in the held-out artifact, so #19 remains open; do not retune against this revealed split.
- Verification at this point: backend suite **163 passed**; frontend build, contract, history and browser navigation checks passed. One frontend assertion about the session POST body was updated after adding run/event identity; the component suite is being rerun.

## Person B software demo and predictive demand — 2026-10-10

Delivered the `/demo` city story over the canonical six-service 14 kW model: one-revision source/hospital/classroom panels, event strip, per-cut reasons, selectable buildings, live fixed-priority versus exact-policy candidate outcomes and guided feeder/supply recovery. `/console` retains history/playback; equipment drill-downs remain available. Landing/README now use Blackout Mesh consistently and display measured JSON-backed 0.17 ms occupancy inference, 1.59 ms exact allocation, and 0 violations/280 simulated runs rather than placeholder percentages.

Added synthetic-trained Ridge demand forecasting: four previous requested-demand readings, six 10-second horizons, empirical synthetic error bands, warmup/freshness/shock abstention and explicit synthetic replay. Complete sessions are disjoint (80 train / 20 calibration / 20 test). 60-second synthetic test MAE: 149.49 W versus 469.59 W persistence across 1,420 windows/20 sessions. This is not a campus accuracy or outage-forecast guarantee; the advisory cannot dispatch or restore loads. The occupancy model is unchanged.

Hospital fault rehearsals cover overload, cooling, combined faults, upstream loss, dropout and stuck sensor. Ranked evidence and inspection instructions are visible; stuck current returns ABSTAINED and is labeled sensor-untrusted. Rehearsals are separate 100 A fixtures and do not mutate the live city. A4 persistent fault injection, A3 legacy 7 kW hospital-drill-down reconciliation, and A1 rank-dwell ablation remain backend dependencies. Current legacy results are shown openly, including switching costs.

Verification: **179 backend tests, 18 component tests and 2 Playwright browser tests passed**. The city browser test uses an isolated real backend, checks shortage reasons/shared revisions, forecast warning, feeder trip, critical shortfall, repair/staged restoration and 375 px layout. Frontend build, generated-client drift check, four history checks and runtime contract check pass. Existing bundle-size warning remains. No push by this task. B5 remains explicitly deferred: no board flashing, pairing, physical acceptance or hardware backup video. Gateway-reported values stay unknown when disconnected/stale; site/gateway lock ordering is regression-tested.

The README software GIF and [demo guide](docs/DEMO_GUIDE.md) provide the presentation handoff. Root implementation plans now live under [docs/planning](docs/planning/README.md), with references updated. Production databases were not used by automated checks.

### PR integration with main — 2026-10-10

Integrated main's A1 rank-dwell benchmark, A3 shared 6 kW hospital catalog and A4 persistent fault controls. Read-only diagnostic buttons now send an explicit `rehearsal` field; mixed rehearsal/live requests reject. Removed the duplicate stuck-sensor rule in favor of main's latched uncertainty and cooling-aware detection. Frozen ranked manifests/results retain their original detector identity; regression checks verify changed rules refuse unsealing rather than rewriting that provenance. No new held-out run was performed. README/demo guide now include the 385-run allocation evidence and rank-dwell comparison. Earlier pending A1/A3/A4 notes above are superseded by this integration. B5 remains on hold.

Validation: 197 backend tests passed against temporary databases; 18 frontend component tests, 4 history tests, runtime contract check, production build and 2 real-browser checks passed. Dependency audit found zero vulnerabilities. The existing frontend bundle-size warning remains. Publication requested by the user; no merge or hardware operation authorized by this update.

### #19 ranked held-out v3 — 2026-10-10

Ranked v2 could not be unsealed (frozen against a detector that changed before it ran). Froze `diag-bench-ranked-v3` (seeds 5000–5007) against the current detector, committed it, then unsealed it once. All fault families detected 8/8 with zero safety violations; top-1/top-3/MRR 1.0 on all 80 ranked cases; dropout and stuck-sensor abstention precision/recall 1.0 (8/8 each). Results in `backend/benchmarks/diagnosis/results/diagnosis_ranked_v3_heldout.{md,json}`; details in `docs/ISSUE_19_DELIVERY.md`. This supersedes the earlier "keep #19 open" notes. Synthetic, developer-held-out only.

## Configurable site profiles (#26) — 2026-10-10

- Delivered: strict Pydantic site profile (`app/core/config.py`) with topology, unit and parent/leaf watt checks reported per asset; hospital equipment, presets, LED bits and board A room letters moved from Python constants into `default_campus.json`; a second site (`small_test_site.json`) runs from configuration only; config hash recorded in snapshot identity, view identity and every persisted decision; `python -m app.core.config <profile>` validates offline. Docs: `docs/SITE_PROFILES.md`.
- Evidence: `backend/tests/test_config.py` (shipped profiles, reference catalog, 17-case invalid matrix, hash stability, private RFID override) and `backend/tests/test_alternate_site.py` (second site in a fresh process twice: same allocation and projections, its own rooms/zones, decisions carry its hash). Full backend suite and frontend build/tests pass.
- Limits: two-feeder radial topology (A hospital, B classroom) is required; dashboard cards, blueprint drawings and city map are still drawn for the default campus.
