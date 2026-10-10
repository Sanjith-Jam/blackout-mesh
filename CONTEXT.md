# Blackout Mesh — implementation context

## PR #38 conflict resolution — 2026-10-10

Merged current main (`6b2feaf`) into `feature/bm-fixes`. Preserved the evaluated logistic artifact and ML requirements, telemetry-derived diagnosis, protected allocation policies, read-only projections, background control loop, electrical-study boundary and evidence-backed classroom/hospital drawings. Integrated per-application lifecycle/storage, configurable inventory, generated OpenAPI/TypeScript contracts and the shared TanStack/Zustand WebSocket connection. Publication ordering uses `published_revision`; duplicate heartbeats remain fresh and older HTTP snapshots cannot replace newer same-run cached data.

SQLModel 0.0.22 failed on the project's Python 3.14 runtime; installed and tested 0.0.48. Each app owns its SQLite engine and shuts down its control/replay tasks. Simulation ACKs are saved without confirming physical LEDs; physical ACKs remain rejected until a validated command/session protocol is provisioned.

Verification: **133 backend tests passed**, including independent app instances, main route/WS envelope checks, SQLite audit records surviving restart and simulated ACK separation. Frontend production build passed; generated API schema/types are synchronized. Existing large-bundle warning remains. No browser interaction or physical hardware acceptance was run. Incident lifecycle/history replay and complete generated typing/runtime validation remain follow-up work; the PR does not establish production or hardware readiness.


Updated 2026-10-09. Remote application/Board B work and local ESP32 A work are merged. See [progress report](PROGRESS_REPORT.md) for current evidence, blockers and next actions; [ESP32 A handoff](ESP32_A_STATUS.md) retains its original build/physical limits.

## Current state

UI: the original light graph-paper theme remains. `/classrooms` now presents one compact tiled game-style campus map with three classrooms, small equipment sprites and a prominent shared current-flow overlay; `/hospital` independently shows three transformers, sensors and likely-cause evidence. The original `/demo` React Flow nodes now have explicit dimensions and render visibly. Model/replay presentation remains available through the API. Frontend production build passes with its existing large-bundle warning.

Software work is active and hardware work is paused. A trained four-feature local occupancy proxy, observation/model/replay APIs, exact 64-mask allocator, restoration gate and responsive command center are now integrated. The software freezes the existing six-service 14-kW catalog; the historical nine-load catalog remains deferred. No paid keys are required.

BM-17 (Issue #19) delivered and pushed to `origin/main`: modular telemetry-derived diagnosis subsystem (`backend/app/diagnostics/`) supporting simultaneous fault coexistence (overload + cooling failure co-occur), transparent deterministic ranking by severity tier and uncalibrated heuristic evidence score, physical contradiction detection (`CONTRADICTORY_EVIDENCE`), scoped missing data handling (`INSUFFICIENT_TELEMETRY`), and observational ambiguity (`INDISTINGUISHABLE_CAUSES`) with required inspection instructions (`next_check_needed`). Hospital visualizer and campus `GridState` now emit structured candidate hypotheses. Frontend displays multi-hypothesis badges and abstention cards. Rebased cleanly onto latest `origin/main` (incorporating Unified Site Authority #3, Safety Limits #22, and Control Loop #9/#10). 64 backend tests pass and frontend build passes cleanly.


The selected logistic pipeline beat Random Forest on validation; the tested CPU TabICL configuration was too slow for live inference. Later-day exploratory performance is much weaker than validation; do not claim real campus accuracy or untouched test results. Full measurements and data attribution are in `backend/models/MODEL_REPORT.md` and `evaluation.json`.

Hardware is not integrated: A/B serial/radio contracts differ, physical ACK fields stay null and the link stays NOT_CONNECTED. No device flashing or fresh physical testing occurred during this software delivery.

## Scope and authority

- Remote current application plan: [remaining plan v2.0](PRIORITYGRID_HACKATHON_REMAINING_PLAN.md) and [blueprint](PRIORITYGRID_FINAL_IMPLEMENTATION_BLUEPRINT.md).
- [Required ML plan](LAB_ACTIVITY_ML_PLAN.md) preserves the user's explicit trained-classifier requirement. Its nine-load catalog differs from the web app's six-load catalog; resolve this explicitly, keeping all values labeled by configuration.
- Physical first milestone: two ESP32s, one RFID reader, three cards, three classroom LEDs and four buttons. Full two-person plan is local-only in `/home/bread/blackout-mesh-local/`. Phase 0 stays complete.
- Simulated power; real radio/LEDs only after verified. No real occupancy accuracy, power delivery, savings or multi-hop mesh claim.
- Approximately 24-hour hackathon and ₹1,500 ceiling; no Arduino/displays. Unknown 12 V/amp/motor modules stay outside baseline.
- Reuse recommendations unchanged and local-only; keep keys, UIDs, device backups and raw local logs out of Git. Graphify/Security Auditor are explicit on-demand only.

## Next action

Rehearse the software demo, gather independently labeled local room observations, and evaluate on new sessions before making accuracy claims. Use `/classrooms`: reset, scan CR1, then overload (3,400 W). CR1 retains 2,000 W; CR2 and CR3 each retain 700 W essential computers/lighting. This separate 8,000-W classroom catalog does not change the six-service campus catalog. Use `/hospital` for overload, cooling failure, upstream loss and missing-sensor scenarios. Diagnosis reads sensor values, uses transparent demonstration thresholds and is not a trained transformer model. Use `/demo` for original shortage and feeder-fault controls; inspect the API at port 8000 `/docs`. Train only when updating evidence/model, not on every start. Detailed current checks are in PROGRESS_REPORT.md.

When hardware resumes, agree one A/B transport and physical mapping before linking the backend. Phase 0 remains complete; physical detailed plans stay local under `/home/bread/blackout-mesh-local/`.

## Pending-work planning — 2026-10-10

[PENDING_IMPLEMENTATION_PLAN.md](PENDING_IMPLEMENTATION_PLAN.md) defines all 24 requested backlog items against `d1c58d7`, with six phases, dependencies, acceptance/verification criteria and scoped library choices. This is planning, not implementation completion. Hardware remains paused and existing reuse recommendations are unchanged. Runtime code and dependencies were not changed or tested in this planning task; plan structure and dependency graph were checked. GitHub issue links are recorded in the plan index.

## Issue #5 delivered locally — 2026-10-10

Added a frozen exploratory temporal-audit protocol, reproducible rolling-day evaluator, leakage/gate tests and a report with split hashes, class counts, confusion matrices, selective risk, per-day variation, latency and memory. Shipped model/manifest/replay unchanged. Four-sensor candidates fail temporal coverage/safety gates; Light is an offline experiment only. Campus generalization remains unvalidated until independently labeled new-room sessions exist. See backend/benchmarks/occupancy/REPORT.md. Temporal tests and existing model tests pass; no hardware work. Code is local until an explicit push.

## Issue #6 delivered locally — 2026-10-10

Versioned activity_first/water_first campus policies, bounded within-tier fairness and switching preferences are configurable through GET/PUT /api/v1/allocation/policy. Hard T1/feeder/source constraints and restoration dwell stay fixed. Snapshot explanations include per-load reasons/score terms, immutable optimization inputs and exact applied-gate replay. Policy/schema/TypeScript/test changes are coordinated. Idle ticks preserve the trace. See docs/ALLOCATION_POLICIES.md. Six services profile at 1.59-ms median; experimental 19 leaves take 11.95 s, so that path stays offline and no unused solver was installed. Safety/control-loop/policy tests pass. Durable persistence and a shared 19-leaf dispatch engine remain outside this issue.

## Issue #7 delivered locally — 2026-10-10

Optional POST /api/v1/studies/electrical runs a balanced 400-V radial AC study on a worker thread; the campus source explicitly labels watt_budget limitations. Power Grid Model 1.13.193 is selected; NetworkX is connectivity-only and pandapower 3.5.6 is offline comparison-only. Result contracts include units, provenance, engine/version, convergence, independent I²R power-balance residual, null islands/failures and no restoration authorization. Observations pass through existing diagnosis validation; no thermal values are fabricated. Busy/timeout/stale-run-or-revision paths are covered, including keeping timed-out work serialized. Engine installed and tested in both the main Python 3.14.7 ML environment and isolated Python 3.12.15 benchmark environment. Detailed assumptions, licenses, matched cases, compatibility and latency evidence are in docs/ELECTRICAL_SIMULATION.md and backend/benchmarks/results/electrical_report.json. No hardware work or field-validation claim. Publication awaits explicit push.

## Issue #25 integration

Integrated PR #36 with current `main`, preserving the app-scoped state, shared WebSocket store, controller and hardware/UI work. SQLite history now drives chart data and read-only timeline playback; fault incidents are stored and emit durable open/resolve events. Current verification: 151 backend tests passed and the frontend production build passed. The history DOM suite is committed but could not run here because jsdom is absent and package downloads are blocked; the browser dashboard showed the updated controls, while the existing backend on port 8000 predates the new API. Keep #25 open pending its #12/#14 contract gates and history DOM check. Details: [docs/ISSUE_25_DELIVERY.md](docs/ISSUE_25_DELIVERY.md).

### Final verification for issues #5–#7

- `PYTHONPATH=backend .venv-ml/bin/python -m pytest backend/tests -q` — **119 passed**, including optional PGM in the Python 3.14.7 ML runtime.
- `PYTHONPATH=backend .venv-electrical/bin/python -m pytest backend/tests/test_electrical.py -q` — **16 passed**, Python 3.12.15; only a dependency TestClient deprecation warning.
- `cd frontend && npm run build` — passed; existing large-bundle warning remains. No interface redesign.
- Temporal evaluator rerun from `/tmp/occupancy.zip`; benchmark scripts produced checked-in evidence. Original model binary/manifest/replay diff is empty. No physical hardware tested, no campus labels invented, no GitHub reuse files uploaded.
- GitHub issues #5/#6/#7 were already marked closed (without linked closing PRs or implementation comments) when inspected. This delivery adds actual local implementation/evidence; it does not rely on those status labels. Commits remain local pending an explicit push.

## Prior art and claim boundaries

Added [docs/NOVELTY_AND_PRIOR_ART.md](docs/NOVELTY_AND_PRIOR_ART.md) to compare the demonstrated prototype with established occupancy, allocation, diagnosis and educational tools. The document explicitly limits the "mesh" name, campus ML generalization, physical switching and energy-savings claims. Novelty here is a prototype integration claim; independent field validation remains future work.

## Issue #14 generated API contract — 2026-10-10

Implemented on `codex/remaining-open-issues`: typed every HTTP route, exported stable method/path operation IDs and a version marker, added documented API errors and the named WebSocket envelope, generated frontend contracts, and added runtime validation before WebSocket snapshots enter cache. Added route/schema determinism tests, malformed-envelope tests, and an API-contract GitHub Actions workflow. Snapshot site identity is validated as a typed model throughout the history recorder. See [docs/ISSUE_14_DELIVERY.md](docs/ISSUE_14_DELIVERY.md); verification is recorded there.

## Issue #12 SQLite audit completion — 2026-10-10

On `codex/remaining-open-issues`, completed durable command/event/decision/incident/ACK history: site command UUIDs are stored and returned in receipts, decisions reference the command, ACK keys deduplicate retries, and run-linked records reject orphan writes. Added v1 SQLite migration tracking, visibly degraded health, verified online backups for both databases, and restart/backup/retention coverage. Raw RFID UIDs stay out of audit payloads. Physical ACKs remain rejected until a verified protocol exists. See [docs/ISSUE_12_DELIVERY.md](docs/ISSUE_12_DELIVERY.md).

## Current backlog follow-up — 2026-10-10

Issue #21 software session semantics now use `GridState.active_sessions` across the campus, classroom visualizer, RFID API and fake-board gateway adapter. Requests bind to the current run and support bounded event-ID replay protection; stale/out-of-order times reject, and new runs clear active sessions. See [docs/ISSUE_21_DELIVERY.md](docs/ISSUE_21_DELIVERY.md). Focused checks passed 53; full backend checks passed 163. ESP32 A/B interoperability remains unverified.

Issue #19's frozen developer-held-out diagnostic split was unsealed and reported once. Results are in `backend/benchmarks/diagnosis/results/diagnosis_heldout.{md,json}`; rank/top-k metrics from the actual multi-hypothesis outputs are not yet captured, so keep #19 open and do not tune against that revealed split.

## Issue #16 frontend tests — in progress

Kept the shared live-state socket and server-history flow from `main`; integrated useful WIP fixtures and component tests without duplicating the socket implementation. Added tests for both facility visualizers and power-edge states, automated accessibility scans, API-shape fixture checks, and Playwright route navigation. Local tests pass; the issue remains open pending CI and any remaining acceptance gaps.

## Person B city demo and predictive demand — 2026-10-10

Added a causal 10–60-second Ridge demand forecast trained on reproducible synthetic sessions (80 train / 20 calibration / 20 test); inputs are previous requested watts, never post-shedding power. Synthetic 60-second MAE is 149.49 W versus 469.59 W persistence. Live forecasting waits for four 10-second readings and abstains on stale/gapped observations or abrupt demand changes. Rehearsal samples remain explicitly synthetic and cannot alter the grid. The API exposes one revision for source, hospital and classroom panels, candidate fixed-priority comparison, forecast and gateway-reported hardware status. The landing page now reads measured inference/allocation results from checked-in JSON rather than placeholder percentages.

The new `/demo` city view preserves the six-service 14 kW electrical catalog and guides shortages, feeder trips, repair and staged recovery. `/console` retains history and engineering controls; facility drill-downs remain available. Hardware LED display now requires a fresh connected confirmation, including after stale links. B5 flashing, pairing, physical acceptance and hardware backup video remain deferred by the user's explicit request.

Checks so far: 9 new backend forecasting/city tests pass; frontend production build passes with the existing bundle-size warning; 17 component tests pass. The real-backend browser smoke check exposed and fixed a feeder-toggle error, then a mobile hardware-input overflow; final rerun is pending. The concurrent full backend suite had two diagnosis failures during separate in-progress diagnosis edits; no passing full-suite result is claimed here. Final verification and remaining Person B work will be recorded below.

### City demo verification and gateway lock ordering

Final real-controller browser journey passed: shortage, shared revisions, forecast warning, feeder A trip, critical shortfall, repair, dwell and full requested-service recovery. The existing facility-navigation browser check also passed (2 browser tests total). All 18 frontend component tests and the production build pass; four history checks and the runtime contract check pass. Current backend suite: 179 passed. City reads now release the site lock before reading the gateway, preventing a site/gateway lock inversion; a regression check verifies that order. No physical hardware was queried, connected or flashed.
