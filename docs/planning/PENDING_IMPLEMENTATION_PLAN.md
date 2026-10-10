# Blackout Mesh — exhaustive pending implementation plan

Prepared 2026-10-10 against repository baseline `d1c58d7`. This is a future-work plan and issue specification, not a completion report. Current local `frontend/tsconfig.tsbuildinfo` was already modified before planning and is outside this change. No runtime code or dependencies are changed by this planning task.

## Outcome and scope

Deliver one coherent, evidence-driven simulated campus controller with honest occupancy/fault uncertainty, reproducible allocation outcomes, durable audit history and synchronized views. Preserve the approved light tiled current-flow classroom visualizer and the distinct hospital view. Hardware remains paused; resume it only after software contracts stabilize and the user resumes that work.

The requested backlog is exactly 24 issues: 7 P0, 14 P1 and 3 P2. P0 means demonstration correctness, safety or validity of core claims; P1 means essential integration, evidence or reliability; P2 means subsequent hardening/generalization. Dependencies outrank labels: lifecycle work BM-09 is P1 but blocks several P0 fixes. Every issue below has implementation scope, acceptance criteria, verification and explicit boundaries. BM IDs are stable and independent of GitHub numbers.

## Current evidence and changes since earlier plans

- `backend/app/main.py` owns independent `grid`, `classroom_demo` and `hospital_scenario`, with global replay/task/connection resources. `GridState` additionally enforces a process singleton.
- `GridState.build_snapshot()` invokes allocation/restoration; `ClassroomDemo.snapshot()` computes allocation and model/replay evidence. Socket broadcast runs only when clients exist. A scheduler that owns control progression does not yet exist.
- Campus is six aggregate services totaling 14 kW: feeder A 6 kW (essential hospital 2, emergency lighting 1, water pump 3), feeder B 8 kW (classrooms 2/2/4). Classroom leaf appliances already sum to the same 8-kW classroom aggregate. Hospital diagnostic fixtures are independent and must not be silently interpreted as three physically mapped transformers.
- Latest classroom work supports multiple scans/unscan, a 0–8-kW supply slider, recorded replay and activity-ranked optional loads. Earlier single-selected-room plans are superseded. Campus RFID behavior still differs.
- Campus fault diagnosis reads configured capacity and feeder flags. Hospital sensor thresholds are a useful starting boundary but not coupled electrical diagnosis or a trained fault model.
- The occupancy model report documents substantial temporal degradation and an exposed exploratory later-day partition. Existing replay is a presentation selection from office validation data, not a natural multi-room held-out deployment stream.
- `DemoDashboard.tsx` hardcodes its WebSocket URL and schedules an uncancelled reconnect on close, including cleanup. `api.ts` already supplies `getWebSocketUrl`.
- Events and chart buffers are ephemeral; response interfaces are manually duplicated; frontend package scripts do not include automated tests. SQLModel, NetworkX, Zustand and TanStack Query are not installed in the inspected runtime manifests.

## Technology decisions and official research

These are recommended roles, not claims of compatibility or completed installation. Test supported Python/Node versions and pin actual successful installs; existing Python 3.14 ML tooling may not match all native electrical-engine wheels. Keep research environments separate. Existing private GitHub reuse recommendations are unchanged.

| Tool | Decision and scope | Avoid |
|---|---|---|
| [Zustand](https://github.com/pmndrs/zustand) | Use for UI-only preferences: map layer/selection, viewport, display choices; small focused selectors | A duplicate mutable store for authority snapshots, allocator masks or predictions |
| [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/overview) | Use for authoritative server snapshots, commands, model/config metadata and paginated history. One application-owned WebSocket adapter updates the same revision-validated cache | Page-owned independent authorities; assuming cache tooling automatically orders socket messages |
| [SQLModel](https://github.com/fastapi/sqlmodel) + [SQLite](https://www.sqlite.org/wal.html) | Implement incidents, decisions, transitions, commands and validated acknowledgments. Explicit sessions, migrations and single-writer durable commit ordering | Treating the database as a distributed controller lock, or persisted ACKs as fresh physical confirmation |
| [NetworkX](https://github.com/networkx/networkx) | Validate topology, connected components, reachability/islands and affected asset sets | Claiming graph reachability is electrical power-flow analysis or fault proof |
| [pandapower](https://www.pandapower.org/about/) | First reference-study candidate: power flow/state estimation/topology analysis; explicit network assumptions and convergence | Invented impedances/thermal behavior or claiming real physical validation |
| [Power Grid Model](https://power-grid-model.readthedocs.io/en/stable/) | Alternative steady-state study candidate; compare on the same reference network and measurements, then choose one runtime engine | Automatically running two engines or maintaining two competing authorities |
| [Google OR-Tools CP-SAT](https://developers.google.com/optimization/cp/cp_solver) | Evaluate for allocation scale after profiling; keep exact small-case enumeration as an oracle in tests | Adding solver complexity to six loads, unsafe timeout results or unbounded weighted objectives |
| [openapi-typescript](https://openapi-ts.dev/introduction) | Generate TS wire types from complete FastAPI models; explicitly include the WebSocket schema | Assuming generated TS validates network payloads at runtime |

Supporting lifecycle/session references: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/), [SQLModel per-operation sessions](https://sqlmodel.tiangolo.com/tutorial/fastapi/session-with-dependency/) and [NetworkX connectivity](https://networkx.org/documentation/stable/reference/algorithms/component.html).

NetworkX supplies graph algorithms; SQLModel wraps SQLAlchemy/Pydantic; TanStack Query handles server-state caching; Zustand provides client-state storage. The separation above is an architectural recommendation for this repository, not a feature promised by those libraries. Both electrical candidates support steady-state studies, but solver capability does not establish diagnosis identifiability or physical safety.

## Target control and data boundary

1. Accept a validated, idempotent command or telemetry observation. Tag site/run/epoch, sequence and input revision. Reject malformed identity/units; missing sensor data stays null.
2. One app-owned writer applies commands and processes observations. Expensive inference/solver jobs run outside the state lock; stale results cannot overwrite newer revisions.
3. A background control tick expires evidence/sessions, computes uncertain activity/diagnosis, evaluates hard constraints and ranks feasible optional allocations.
4. Apply immediate protective shedding and gated restoration. Proposed plan, applied simulated outputs and validated physical ACKs remain distinct.
5. Persist accepted decision/transition evidence before publishing its revision. If persistence or evidence is degraded, show it and use a declared conservative policy; do not silently report an audited success.
6. Publish one immutable materialized revision. GETs, socket broadcasts, chart queries and historical replays only read it or persisted history.
7. Campus/classroom/hospital are projections of that same run. TanStack Query receives revision-checked updates; UI preferences live in Zustand. Route navigation never creates a new simulation.

Canonical envelope: `schema_version`, `site_id`, `run_id`, `server_epoch`, `state_revision`, `generated_at`, `catalog_version`, `policy_version`, `model_version`, `observation_window` and provenance/quality. Commands have `command_id`, optional expected revision and explicit accepted/pending/applied/rejected status. Device ACKs also require device boot/session/command sequence identity. New server epochs permit revision restart only after explicit client resynchronization.

## Catalog and solver migration

Freeze a migration table, do not add all historical catalogs together. Initial campus total can remain 14 kW because 16 classroom appliance groups sum to existing L3/L4/L5 = 8 kW, while L0/L1/L2 = 6 kW. Parent aggregates become projections, not additional loads. Resolve feeder/transformer/room mappings before electrical studies; no arbitrary allocation of 100-A transformer fixtures to the 2-kW essential circuit.

Six aggregate services have 64 masks; expanding to 19 leaves yields 524288 masks. Retain exact enumeration for small regression cases. Benchmark real tick latency before choosing hierarchical search/branch-and-bound or CP-SAT. Hard constraints cannot be relaxed by preference weights. Always validate feasibility after a solver result; return a declared conservative feasible fallback or quantified unavoidable shortfall on failure. Do not describe an impossible essential minimum as satisfied.

## Phases, sequencing and release gates

Effort ranges in issue specifications are planning estimates, not measured commitments. The full backlog exceeds a 24-hour hackathon build. The issue estimates sum to approximately 61–103 focused engineering days before data-collection wait time. Some implementation work overlaps, so this sum is a budgeting envelope rather than a schedule; elapsed time depends on parallel capacity and fixed contracts. Electrical integration and independently labeled data are the largest uncertainties. No team-based roles are assigned.

### Phase 0 — freeze contracts and evidence

Read the baseline and all current tests; archive reproducible reference fixtures. Begin BM-09 lifecycle and BM-20 safety contract, research BM-03/BM-06, inventory BM-13 and sketch benchmark protocol BM-16. Record exact catalog, identity, unit and command semantics before changing interfaces. Do not inspect new final labels while tuning models/rules.

Gate: current behavior/migration table written; read-side mutations reproduced; critical/essential protection and uncertainty policy agreed; benchmark development/final boundaries declared.

### Phase 1 — one writer, read-only projections

Complete BM-09 → BM-01 → BM-07 → BM-08. Finish BM-20 and BM-19 on the canonical authority. Introduce enough typed identity/response structure to keep projections synchronized; BM-12 can grow incrementally. Begin persistence BM-10 once transitions are stable. The reconnect timer/URL fix in BM-11 can land independently as an immediate small patch, but final resynchronization waits for the revision contract.

Gate: no-client and reader-heavy timelines produce identical decisions; all GETs are inert; one command affects all relevant projections; multi-room sessions and original demo acceptance case remain correct; no safety constraints are bypassed by ML.

### Phase 2 — observation-derived faults and electrical boundary

Complete BM-05 reference-study comparison, BM-02 telemetry inference, BM-16 benchmark infrastructure/sealed fixtures and BM-17 multiple hypotheses. Keep budget mode available. Do not release final held-out labels before diagnosis and allocation candidates are frozen. BM-16 can be closed for the benchmark infrastructure without publishing held-out model-selection feedback; final performance reports belong to BM-17/BM-18.

Gate: observation-only module boundary; identical observations imply identical diagnosis regardless of hidden scenario; ambiguous inputs abstain; solver non-convergence is visible; simultaneous faults are represented without inventing certainty.

### Phase 3 — defensible model and allocation outcomes

Complete BM-03 with independently collected final sessions where possible; otherwise retain the limited office-proxy claim. Complete BM-04 policies/explanations and BM-18 fair-baseline evaluation. Evaluate UNKNOWN/no-ML and classifier-error ablations. Preserve development-only metrics separately from final reporting.

Gate: frozen protocol, no truth leakage, reported class/family denominators, independent service metrics and zero unsafe accepted allocations. A model need not beat every baseline to pass documentation integrity; poor performance must constrain the claim and policy.

### Phase 4 — durable history and synchronized client

Complete BM-10 storage, BM-12 generated contracts, BM-11 shared reconnect/cache ownership, BM-22 cross-route contract, BM-23 history/replay and BM-21 evidence-backed motion. Introduce Zustand/TanStack only in these scoped migrations; avoid two sources of truth. Preserve distinct current-flow visuals and hospital evidence presentation.

Gate: restart preserves audit history; clients recover from restart/gaps/out-of-order frames; route changes preserve run/revision; historical replay is inert; every path state has provenance and stale/unknown are visible.

### Phase 5 — release hardening and claim review

Complete BM-14 UI/a11y/E2E, BM-15 single-authority deployment, BM-24 configurable sites, BM-13 cleanup and final BM-06 comparison/pitch. Validate alternate site configuration without changing Python constants. Re-run migration and fresh-checkout checks before release.

Gate: one documented deployable process, durable backups/recovery, second authority rejected, fresh install reproducible, component/browser/accessibility suites passing, published limitations match evidence. External deployment/authentication is a separate explicit exposure decision, not an implicit consequence of this plan.

## Verification matrix and measurements

| Area | Required evidence |
|---|---|
| Control independence | Same command/observation timeline and decisions for 0/1/100 readers; virtual clock boundary tests; no orphan tasks |
| Hard feasibility | Source/feeder reachability and ratings; protected minima when feasible; quantified essential shortfall otherwise; all occupancy-state combinations |
| Diagnostic integrity | Observation-only import/type boundary; hidden-label substitution invariance; dropout/stuck/delayed/conflicting sensors; multiple faults and abstention |
| ML validity | Grouped temporal splits, untouched new sessions when available, no leakage, confusion matrices/coverage/selective risk, latency/memory and full provenance |
| Allocation value | Identical exogenous timelines for baselines, no-ML/UNKNOWN ablations, critical/essential unmet Wh, starvation/switching/recovery outcomes independent of solver score |
| Storage | Restart, idempotency, wrong-session ACK, rollback/busy/full disk, pagination, retention, migration/backup restore |
| API/client | Generated schema drift check, runtime envelope validation, stale HTTP/socket ordering, reconnect cleanup/StrictMode, epoch/run reset |
| Visuals | No flow on known-open/cut paths; proposed/applied/confirmed distinction; simulated units/provenance; reduced motion and keyboard legends |
| Deployment/config | Second controller rejected, supported local volume, invalid config matrix, alternate site, fresh setup/build |

Proposed engineering targets to measure, not current results: initial control cadence 250 ms; protective modeled shedding by the next healthy tick, p95 end-to-end command-to-published simulated decision ≤500 ms on the documented reference machine; zero constraint violations in accepted benchmark cases. Log actual tick/solver/inference/commit latencies and adjust cadence if measured costs require it. Physical radio/LED latency has no new target/result until hardware resumes. Avoid flaky absolute timing assertions in ordinary CI; use virtual-clock correctness tests and a separate performance report.

Existing checks to preserve: `PYTHONPATH=backend .venv-ml/bin/python -m pytest backend/tests -q` in the configured local environment; `npm run build` from frontend. Future additions: component/contract tests and real-backend Playwright journeys. This planning task does not rerun runtime suites because it changes documentation only.

## Persistence, migration and rollback details

Store typed Run/Command/Decision/Transition/Incident/Acknowledgment identities with indexes on site/run/time/revision and unique idempotency keys. Persist original inputs/config/model references sufficient for reproducibility. Avoid raw card UID or secret dumps. Separate actor/user incident acknowledgment from device command acknowledgment. Define migrations and retention before collecting history indefinitely; use local WAL with documented checkpoints/backup behavior, foreign keys and bounded transactions.

Migrate in vertical slices with compatibility responses/tests; remove an old authority only once all callers use the new one. Keep existing approved fixtures as regressions. Version the catalog/API rather than silently reinterpreting old masks. A rollback reactivates a known config/model/version and starts a new epoch/run where needed; it never rewrites historical decisions or converts old ACKs into current confirmation. Fault injected truth belongs only to test/simulator internals, not incident inference inputs.

## Explicitly pending but outside these 24 software issues

Hardware remains a separate paused acceptance track: resolve incompatible A/B radio and serial codecs, session/boot semantics, normalized RFID interaction and catalog-to-indicator mapping; validate A flashing/reader/cards/buttons; wire low-voltage B LEDs with individual resistors; pair radio; verify disconnect/reboot/late ACK behavior; capture three real card → backend decision → matching physical acknowledgment rehearsals. Existing successful chip queries or B USB logs do not prove the complete chain. Do not resume or flash devices as part of this planning task.

No mains/relays, paid API keys, deep vision model, MQTT broker, second backend, cloud database, distributed leader service or multi-hop mesh implementation is required for the scoped outcome. New libraries must earn their place through the corresponding issue's acceptance evidence.

## Backlog index

All 24 requested issues are published with P0/P1/P2 labels. GitHub numbers differ from the stable BM plan IDs because the repository already has pull-request numbers.

| ID | Priority | Issue | Blocking BM IDs |
|---|---|---|---|
| [BM-01 / #3](https://github.com/Sanjith-Jam/blackout-mesh/issues/3) | P0 | Unify campus, classroom and hospital under one authoritative simulation state | 09 |
| [BM-02 / #4](https://github.com/Sanjith-Jam/blackout-mesh/issues/4) | P0 | Replace oracle-based fault detection with telemetry-derived inference | 01, 07 |
| [BM-03 / #5](https://github.com/Sanjith-Jam/blackout-mesh/issues/5) | P1 | Investigate occupancy-model temporal generalization and publish a defensible evaluation | — |
| [BM-04 / #6](https://github.com/Sanjith-Jam/blackout-mesh/issues/6) | P1 | Make allocation objectives configurable and output full decision explanations | 01, 20, 19 |
| [BM-05 / #7](https://github.com/Sanjith-Jam/blackout-mesh/issues/7) | P1 | Introduce a technically defensible electrical simulation boundary | 01 |
| [BM-06 / #8](https://github.com/Sanjith-Jam/blackout-mesh/issues/8) | P1 | Write prior-art comparison and narrow the technical novelty claim | 03, 05, 17, 18 |
| [BM-07 / #9](https://github.com/Sanjith-Jam/blackout-mesh/issues/9) | P0 | Run allocation and staged restoration in a background control loop, not during snapshots | 01, 09 |
| [BM-08 / #10](https://github.com/Sanjith-Jam/blackout-mesh/issues/10) | P0 | Make GET requests and WebSocket snapshots strictly read-only | 07 |
| [BM-09 / #11](https://github.com/Sanjith-Jam/blackout-mesh/issues/11) | P1 | Replace process-wide mutable singletons and globals with explicit application state lifecycle | — |
| [BM-10 / #12](https://github.com/Sanjith-Jam/blackout-mesh/issues/12) | P1 | Persist incidents, state transitions and control decisions to SQLite | 09, 07 |
| [BM-11 / #13](https://github.com/Sanjith-Jam/blackout-mesh/issues/13) | P1 | Fix WebSocket reconnect lifecycle and synchronize state revisions | 08, 09 |
| [BM-12 / #14](https://github.com/Sanjith-Jam/blackout-mesh/issues/14) | P1 | Generate TypeScript API types from the FastAPI OpenAPI schema | 01, 08 |
| [BM-13 / #15](https://github.com/Sanjith-Jam/blackout-mesh/issues/15) | P2 | Clean up temporary scripts, empty scaffolds and dependency drift | — |
| [BM-14 / #16](https://github.com/Sanjith-Jam/blackout-mesh/issues/16) | P1 | Add frontend component, accessibility and cross-page end-to-end tests | 11, 12, 22, 23 |
| [BM-15 / #17](https://github.com/Sanjith-Jam/blackout-mesh/issues/17) | P2 | Define supported deployment model and protect against multi-worker split-brain | 09, 07, 10 |
| [BM-16 / #18](https://github.com/Sanjith-Jam/blackout-mesh/issues/18) | P0 | Build blind adversarial synthetic scenario benchmark with held-out fixtures | 02, 05, 20 |
| [BM-17 / #19](https://github.com/Sanjith-Jam/blackout-mesh/issues/19) | P1 | Support simultaneous faults, hypothesis ranking and diagnostic abstention | 02, 16 |
| [BM-18 / #20](https://github.com/Sanjith-Jam/blackout-mesh/issues/20) | P0 | Benchmark allocation against fair baselines using external outcome metrics | 04, 16 |
| [BM-19 / #21](https://github.com/Sanjith-Jam/blackout-mesh/issues/21) | P1 | Make RFID/software event semantics consistent with classroom demand and sessions | 01, 20 |
| [BM-20 / #22](https://github.com/Sanjith-Jam/blackout-mesh/issues/22) | P0 | Establish hard safety constraints for uncertain occupancy predictions | 01 |
| [BM-21 / #23](https://github.com/Sanjith-Jam/blackout-mesh/issues/23) | P1 | Make energy-flow graphics evidence-backed and label simulated quantities | 02, 05, 22 |
| [BM-22 / #24](https://github.com/Sanjith-Jam/blackout-mesh/issues/24) | P1 | Add cross-route consistency contract for scenario state, numbers and units | 01, 11, 12 |
| [BM-23 / #25](https://github.com/Sanjith-Jam/blackout-mesh/issues/25) | P1 | Replace client-only chart buffers with server history and replayable incident timelines | 10, 11, 12 |
| [BM-24 / #26](https://github.com/Sanjith-Jam/blackout-mesh/issues/26) | P2 | Make sites, facility inventories and policies configurable without editing Python source | 01, 04, 05 |

## Full implementation specifications

### BM-01 — [Unify campus, classroom and hospital under one authoritative simulation state](https://github.com/Sanjith-Jam/blackout-mesh/issues/3)

<!-- blackout-mesh-backlog:01 -->
#### Priority and outcome

**P0 · BM-01 · architecture**. One site/run authority owns commands, observations, topology, sessions, predictions, decisions and simulated applied outputs. Routes become projections of the same immutable revision.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). backend/app/main.py constructs grid, classroom_demo and hospital_scenario separately. GridState models six 14-kW services; visualizers.py has a distinct 8-kW appliance catalog and independent transformer fixtures. Sharing the activity model object does not unify scenario, demand or allocation state.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Inventory every existing ID, load total, feeder assignment, room mapping and route command. Write a migration table before replacing any catalog.
2. Use the existing 14-kW campus as the initial aggregate: feeder A has hospital essential 2 kW, emergency lighting 1 kW and pump 3 kW; feeder B has classrooms 2/2/4 kW. Classroom appliances decompose those aggregates; do not count parents and children twice.
3. Resolve three-transformer-to-service topology explicitly. Current ICU/Theatre/Wards sensor fixtures are not proof of an existing physical mapping. Preserve them as named fixtures until the mapping is reviewed.
4. Introduce one command gateway and site/run-scoped projection functions; retire independent mutable visualizer authorities. Keep distinct UI layouts and compatibility adapters during migration.
5. Make isolated teaching scenarios explicit run/site profiles with visible identity; switching profile is an explicit command, never a route-navigation side effect.

#### Acceptance criteria

- [ ] A single scenario change updates campus/classroom/hospital projections with the same run identity and revision.
- [ ] Demand/served totals reconcile from leaf loads through feeders to source; legacy budgets remain explicitly named until migration finishes.
- [ ] Existing multi-room scans, supply slider, recorded replay and hospital scenarios have a documented equivalent or explicit replacement; no silent behavior loss.

#### Verification

- Cross-route fixture checks with normal, CR1-only and multi-scan shortage; feeder trip and reset.
- Assert no duplicate leaf contribution and no route GET changes authority state.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-09 / #11](https://github.com/Sanjith-Jam/blackout-mesh/issues/11) — Replace process-wide mutable singletons and globals with explicit application state lifecycle

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Changing catalogs breaks masks and old demonstrations. Version the catalog/projections and keep physical indicator projection separate from simulated allocation.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **4–7 focused engineering days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

### BM-02 — [Replace oracle-based fault detection with telemetry-derived inference](https://github.com/Sanjith-Jam/blackout-mesh/issues/4)

<!-- blackout-mesh-backlog:02 -->
#### Priority and outcome

**P0 · BM-02 · diagnostics**. Diagnosis consumes only timestamped observation envelopes and configured equipment ratings/topology. Simulator truth remains inaccessible to the inference boundary.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). GridState.compute_fault_diagnosis reads source_capacity_w and feeder_available directly. The hospital diagnose function already accepts sensor values, but is an independent threshold demo and does not fix campus oracle access.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Define observation fields: asset_id, observed_at, received_at, sequence, unit, value/null, quality, provenance and uncertainty where meaningful. Reject invalid types, non-finite values, future timestamps beyond a documented tolerance and unknown assets.
2. Separate scenario truth, sensor synthesis and diagnostic input types/modules. The allocator may use explicitly configured conservative capacity limits; these must never be presented as inferred fault evidence.
3. Implement initial explainable hypotheses for overload, upstream undervoltage/loss, branch interruption and cooling failure using upstream/downstream readings and temporal consistency.
4. Attach supporting/contradicting evidence, observation window, missing sensors, likely affected assets and recommended verification. Treat missing/contradictory/stale data as uncertain, not healthy or zero.
5. Move all route fault panels to the common result; use likely cause language and distinguish an observation alarm from inferred root cause.

#### Acceptance criteria

- [ ] Changing hidden fixture labels while holding observations fixed never changes the diagnosis.
- [ ] No diagnostic code imports scenario truth or reads simulator feeder/capacity flags; dependency-boundary test enforces this.
- [ ] Stale/dropout observations lead to an explicit abstention or limited hypothesis, including a reason.

#### Verification

- Same telemetry under different hidden truths; different telemetry under identical scenario labels.
- Missing upstream voltage, swapped sensor IDs, cooling failure at normal current, overload without heat and plausible normal demand changes.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-01 / #3](https://github.com/Sanjith-Jam/blackout-mesh/issues/3) — Unify campus, classroom and hospital under one authoritative simulation state
- [BM-07 / #9](https://github.com/Sanjith-Jam/blackout-mesh/issues/9) — Run allocation and staged restoration in a background control loop, not during snapshots

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Voltage/current/temperature alone cannot uniquely identify every fault. Do not fabricate confidence, causality or protection guarantees.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **4–6 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

### BM-03 — [Investigate occupancy-model temporal generalization and publish a defensible evaluation](https://github.com/Sanjith-Jam/blackout-mesh/issues/5)

<!-- blackout-mesh-backlog:03 -->
#### Priority and outcome

**P1 · BM-03 · ml**. Explain the temporal degradation and publish reproducible, honest performance and abstention results before expanding classifier influence.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). backend/models/MODEL_REPORT.md reports logistic validation macro-F1 0.843 versus exploratory later-day 0.496, with 348/1835 false-INACTIVE occupied rows and 79.9% coverage later. The later block was exposed during development and is not untouched. Replay is class-balanced presentation sampling from validation office data.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Audit deduplication, complete-session/day grouping, feature transformations, training-only preprocessing and provenance. Freeze the currently exposed data as development/exploratory.
2. Compare majority/rule/logistic/tree baselines with rolling-origin evaluation and complete held-out sessions. Diagnose drift, environmental differences and omitted light feature as experiments, not assumed causes.
3. Predeclare operating-point selection, coverage and false-INACTIVE criteria; perform calibration only on an independent calibration partition if justified.
4. Gather independently labeled new room sessions for a final local evaluation; if unavailable, publish that campus generalization remains unvalidated and keep conservative policy.
5. Version artifact, feature schema, split manifests, software environment, latency and memory measurements; retain the existing baseline until a candidate clears the predeclared gate.

#### Acceptance criteria

- [ ] Report class counts, confusion matrices, false-INACTIVE/occupied denominator, coverage, selective risk, per-session variation and latency; UNKNOWN is not silently removed.
- [ ] No model selection or threshold tuning uses the final held-out labels.
- [ ] The model card clearly separates occupancy, room use and equipment demand; office occupancy is not relabeled as laboratory ground truth.

#### Verification

- Leakage checks; grouped split disjointness; artifact hash and feature-order tests.
- Run inference without labels, timestamps, RFID UID, scenario IDs or post-shedding power.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- No blocking implementation dependency. Start with the stated contract/research scope.

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

A pretrained tabular model cannot replace local evidence. Better validation alone is insufficient; publish poor results instead of tuning on held-out labels.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **3–5 days plus data collection**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

### BM-04 — [Make allocation objectives configurable and output full decision explanations](https://github.com/Sanjith-Jam/blackout-mesh/issues/6)

<!-- blackout-mesh-backlog:04 -->
#### Priority and outcome

**P1 · BM-04 · allocation**. One versioned policy ranks feasible plans transparently without allowing configurable preferences to override safety constraints.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). backend/app/core/allocator.py embeds a lexicographic tuple with fixed service bits, activity rankings and a water-pump ordering. ClassroomDemo implements a different greedy appliance policy. Current output is not a complete objective/constraint trace.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Represent hard constraints separately from preferences: source/feeder limits, disconnected paths, critical minima, uncertain occupancy protection, minimum off dwell and restoration eligibility.
2. Define policy configuration for priority tiers, optional-load order, fairness/starvation limits, switching penalties and deterministic tie breaks. Specify where each objective is lexicographic versus weighted.
3. Emit per-load requested/proposed/applied status, binding constraints, policy version, score terms, shortfall and counterfactual reason for rejection. Include why a lower-tier load can fit when a larger higher-tier one cannot.
4. Keep the 64-mask solver as the six-service reference. Profile the decomposed appliance inventory: 19 binary leaf loads imply 524288 masks; do not blindly enumerate it at every tick.
5. Evaluate Google OR-Tools CP-SAT only when the real inventory/runtime budget requires it; validate status, timeouts, feasible incumbent and deterministic tie handling. Never return an unchecked mask after timeout.

#### Acceptance criteria

- [ ] Two named policies can differ on optional loads while satisfying identical hard constraints.
- [ ] Every decision carries replayable input/policy revisions and a human-readable per-load reason.
- [ ] Feasible output never exceeds any capacity; infeasible critical minima are explicitly reported rather than claimed satisfied.

#### Verification

- Small-inventory exact enumeration comparison; objective ties; insufficient capacity; disconnected feeder; fairness over time.
- Solver timeout/no-solution fallbacks and changing policy during staged restoration.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-01 / #3](https://github.com/Sanjith-Jam/blackout-mesh/issues/3) — Unify campus, classroom and hospital under one authoritative simulation state
- [BM-20 / #22](https://github.com/Sanjith-Jam/blackout-mesh/issues/22) — Establish hard safety constraints for uncertain occupancy predictions
- [BM-19 / #21](https://github.com/Sanjith-Jam/blackout-mesh/issues/21) — Make RFID/software event semantics consistent with classroom demand and sessions

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Configurable does not mean arbitrary safety-critical weights. Do not conflate the allocator objective with independent benchmark outcomes.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **3–5 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

#### Official technical references

- https://developers.google.com/optimization/cp/cp_solver

### BM-05 — [Introduce a technically defensible electrical simulation boundary](https://github.com/Sanjith-Jam/blackout-mesh/issues/7)

<!-- blackout-mesh-backlog:05 -->
#### Priority and outcome

**P1 · BM-05 · simulation**. Keep a fast explicit budget mode and introduce a validated optional electrical-study adapter with honest modeling limits.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). The current allocator uses watt budgets, while hospital_snapshot supplies deterministic current/voltage/temperature tuples. There is no coupled electrical power-flow or thermal model; capacity reduction alone is not an electrical fault simulation.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Define the adapter contract: topology/config version, switch/load/generator inputs, solve status, units, bus voltage, branch current, active/reactive power, loading and timestamps. Missing/failed solve results remain invalid, not zero.
2. Use NetworkX for connectivity/islanding/reachability checks. It is not a power-flow solver or fault classifier.
3. Build the same small radial reference network in pandapower and Power Grid Model in isolated optional environments. Compare supported features, installation compatibility, numerical agreement, non-convergence handling and p50/p95 batch/single-case latency.
4. Select one runtime study engine by recorded evidence. Keep the alternative only as an offline cross-check if valuable; do not add both to the default API environment.
5. Document nominal voltage, line impedance, power factor, transformer rating, grounding/model assumptions and parameter sources. Do not infer temperature dynamics or cooling faults from steady-state power flow without a separate declared thermal model.
6. Connect solver-generated observations through the telemetry boundary; diagnosis cannot access the hidden fault injection. Offload expensive solves and reject stale results using run/revision identity.

#### Acceptance criteria

- [ ] Budget mode explicitly labels its limitations. Electrical mode exposes solver/version, convergence, assumptions and quantity provenance.
- [ ] Normal, overload, open branch and upstream loss cases produce explained results with residual/tolerance checks.
- [ ] Study failures abstain and cannot trigger unsafe restoration or fake flowing current.

#### Verification

- Conservation/unit-conversion checks; disconnected islands; invalid impedance; balanced/unbalanced applicability; solver failure.
- Matched reference cases with documented numerical tolerances, not a claim of field validation.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-01 / #3](https://github.com/Sanjith-Jam/blackout-mesh/issues/3) — Unify campus, classroom and hospital under one authoritative simulation state

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Power flow is steady-state analysis, not protective relay coordination, switching transients or certified safety. Version/license compatibility must be verified before installation.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **4–7 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

#### Official technical references

- https://www.pandapower.org/about/
- https://power-grid-model.readthedocs.io/en/stable/
- https://networkx.org/documentation/stable/reference/algorithms/component.html

### BM-06 — [Write prior-art comparison and narrow the technical novelty claim](https://github.com/Sanjith-Jam/blackout-mesh/issues/8)

<!-- blackout-mesh-backlog:06 -->
#### Priority and outcome

**P1 · BM-06 · research**. A source-backed comparison and pitch claim that reflect measured integration value rather than claiming invention of established methods.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). The prototype combines occupancy classification, load allocation, visual explanations and planned ESP32 indicators. Existing reports explicitly exclude campus accuracy, measured savings, real power delivery and multi-hop mesh; no measured novelty comparison is published.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Research primary papers and official implementations in occupancy sensing, demand response, priority shedding, topology-aware diagnosis and hardware-in-the-loop teaching demos.
2. Build a comparison matrix with task, data, constraints, model, diagnosis uncertainty, hardware integration, evaluation and license; cite DOI/official URL and access date.
3. Separate reused technique, implemented integration, measured improvement and future proposal. Preserve existing private reuse recommendations; publish only relevant technical attribution and implementation claims.
4. Use the blind diagnosis and fair allocation reports for claims. Record negative findings and an explicit limitations/claim checklist for judges.
5. Document the working-name mesh limitation and require real packet-path evidence before making a routing claim.

#### Acceptance criteria

- [ ] Every technical novelty/performance statement links to a result or prior-art source.
- [ ] Pitch differentiates demonstrated features from proposed hardware and electrical realism.
- [ ] No energy-saving, real-campus accuracy or novel ML claim is made without the corresponding evidence.

#### Verification

- Review claims against current tests/artifacts and end-to-end demo evidence.
- Check citations, comparability assumptions and copied-code license obligations at pinned revisions if code is actually adopted.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-03 / #5](https://github.com/Sanjith-Jam/blackout-mesh/issues/5) — Investigate occupancy-model temporal generalization and publish a defensible evaluation
- [BM-05 / #7](https://github.com/Sanjith-Jam/blackout-mesh/issues/7) — Introduce a technically defensible electrical simulation boundary
- [BM-17 / #19](https://github.com/Sanjith-Jam/blackout-mesh/issues/19) — Support simultaneous faults, hypothesis ranking and diagnostic abstention
- [BM-18 / #20](https://github.com/Sanjith-Jam/blackout-mesh/issues/20) — Benchmark allocation against fair baselines using external outcome metrics

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Literature search starts in parallel; final claims depend on the measured work. This issue does not authorize copying unknown-license code.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **2–3 days plus final report refresh**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

### BM-07 — [Run allocation and staged restoration in a background control loop, not during snapshots](https://github.com/Sanjith-Jam/blackout-mesh/issues/9)

<!-- blackout-mesh-backlog:07 -->
#### Priority and outcome

**P0 · BM-07 · control**. A single application-owned scheduler advances control regardless of readers, client count or route polling frequency.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). GridState.build_snapshot calls compute_allocation, which updates RestorationGate. ClassroomDemo.snapshot allocates, predicts/caches replay evidence and advances restoration. broadcast_state runs only when clients are connected.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Add an explicit tick(now, accepted_commands, observations) path that expires evidence, updates sessions, infers activity/faults, allocates and applies staged restoration.
2. Start/stop one loop in FastAPI lifespan; await cancellation and expose loop health/last-successful tick. Use a monotonic clock for dwell/freshness and UTC for persisted/display timestamps.
3. Choose an initial measured 250-ms control period; commands wake the loop for prompt protective shedding. Expensive inference/study tasks run outside the critical section and carry input revision tokens.
4. Publish an immutable materialized snapshot after a committed transition. Do not advance simulation time from GETs, sockets or chart reads.
5. Define overrun policy without unbounded catch-up: coalesce obsolete work, record missed ticks and retain conservative outputs when evidence is stale.

#### Acceptance criteria

- [ ] With zero browsers, shedding and restoration progress correctly in the same virtual-time schedule as with 1 or 100 readers.
- [ ] Only one active control loop exists per authority; shutdown cancels and awaits owned tasks.
- [ ] Protective shedding bypasses restoration delays; restoration still requires stable evidence and off dwell.

#### Verification

- Injected-clock tests at 2.99/3/4.99/5 seconds; one-new-load/sec; changing constraints during recovery.
- No-client, many-client, slow inference, stale result, cancellation and loop-overrun integration tests.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-01 / #3](https://github.com/Sanjith-Jam/blackout-mesh/issues/3) — Unify campus, classroom and hospital under one authoritative simulation state
- [BM-09 / #11](https://github.com/Sanjith-Jam/blackout-mesh/issues/11) — Replace process-wide mutable singletons and globals with explicit application state lifecycle

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

P0 even though lifecycle issue 09 is labeled P1: dependency order takes precedence over label order. Publishing must not hold the state lock while writing to slow clients.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **2–4 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

#### Official technical references

- https://fastapi.tiangolo.com/advanced/events/

### BM-08 — [Make GET requests and WebSocket snapshots strictly read-only](https://github.com/Sanjith-Jam/blackout-mesh/issues/10)

<!-- blackout-mesh-backlog:08 -->
#### Priority and outcome

**P0 · BM-08 · api**. Queries serialize the last published immutable state; all state changes originate from accepted commands or control ticks.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). GET /api/v1/snapshot calls grid.build_snapshot; GET /api/v1/visualizers/classrooms calls snapshot. Both can change allocation/restoration. Repeated reads can affect state timing, prediction caches and replay projection.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Split mutation/advance methods from serialization/projection methods. Move prediction cache writes, replay progress and freshness transitions into the control loop.
2. GET and socket publication return the same revision payload for unchanged state; transport send time may be a separate envelope field rather than rewriting generated state timestamps.
3. Audit health/model/history endpoints for hidden initialization, training, replay or command effects.
4. Define command responses with accepted command identity and applied/pending revision semantics so clients do not mistake request acceptance for completed application.

#### Acceptance criteria

- [ ] Repeated GETs and socket subscriptions produce no changes in masks, restoration timers, inference counts, replay cursor, domain event count or control revision.
- [ ] GET before first ready tick returns explicit readiness/unavailable state, never initializes a control decision.
- [ ] Read endpoints can serve concurrent readers without copying mutable nested references into clients.

#### Verification

- Freeze the clock and fingerprint all domain state before/after 100 reads across all routes.
- Run identical scripted timelines with zero/read-heavy clients and compare decision/event digests.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-07 / #9](https://github.com/Sanjith-Jam/blackout-mesh/issues/9) — Run allocation and staged restoration in a background control loop, not during snapshots

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Issue 07 supplies the writer. Retain an initial state publication at startup so read-only queries do not regress initial UX.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **1–2 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

### BM-09 — [Replace process-wide mutable singletons and globals with explicit application state lifecycle](https://github.com/Sanjith-Jam/blackout-mesh/issues/11)

<!-- blackout-mesh-backlog:09 -->
#### Priority and outcome

**P1 · BM-09 · architecture**. Each app instance owns explicit resources and an isolated lifecycle, while each supported site/run has one authority.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). GridState.__new__ enforces a process singleton. main.py has module-level grid, manager, classroom_demo, replay_task/generation and hospital_scenario; lifespan cancels tasks but does not await their completion.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Create application resources in lifespan or an app factory: authority, clock, model handle, command gateway, repository and connection manager. Inject them through dependencies/app.state.
2. Remove GridState singleton construction and import-time mutable initialization; models may be read-only shared resources only where explicitly safe.
3. Track every background task, cancel and await it on shutdown, close sockets and release repository resources even after partial startup failure.
4. Separate test application construction from production configuration and expose readiness checks for model, loop and storage.

#### Acceptance criteria

- [ ] Two app instances in one process do not share sessions, replay, commands, sockets or revisions.
- [ ] Startup/shutdown can repeat without leaked tasks, locks or connections.
- [ ] Existing endpoints obtain authority through the same explicit dependency rather than importing globals.

#### Verification

- Two TestClients with distinct states; repeated lifespan; failed model/storage initialization; shutdown during replay.
- No orphan tasks and no cross-test state reset hacks.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- No blocking implementation dependency. Start with the stated contract/research scope.

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

This does not by itself provide distributed coordination. Single-process ownership remains the supported deployment until issue 15 is complete.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **2–3 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

#### Official technical references

- https://fastapi.tiangolo.com/advanced/events/

### BM-10 — [Persist incidents, state transitions and control decisions to SQLite](https://github.com/Sanjith-Jam/blackout-mesh/issues/12)

<!-- blackout-mesh-backlog:10 -->
#### Priority and outcome

**P1 · BM-10 · persistence**. Use SQLModel with SQLite for a durable, queryable audit trail of observations, commands, decisions, incidents, applied transitions and acknowledgments.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). GridState.events is an in-memory list truncated to 50 entries. There is no SQL dependency, durable decision log or persisted acknowledgment store in backend requirements.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Define Run, Command, Decision, Transition, Incident and Acknowledgment tables; add observation/telemetry storage or an explicitly versioned compressed reference where replayability requires it.
2. Use explicit typed identity columns (site/run/epoch/revision, command_id, decision_id, asset_id and device boot/sequence/session where relevant), UTC timestamps, schema version and bounded metadata payloads.
3. Implement per-operation SQLModel sessions, foreign keys, unique idempotency constraints, migrations, indexes, retention and cursor pagination. Use SQLite WAL only on supported local persistent storage, with busy timeout and a single serialized writer.
4. Commit decision/transition audit records before publishing the new revision; the authority must not call an unpersisted action audited. Handle full disk/busy/corruption with a visible degraded state and conservative restoration policy.
5. Validate physical ACK identity before recording confirmed output; simulation acknowledgments must be a distinct provenance. On restart, restore display history but do not assume persisted physical ACKs confirm current device state.

#### Acceptance criteria

- [ ] Restart preserves incidents, decisions and ACK history with stable IDs; duplicates do not create extra state transitions.
- [ ] Unacknowledged or wrong-session commands never set confirmed hardware status.
- [ ] Backups/migrations/retention preserve referential integrity and sensitive raw card IDs are excluded from public logs.

#### Verification

- Temporary-file SQLite restart, rollback, duplicate command/ACK, wrong boot/session, database busy and disk-failure simulations.
- Pagination/index query checks and integrity after retention/backup restore.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-09 / #11](https://github.com/Sanjith-Jam/blackout-mesh/issues/11) — Replace process-wide mutable singletons and globals with explicit application state lifecycle
- [BM-07 / #9](https://github.com/Sanjith-Jam/blackout-mesh/issues/9) — Run allocation and staged restoration in a background control loop, not during snapshots

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

SQLite is not a multi-worker authority lock. Async API code must not block on long transactions; a bounded writer path and commit ordering are required.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **4–6 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

#### Official technical references

- https://github.com/fastapi/sqlmodel
- https://sqlmodel.tiangolo.com/tutorial/fastapi/session-with-dependency/
- https://www.sqlite.org/wal.html

### BM-11 — [Fix WebSocket reconnect lifecycle and synchronize state revisions](https://github.com/Sanjith-Jam/blackout-mesh/issues/13)

<!-- blackout-mesh-backlog:11 -->
#### Priority and outcome

**P1 · BM-11 · frontend**. One shared connection owner reconnects safely, uses configured URLs and never overwrites a newer state with stale messages.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). DemoDashboard.tsx uses ws://127.0.0.1:8000/ws/live directly and schedules setTimeout(connectWs, 3000) on every close without tracking/cancelling it. Closing on unmount can schedule a new connection. api.ts already exports getWebSocketUrl.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Immediate first slice: use getWebSocketUrl; track reconnect/feedback timer IDs; mark disposed before close; detach handlers and cancel timers on unmount. Test React StrictMode setup/cleanup.
2. Move long-lived subscription ownership to the application shell/shared server-state adapter, with capped backoff+jitter, network offline handling, heartbeat timeout and explicit stale age.
3. Define server_epoch/run_id/state_revision plus command revision/command_id where needed. Accept monotonically newer revisions within an epoch; reject duplicates/out-of-order frames and explicitly resync on epoch/run change or gaps.
4. Use TanStack Query as the sole snapshot/server-history cache. WebSocket full snapshots update the same query key after revision validation; cancel stale HTTP requests so late responses cannot roll the cache back.
5. Use Zustand only for UI selections, map layer/viewport and connection presentation if needed; do not duplicate authoritative allocation or ML outputs in a second mutable store.

#### Acceptance criteria

- [ ] Navigation, unmount and StrictMode create no orphan reconnects; one socket serves active routes.
- [ ] Configured HTTPS API origin produces wss; reconnect rehydrates the latest state and preserves a visible stale banner until synchronized.
- [ ] Older HTTP/socket messages cannot reverse a newer decision; missed revisions trigger a documented full resync.

#### Verification

- Fake-timer component tests for unmount, close/error races and capped retries.
- Local HTTP/WebSocket tests for backend restart, duplicates, gaps, reordered messages and route switching.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-08 / #10](https://github.com/Sanjith-Jam/blackout-mesh/issues/10) — Make GET requests and WebSocket snapshots strictly read-only
- [BM-09 / #11](https://github.com/Sanjith-Jam/blackout-mesh/issues/11) — Replace process-wide mutable singletons and globals with explicit application state lifecycle

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Libraries do not automatically solve ordering. Never optimistically show a command as applied or physically ACKed.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **2–4 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

#### Official technical references

- https://tanstack.com/query/latest/docs/framework/react/overview
- https://github.com/pmndrs/zustand

### BM-12 — [Generate TypeScript API types from the FastAPI OpenAPI schema](https://github.com/Sanjith-Jam/blackout-mesh/issues/14)

<!-- blackout-mesh-backlog:12 -->
#### Priority and outcome

**P1 · BM-12 · contract**. FastAPI response/request models define the wire contract and generate TypeScript types reproducibly.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). frontend/src/types.ts manually duplicates Python contracts. Several visualizer handlers return untyped dictionaries, so current OpenAPI generation alone would omit important response structure.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Add strict Pydantic response models for canonical snapshot, projections, commands, errors, history, telemetry and diagnosis. Document null/missing, integer watts and ISO UTC timestamps.
2. Export OpenAPI from an isolated app/schema process with no training, running control loop or physical device startup. Stabilize operation IDs and schema version.
3. Generate types with openapi-typescript; keep UI-only view models separate and remove duplicated wire interfaces. Feed the generator-produced types into existing API helpers or a small typed client.
4. Represent the WebSocket envelope with a named Pydantic/JSON-schema contract and generate it explicitly if not naturally reachable through OpenAPI.
5. Add generation scripts and CI drift checks; introduce runtime validation of untrusted socket envelopes rather than assuming TypeScript protects network input.

#### Acceptance criteria

- [ ] Fresh generation produces no diff; backend schema changes fail CI until generated consumers/fixtures are updated.
- [ ] Every route including hospital/classroom has concrete request and response schemas.
- [ ] WebSocket envelopes, units, null evidence and enum variants are covered by the same contract workflow.

#### Verification

- Golden response validation, malformed network payload rejection, generator determinism and consumer build.
- Backward-compatibility/schema migration fixture for any retained old endpoint.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-01 / #3](https://github.com/Sanjith-Jam/blackout-mesh/issues/3) — Unify campus, classroom and hospital under one authoritative simulation state
- [BM-08 / #10](https://github.com/Sanjith-Jam/blackout-mesh/issues/10) — Make GET requests and WebSocket snapshots strictly read-only

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Generated TypeScript is not runtime validation. Keep generated files read-only and avoid silently treating unknown enum values as healthy.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **2–3 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

#### Official technical references

- https://openapi-ts.dev/introduction

### BM-13 — [Clean up temporary scripts, empty scaffolds and dependency drift](https://github.com/Sanjith-Jam/blackout-mesh/issues/15)

<!-- blackout-mesh-backlog:13 -->
#### Priority and outcome

**P2 · BM-13 · maintenance**. Remove proven dead scaffolding and make fresh-checkout setup reproducible without destroying useful hardware or evaluation work.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). The repository has backend/allocator_check.py, multiple firmware/host implementations, separate requirement sets and a generated tracked frontend/tsconfig.tsbuildinfo. Their current necessity requires a caller/inventory audit; do not assume they are all removable.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Inventory scripts/modules/config and their callers using rg; classify maintained, historical/reference, generated and unused. Record evidence before deletion.
2. Consolidate overlapping dependency definitions where consumers permit; keep optional ML benchmarking/electrical study dependencies separate from the default runtime.
3. Pin tested compatible versions/lockfiles after successful clean installation; review Python/native-wheel compatibility and licenses for newly selected libraries.
4. Exclude generated build caches and local databases/evaluation scratch files from tracking after confirming no intentional fixture use.
5. Split cleanup from behavior changes; preserve both hardware implementations until protocol reconciliation lands. Update setup commands and remove stale claims.

#### Acceptance criteria

- [ ] A clean checkout installs and runs documented backend/frontend checks.
- [ ] Every removed file has an audited no-caller explanation or explicit archival path.
- [ ] No credentials, raw UID maps, private reuse research or local DBs enter Git.

#### Verification

- Fresh isolated install/build/test; dependency resolution and import check for optional study environment.
- Check references after deletion and confirm hardware tools retain their documented entry points.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- No blocking implementation dependency. Start with the stated contract/research scope.

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Do not rewrite history or delete local user data. Cleanup must not become a general reformat or unsolicited dependency upgrade.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **1–2 days after main migrations**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

### BM-14 — [Add frontend component, accessibility and cross-page end-to-end tests](https://github.com/Sanjith-Jam/blackout-mesh/issues/16)

<!-- blackout-mesh-backlog:14 -->
#### Priority and outcome

**P1 · BM-14 · testing**. Automate meaningful interactions and cross-route correctness while preserving the approved light game-style map.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). frontend/package.json only defines dev/build/preview; there is no frontend test command or automated UI/a11y suite. Manual browser evidence does not prevent reconnect/state/visual regressions.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Introduce Vitest/React Testing Library and a focused network mock layer for component behavior; add Playwright for browser E2E and axe-based automated accessibility checks.
2. Cover loading/error/stale/recovery, command pending/rejected, multi-scan demand, slider validation, missing-sensor abstention and history pagination.
3. Run one seeded cross-page script against the real backend: normal, CR1 scan, shortage, route switch, hospital fault, backend restart/resync, restoration and history replay.
4. Assert current paths correspond to canonical energized/applied state; verify optional device motion stops when shed and all animations honor reduced motion.
5. Check keyboard focus, accessible controls/legends, status text beyond color, narrow screens and representative screenshot baselines. Keep screenshots limited to meaningful approved views.

#### Acceptance criteria

- [ ] CI runs unit/component/contract/E2E checks with deterministic fixtures and reports failures.
- [ ] Unmount/reconnect and cross-route revision regressions have failing-before/passing-after tests.
- [ ] No page-level overflow at supported widths; map scrolling is contained and labeled.

#### Verification

- Real-browser 375px and desktop viewport checks; keyboard-only journey; reduced motion; axe.
- Backend unavailable, malformed/reordered frames and database history surviving page reload.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-11 / #13](https://github.com/Sanjith-Jam/blackout-mesh/issues/13) — Fix WebSocket reconnect lifecycle and synchronize state revisions
- [BM-12 / #14](https://github.com/Sanjith-Jam/blackout-mesh/issues/14) — Generate TypeScript API types from the FastAPI OpenAPI schema
- [BM-22 / #24](https://github.com/Sanjith-Jam/blackout-mesh/issues/24) — Add cross-route consistency contract for scenario state, numbers and units
- [BM-23 / #25](https://github.com/Sanjith-Jam/blackout-mesh/issues/25) — Replace client-only chart buffers with server history and replayable incident timelines

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Automated a11y checks are incomplete; retain manual keyboard/visual review. Avoid brittle pixel-perfect full-page snapshots for dynamic clocks.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **3–5 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

### BM-15 — [Define supported deployment model and protect against multi-worker split-brain](https://github.com/Sanjith-Jam/blackout-mesh/issues/17)

<!-- blackout-mesh-backlog:15 -->
#### Priority and outcome

**P2 · BM-15 · deployment**. Document and enforce a single-authority local deployment with clear boundaries for any future scaling.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). Module-global authorities create independent decisions in each worker. There is no cross-process command ownership, and adding SQLite audit storage alone would not synchronize simulation state.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Support one API/control process and one worker initially. Define bind address, allowed origins, API/WebSocket origin config, durable local volume, health/readiness and graceful shutdown.
2. Use a deployment guard against duplicate authorities for the same site/store (OS-backed lifetime lock or proven equivalent), plus documented worker restrictions; reject accidental duplicate launches.
3. Specify safe restart: new server epoch, historical recovery, sensor/ACK resynchronization and conservative live status until fresh evidence arrives.
4. If external deployment is later required, define authentication/TLS and access boundaries before exposing controls. A distributed leader/queue service is explicitly deferred until requirements justify it.

#### Acceptance criteria

- [ ] Second authority for the same site fails visibly; different isolated test sites remain possible.
- [ ] Documented startup, backup, restore and crash recovery are reproducible.
- [ ] Environment config reaches both HTTP and sockets; no hardcoded localhost deployment breakage.

#### Verification

- Two-process ownership attempt, abrupt termination/restart, stale lock recovery and volume permission failure.
- Readiness failure on unhealthy control loop/storage and graceful cancellation under active clients.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-09 / #11](https://github.com/Sanjith-Jam/blackout-mesh/issues/11) — Replace process-wide mutable singletons and globals with explicit application state lifecycle
- [BM-07 / #9](https://github.com/Sanjith-Jam/blackout-mesh/issues/9) — Run allocation and staged restoration in a background control loop, not during snapshots
- [BM-10 / #12](https://github.com/Sanjith-Jam/blackout-mesh/issues/12) — Persist incidents, state transitions and control decisions to SQLite

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

WAL does not provide a distributed lock and network filesystems are not an assumed SQLite deployment. Physical control remains outside scope.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **1–3 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

### BM-16 — [Build blind adversarial synthetic scenario benchmark with held-out fixtures](https://github.com/Sanjith-Jam/blackout-mesh/issues/18)

<!-- blackout-mesh-backlog:16 -->
#### Priority and outcome

**P0 · BM-16 · benchmark**. A frozen reproducible benchmark separates hidden truth from observations and measures errors under adversarial but declared simulation conditions.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). Existing backend tests include named deterministic fixtures and expected threshold outcomes. They verify examples but are not a blind generalization benchmark for diagnosis or allocation safety.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Write the benchmark protocol before evaluating: fault families, parameter ranges, noise/dropout/delay/corruption, simultaneous events, normal distractors, duration, seeds and outcome metrics.
2. Split by whole scenario families/topologies/parameter regimes, not random rows from the same trajectory. Separate development, calibration and held-out fixture bundles with hashes.
3. Keep hidden labels/truth out of the production API, inference input and developer replay. A separate evaluator joins predicted results to truth after execution.
4. Include overload versus hot-ambient/cooling ambiguity, shared upstream sag versus local interruption, missing/conflicting sensors, stuck values, reorder/delay and recovery chatter.
5. Freeze thresholds/policies before held-out evaluation; any retuning marks that set development and requires a fresh final set. If no independent custodian exists, label the process developer-held-out rather than fully blind.

#### Acceptance criteria

- [ ] Published manifest contains counts, family split, seeds/hashes and protocol version; no label-bearing feature leaks.
- [ ] The runner/report schema covers per-family precision/recall, false alarms, time-to-detect, location error, abstention/coverage and safety violations with denominators. Held-out results remain sealed until BM-17 and allocation candidates are frozen; development-only runs validate the infrastructure.
- [ ] All missed/uncertain cases remain in the report and are not discarded as inconvenient fixtures.

#### Verification

- Observation-only runner and label isolation tests; replay determinism and test/train-family disjointness.
- Run against an intentionally oracle-contaminated fake detector to prove the leakage guard catches it.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-02 / #4](https://github.com/Sanjith-Jam/blackout-mesh/issues/4) — Replace oracle-based fault detection with telemetry-derived inference
- [BM-05 / #7](https://github.com/Sanjith-Jam/blackout-mesh/issues/7) — Introduce a technically defensible electrical simulation boundary
- [BM-20 / #22](https://github.com/Sanjith-Jam/blackout-mesh/issues/22) — Establish hard safety constraints for uncertain occupancy predictions

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Synthetic performance cannot establish field accuracy. Fixture generation starts early; final execution follows the observation and safety contracts.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **3–5 days plus independent fixture review**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

### BM-17 — [Support simultaneous faults, hypothesis ranking and diagnostic abstention](https://github.com/Sanjith-Jam/blackout-mesh/issues/19)

<!-- blackout-mesh-backlog:17 -->
#### Priority and outcome

**P1 · BM-17 · diagnostics**. Multiple compatible fault hypotheses can coexist, while contradictory or unobservable causes lead to explicit uncertainty.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). The current hospital diagnose function returns the first matching branch, so overload can hide cooling failure. Campus diagnosis concatenates simulator flags; neither provides a ranked multi-hypothesis evidence model.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Replace first-match output with candidate hypotheses carrying asset/scope, supporting and contradicting observations, time window and evidence sufficiency.
2. Rank using transparent evidence rules initially; distinguish severity from likelihood and label heuristic scores as scores, not calibrated probabilities.
3. Allow simultaneous local cooling failure plus upstream sag, or overload plus cooling failure; encode shared-cause explanations without double-counting correlated sensor readings.
4. Define abstention criteria for stale/missing/contradictory evidence and indistinguishable causes; return unknown with the next sensor/check needed.
5. Expose the ranked result and evolution in incident history and both campus/hospital projections. Do not inspect held-out fixture labels while designing rules.

#### Acceptance criteria

- [ ] The detector can return more than one supported hypothesis and does not force a single fault.
- [ ] Indistinguishable observations yield an explicit ambiguous set/abstention rather than an invented exact cause.
- [ ] Severity, confidence semantics, evidence quality and affected location are independently represented.

#### Verification

- Developed simultaneous-fault matrix, contradiction/stuck-sensor and ambiguous equivalence cases.
- Evaluate once on the frozen held-out suite and publish rank/top-k/abstention results with denominator.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-02 / #4](https://github.com/Sanjith-Jam/blackout-mesh/issues/4) — Replace oracle-based fault detection with telemetry-derived inference
- [BM-16 / #18](https://github.com/Sanjith-Jam/blackout-mesh/issues/18) — Build blind adversarial synthetic scenario benchmark with held-out fixtures

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Ranking is not proof of causality. A likelihood percentage requires calibration data; until then use evidence strength labels.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **3–5 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

### BM-18 — [Benchmark allocation against fair baselines using external outcome metrics](https://github.com/Sanjith-Jam/blackout-mesh/issues/20)

<!-- blackout-mesh-backlog:18 -->
#### Priority and outcome

**P0 · BM-18 · benchmark**. Compare policies under identical demand/topology/capacity and outcome metrics defined independently of the optimization objective.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). fixed_priority_mask provides one reference on the six-service catalog, while allocator scores prioritize activity and policy choices. Winning the allocator's own score is not independent evidence of better service outcomes.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Run fixed priority, essentials-first without ML, round-robin/fair optional scheduling and the proposed policy on identical exogenous timelines. Use identical switching/restoration limits and random seeds.
2. Separate an oracle-occupancy upper bound clearly from deployable baselines; evaluate no-ML/always-UNKNOWN and classifier ablations.
3. Measure critical unmet Wh, essential unmet Wh, occupied-room optional service time, worst-room starvation, switching count, recovery latency and constraint violations. Integrate W over elapsed hours; do not call a snapshot watt difference measured energy savings.
4. Use independent occupancy labels only inside the evaluator. Report per-scenario outcomes, paired differences and session-level uncertainty where defensible.
5. Evaluate shortage, feeder loss, model mistakes, insufficient critical capacity, zero supply and recovery. Include failures and tradeoffs without selecting only favorable scenarios.

#### Acceptance criteria

- [ ] All baselines receive identical inputs and feasible-action constraints; objective weights cannot serve as the only evaluation metric.
- [ ] Zero unsafe allocations in the accepted benchmark; impossible critical demand is counted as unmet, not hidden.
- [ ] The report includes absolute units, sample denominators, policy versions and reproducible commands.

#### Verification

- Hand-computed energy integration fixture, baseline fairness checks and small-case optimality cross-check.
- Held-out outcome report with no-ML and UNKNOWN ablations and explicit classifier-error impact.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-04 / #6](https://github.com/Sanjith-Jam/blackout-mesh/issues/6) — Make allocation objectives configurable and output full decision explanations
- [BM-16 / #18](https://github.com/Sanjith-Jam/blackout-mesh/issues/18) — Build blind adversarial synthetic scenario benchmark with held-out fixtures

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Simulated service outcomes do not demonstrate real measured savings or comfort. Report regressions if the proposed policy loses on a relevant metric.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **3–5 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

### BM-19 — [Make RFID/software event semantics consistent with classroom demand and sessions](https://github.com/Sanjith-Jam/blackout-mesh/issues/21)

<!-- blackout-mesh-backlog:19 -->
#### Priority and outcome

**P1 · BM-19 · sessions**. One explicit room-use session model drives all software routes and future hardware adapters without using a card UID as occupancy truth.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). Latest ClassroomDemo supports multiple scanned rooms, explicit unscan, supply slider and model-ranked scanned-room optional loads. GridState still has one active_classroom_id, unknown-card selection clearing and separate classroom load events; hardware protocols use yet other semantics.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Define scan/start, duplicate scan, explicit end/unscan, expiry, unknown card, reset and reconnect semantics. Preserve simultaneous rooms and documented tie ordering.
2. Keep registered card mapping private; emit room/session IDs and source provenance. Debounce duplicate physical events without hiding genuine session end/start.
3. Separate requested equipment demand, session evidence, occupancy prediction and allocated output. Document whether default demand is requested independent of a session and how uncertainty protects essentials.
4. Make HTTP commands idempotent using command/session identity; define delayed/stale event handling, epoch boundaries and recorded replay interactions.
5. Publish a semantic compatibility table for GridState, ClassroomDemo and A/B hardware. Hardware remains paused; do not claim protocol integration from software agreement.

#### Acceptance criteria

- [ ] Equivalent UI and normalized RFID events produce the same room sessions and requested loads.
- [ ] Multiple active rooms survive navigation; unscan/expiry removes only the intended session; unknown cards follow a documented non-destructive policy.
- [ ] UID/scenario IDs never enter occupancy inference and session presence is not presented as a trained prediction.

#### Verification

- Duplicate/stale/out-of-order scans, unknown card, multi-room start/end, expiry, restart and reset.
- Contract fixtures for future hardware adapter without flashing devices.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-01 / #3](https://github.com/Sanjith-Jam/blackout-mesh/issues/3) — Unify campus, classroom and hospital under one authoritative simulation state
- [BM-20 / #22](https://github.com/Sanjith-Jam/blackout-mesh/issues/22) — Establish hard safety constraints for uncertain occupancy predictions

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Scan-only evidence does not prove people remain in a room. Session policies must expose uncertainty and never silently cut essential loads.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **2–4 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

### BM-20 — [Establish hard safety constraints for uncertain occupancy predictions](https://github.com/Sanjith-Jam/blackout-mesh/issues/22)

<!-- blackout-mesh-backlog:20 -->
#### Priority and outcome

**P0 · BM-20 · safety**. Predictions can influence optional service preferences but cannot silently remove essential or critical demand.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). The occupancy model has documented temporal false-INACTIVE errors. ClassroomDemo currently protects lights/computers while the campus policy ranks whole room services; these are inconsistent safety boundaries.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Define versioned protected hospital/room essential minima independent of ML output and RFID presence. Separate hard safety constraints from activity preferences.
2. Treat stale/missing/failed/OOD inference as UNKNOWN; use conservative defaults. A predicted INACTIVE alone cannot cancel protected requested load.
3. Specify policy for insufficient supply: report essential/critical shortfall, choose a declared fallback order and never fabricate capacity or call unmet minima feasible.
4. Add temporal persistence/hysteresis for optional changes where evidence warrants it; explicit manual overrides are logged and cannot bypass physical limits.
5. Propagate guard reasons to decisions/UI and enforce them in every authority/projection; restoration requires fresh conservative evidence, not just a high model score.

#### Acceptance criteria

- [ ] Property checks across all occupancy states never shed protected demand when a feasible protected plan exists.
- [ ] Zero/insufficient supply reports quantified shortfall and the correct infeasibility status.
- [ ] Classifier failure or conflicting sessions produces a visible conservative fallback with no hidden priority escalation.

#### Verification

- All ACTIVE/INACTIVE/UNKNOWN combinations, adversarial false-INACTIVE predictions and stale/OOD evidence.
- Source/feeder limits, disconnected branches, restore chatter and manual override constraints.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-01 / #3](https://github.com/Sanjith-Jam/blackout-mesh/issues/3) — Unify campus, classroom and hospital under one authoritative simulation state

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

This is a modeled safety policy, not certified electrical protection. No software plan can guarantee essential service when physical supply is insufficient.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **2–3 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

### BM-21 — [Make energy-flow graphics evidence-backed and label simulated quantities](https://github.com/Sanjith-Jam/blackout-mesh/issues/23)

<!-- blackout-mesh-backlog:21 -->
#### Priority and outcome

**P1 · BM-21 · visualization**. Every moving path and numerical reading identifies its evidence, freshness and simulation layer while retaining the approved game-style visuals.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). ClassroomBlueprint and hospital drawings derive flow from served flags/thresholded fixture voltage. The graphics are useful allocation illustrations but not measured electrical current or a coupled power-flow solution.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Define a backend projection for each edge: connected/reachable, commanded, simulated applied, observed energized, physical confirmed, quality, source and timestamp.
2. Use the selected view mode explicitly: allocation mode can show simulated power-service paths; electrical-study mode can show solver-derived voltage/current. Do not infer amps by visually scaling integer watts without voltage/power-factor assumptions.
3. Animate only the selected evidenced state; stopped/unknown/stale/disconnected paths have distinct text/legend treatment. Reduced-motion uses static indicators.
4. Map every sprite/wire to canonical asset/edge IDs and show a compact evidence explanation for a cut branch or uncertain diagnosis.
5. Keep proposed decisions, applied modeled state and hardware ACK state visually separate; ACK only changes on validated acknowledgment.

#### Acceptance criteria

- [ ] Every active path can be traced to a canonical edge/result revision; no flow across known-open topology.
- [ ] All quantities show units and modeled/recorded/observed provenance; animation speed is decorative unless quantitatively mapped and documented.
- [ ] UNKNOWN/stale does not look healthy and voltage-present does not falsely imply measured current.

#### Verification

- Topology trip, solver failure, stale telemetry, rejected command, pending restoration and wrong-session ACK screenshots/DOM assertions.
- Reduced-motion/keyboard/accessibility and sprite-to-edge mapping checks.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-02 / #4](https://github.com/Sanjith-Jam/blackout-mesh/issues/4) — Replace oracle-based fault detection with telemetry-derived inference
- [BM-05 / #7](https://github.com/Sanjith-Jam/blackout-mesh/issues/7) — Introduce a technically defensible electrical simulation boundary
- [BM-22 / #24](https://github.com/Sanjith-Jam/blackout-mesh/issues/24) — Add cross-route consistency contract for scenario state, numbers and units

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Preserve the light tiled visual style; this issue fixes semantic truth rather than authorizing another global redesign.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **2–3 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

### BM-22 — [Add cross-route consistency contract for scenario state, numbers and units](https://github.com/Sanjith-Jam/blackout-mesh/issues/24)

<!-- blackout-mesh-backlog:22 -->
#### Priority and outcome

**P1 · BM-22 · contract**. Different visualizers remain distinct layouts but must agree on shared site/run facts and explicitly label scoped totals.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). Campus, classroom and hospital endpoints currently have independent identity/state conventions. Different supply totals and fixture numbers are not reconciled under one run/revision contract.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Define site_id, run_id, server_epoch, state_revision, catalog/policy/model versions and observation timestamps in every projection.
2. Specify unit rules: integer W for control budgets, V/A/degC for sensors, Wh/kWh only for time-integrated quantities; define power-factor/phase assumptions for any conversion.
3. Define campus totals, zone totals and equipment totals plus additive relationships. Do not compare a whole-campus source capacity with classroom-only served load without scope labels.
4. Make route changes select projections, not create/reset simulations. Explicit profile switches create a new run identity and clear stale cached projections.
5. Contract-test shared asset status, active sessions, fault result identity, scenario revision and applied masks across API and WebSocket responses.

#### Acceptance criteria

- [ ] All routes at one revision agree on shared facts and totals reconcile within declared scope.
- [ ] Reset/profile switch cannot leave a previous run visible as live on another page.
- [ ] Unknown/null is consistent across Python, generated TS and UI formatting; missing readings are not zeros.

#### Verification

- Normal/shortage, multi-room demand, fault+reset, rapid navigation and concurrent HTTP/socket refresh.
- Unit conversion fixtures and same-revision canonical projection digest comparison.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-01 / #3](https://github.com/Sanjith-Jam/blackout-mesh/issues/3) — Unify campus, classroom and hospital under one authoritative simulation state
- [BM-11 / #13](https://github.com/Sanjith-Jam/blackout-mesh/issues/13) — Fix WebSocket reconnect lifecycle and synchronize state revisions
- [BM-12 / #14](https://github.com/Sanjith-Jam/blackout-mesh/issues/14) — Generate TypeScript API types from the FastAPI OpenAPI schema

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Different facility views need not show identical totals, but must show explicit scope and correct aggregation. Avoid duplicating control state in Zustand.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **2–3 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

### BM-23 — [Replace client-only chart buffers with server history and replayable incident timelines](https://github.com/Sanjith-Jam/blackout-mesh/issues/25)

<!-- blackout-mesh-backlog:23 -->
#### Priority and outcome

**P1 · BM-23 · history**. Charts and incident timelines query durable server history and can replay past decisions without mutating a live run.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). DemoDashboard stores the last 50 socket samples in component state and formats local clock strings. GridState retains only 50 in-memory events; page reload loses client series and ordering context.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Add cursor/time-range history endpoints keyed by site/run with stable UTC timestamps and revision/event IDs. Distinguish sampled telemetry from event/decision records.
2. Use SQLModel/SQLite indexes and retention/aggregation policies; never store every identical rendered frame as a new decision.
3. Use TanStack Query for pagination, cancellation, cache keys and incremental history refresh. Append/deduplicate socket events by ID and backfill gaps from the server.
4. Build read-only replay over recorded inputs/decisions with explicit LIVE versus HISTORY mode. A what-if simulation must fork a new run, never overwrite historical evidence.
5. Show linked incident → observation evidence → decision → applied transition → validated ACK trail, with absent links explicitly pending/unknown.

#### Acceptance criteria

- [ ] Reload/navigation recovers the same timeline and chart range; duplicates and reconnects do not double-count.
- [ ] Replay does not issue commands or advance the live controller.
- [ ] Historical charts retain original UTC timestamps and provenance; timezone formatting happens only at presentation.

#### Verification

- Pagination boundaries, equal timestamps, duplicate events, retention boundary, restart and gap backfill.
- Replay determinism from persisted evidence and command/ACK association correctness.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-10 / #12](https://github.com/Sanjith-Jam/blackout-mesh/issues/12) — Persist incidents, state transitions and control decisions to SQLite
- [BM-11 / #13](https://github.com/Sanjith-Jam/blackout-mesh/issues/13) — Fix WebSocket reconnect lifecycle and synchronize state revisions
- [BM-12 / #14](https://github.com/Sanjith-Jam/blackout-mesh/issues/14) — Generate TypeScript API types from the FastAPI OpenAPI schema

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Persist enough input/policy/model identity to reproduce a result; a chart of outputs alone is not a causal replay record.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **3–5 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

### BM-24 — [Make sites, facility inventories and policies configurable without editing Python source](https://github.com/Sanjith-Jam/blackout-mesh/issues/26)

<!-- blackout-mesh-backlog:24 -->
#### Priority and outcome

**P2 · BM-24 · configuration**. Validated versioned site profiles define inventories/topology/policies while keeping one authority and known good examples.

#### Current evidence

Reviewed repository baseline: `d1c58d7ae49a376610d52cf82edf3a72e31bf72e` (2026-10-10). SERVICE_CATALOG, CLASSROOMS, HOSPITAL_ROOMS, visualizer LOADS/ZONES and electrical thresholds are Python constants with different conventions.

This is pending implementation work, not a claim that the proposed design or tests already exist.

#### Implementation scope

1. Start with a strict Pydantic-validated JSON site profile: globally unique asset IDs, parent/leaf grouping, feeder/source links, ratings/units, optional device coordinates and policy references.
2. Keep sensitive RFID enrollment/credentials in private external configuration. Catalog files contain aliases/room mappings, not raw secrets.
3. Validate graph connectivity, dangling IDs, cycles where unsupported, non-negative finite quantities, essential minima and conflicting parent/child accounting before activation.
4. Hash config/policy versions into runs and decisions. Apply config changes as an explicit validated new run or safe migration, never live partial mutation.
5. Provide the current campus and a second small test site without source edits. Generate visual inventory from asset types and fallback sprites instead of hardcoded CR1/2/3 assumptions.

#### Acceptance criteria

- [ ] Two sites with different room/load counts run from configuration only and retain deterministic allocation/projections.
- [ ] Invalid topology, duplicate IDs, bad units or impossible declared ratings fail with actionable diagnostics before activation.
- [ ] Existing profile reproduces the approved reference behavior and each decision records its configuration hash.

#### Verification

- Round-trip/schema migration, invalid-config matrix, alternate-site API/UI and parent/child watt reconciliation.
- Topology and policy compatibility checks using NetworkX and the selected electrical adapter where enabled.

Run the existing backend checks and frontend production build when their behavior/contracts are touched. Add targeted failing-before/passing-after coverage; preserve errors, null evidence and transport identity checks. Record exact commands, results, artifact/config versions and remaining limitations in the delivery notes.

#### Dependencies and boundaries

- [BM-01 / #3](https://github.com/Sanjith-Jam/blackout-mesh/issues/3) — Unify campus, classroom and hospital under one authoritative simulation state
- [BM-04 / #6](https://github.com/Sanjith-Jam/blackout-mesh/issues/6) — Make allocation objectives configurable and output full decision explanations
- [BM-05 / #7](https://github.com/Sanjith-Jam/blackout-mesh/issues/7) — Introduce a technically defensible electrical simulation boundary

Dependencies are blocking completion, not a reason to delay independent design or fixtures. BM identifiers are stable plan IDs, not assumed GitHub issue numbers.

#### Risks and non-goals

Issue 01 introduces the minimal shared inventory now; this issue generalizes and hardens it later. Do not add a visual configuration editor unless separately requested.

Hardware remains paused. No real power switching, certified protection, campus accuracy or energy-saving claim is authorized by this issue. Preserve private enrollment/reuse files. Keep the approved interface theme and split implementation into reviewable commits.

#### Delivery and estimate

Planning estimate: **3–5 days**; unmeasured and dependent on integration/data availability. Deliver code/config/docs, targeted tests, reproducible evidence and an explicit limitation list. Update CONTEXT.md and PROGRESS_REPORT.md when work actually lands. Do not close this issue on planning alone.

