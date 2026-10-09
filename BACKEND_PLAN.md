# BACKEND IMPLEMENTATION PLAN

*(Extracted exactly from PRIORITYGRID_UNIFIED_IMPLEMENTATION_PLAN.md)*

## 8. Simulator and fault injection

### 8.1 Graph and world state
Use NetworkX `DiGraph` or typed tree structures: `Source`, `Bus`, `Edge(id, from, to, max_kw, closed, faulted)`, `Load(id, bus, demand_kw, tier, enabled, min_off_ms, manual_lock)`. Validate on load: exactly one source; DAG/tree for MVP; no negative demand; each load bus exists; no duplicate IDs; constraints are positive. Snapshot world state before each tick for reproducible replay.

### 8.2 Electrical simplification
- **Availability:** energizable if connected by closed, healthy edge path to energized source and local source/feeder constraints can support that assignment.
- **Demand:** `demand_kw` known as a scenario load property; telemetry reports requested/served demand with controlled noise. `available_capacity_kw` from trusted source reporting.
- **Line loading:** for radial lines, calculated `flow_kw(edge) = Î£ served demand_kw` in the downstream subtree; require `flow_kw(edge) â‰¤ max_kw(edge)` for operating plans.
- **Voltage proxy:** e.g. `v_pu = clip(1.0 âˆ’ 0.02 Ã— (path_loading_fraction) + scenario_depression + Gaussian_noise, 0, 1.10)`; for disconnected/islanded bus without source, `v_puâ‰ˆ0` with noise floor. This equation is **heuristic telemetry generation**, not Ohm/Kirchhoff power flow. Document generation/noise before held-out evaluation; do not tune the generator to flatter the controller.
- **Sensor faults:** introduce offset, stale stream, freeze or random spikes on one report; never modify world truth when simulating a sensor fault.
- **Communications fault:** drop observation packets on simulated virtual nodes; for actual ESP32 peer failure, loss belongs to physical indicator network and need not alter synthetic grid electrically.
- **Ground truth:** `scenario_truth` stored by evaluation runner in a separate module and withheld from engine. Runtime operator may still view injection instructions in demo panel; dashboard must distinguish *what was injected* from *what the engine inferred*.

### 8.3 Scenario catalog, predefined before testing
| ID | Event | Observable pattern (illustrative) | Correct expected effect |
|---|---|---|---|
| S00 | NORMAL_STEADY | stable source/demand/v_pu | all reachable loads served, no alarm |
| S01 | NORMAL_VARIATION | moderate demand fluctuations | baseline adapts, no confirmed fault |
| S02 | CAPACITY_DERATE | source cap 100â†’52 kW | capacity-shortage incident; optimize compliant shedding |
| S03 | F2_FEEDER_OPEN | bus C drops to no-source state | L_LAB + L_CLASS unreachable, no false restoration |
| S04 | F1_FEEDER_OPEN | bus B disconnected | L_CLINIC + L_HOSTEL unreachable; show critical coverage risk |
| S05 | SENSOR_BIAS | one `v_pu` shifted independent of peers | degraded sensor trust / uncertain diagnosis |
| S06 | SENSOR_STUCK | identical repeated sensor samples while peers vary | sensor-health alert, no false electrical certainty |
| S07 | VIRTUAL_REPORT_LOSS | simulated downstream stream disappears | stale/communication hypothesis, no electrical claim absent evidence |
| S08 | PHYSICAL_ESP_NOW_LOSS | remote ESP32 off/radio muted | physical device-link failure, simulator electric state unchanged |
| S09 | TRANSIENT_DIP | short voltage-proxy dip | info event; no hard shutdown if below persistence threshold |
| S10 | INTERMITTENT | repeated open/closed telemetry disturbance | repeated-event warning and anti-flap |
| S11 | DUAL_EVENT | capacity shortage + missing sensor | conservative fallback / trust gate |
| S12 | RESTORE_CAPACITY | cap 52â†’100 and stabilized | ordered re-service after cooldown |
| S13 | FEEDER_REPAIRED | F2 closes explicitly in simulator | newly reachable loads eligible for restoration |
| S14 | RECOVERY_INTERRUPTED | second derate during restoration | cancel/recompute stale plan, no oscillation |
| S15 | CRITICAL_INFEASIBLE | cap < aggregate T0 demand | report inability to preserve all essential loads; never invent capacity |

Define YAML/JSON scripted events (`seed`, `duration_ms`, `steps`, `expected`). Maintain **at least one normal control run** for every fault family. Include event injection time, pre-state and expected truth. Support reset, pause and step first; faster playback and deterministic re-execution are optional. History remains available.

## 9. Fault detection, diagnosis, trust and explainability

### 9.1 Feature and baseline layers
1. Validate samples (`source`, finite values, timestamp order, units, monotonic sequence). Out-of-range/no-data becomes a **quality event**, not proof of an electrical fault.
2. Smoothing: last-3-sample median for spike suppression; keep raw trace for transient detection.
3. Baselines: initial normal window median and robust spread `MAD Ã— 1.4826` with nonzero floor. Keep a fixed **golden profile** and an adaptive normal baseline.
4. Gated EWMA adaptation: record alpha (initial 0.05 at 5 Hz); update only in `NORMAL` with fresh trusted samples and residual within the normal envelope; **freeze on SUSPECTED, CONFIRMED, CRITICAL, SENSOR_UNTRUSTED**. This prevents learning a persistent shortage as â€œnormalâ€.
5. Compute independent features: `demand/capacity`, `v_pu` residual vs expected synthetic load behavior, neighbor agreement, downstream connectivity consistency, stale/heartbeat age, variance/stuck, rate-of-change and persistence.
Baseline warm-up is explicit. Initialize golden limits from documented configuration/development-normal data; a faulty startup must not redefine normal. Hard capacity guards remain active during warm-up. Constant samples alone do not prove a stuck sensor; require independently expected variation or timestamp/counter inconsistency.

6. Simple change-point/CUSUM advisory for slow drift if time remains; optional Isolation Forest is **not** needed for P0 and must not directly actuate critical decisions.

### 9.2 Explicit hypotheses; no blind single score
`NORMAL`, `SOURCE_CAPACITY_SHORTAGE`, `FEEDER_OPEN(edge_id)`, `VOLTAGE_PROXY_ANOMALY`, `SENSOR_FAILURE(node_id)`, `VIRTUAL_NODE_COMM_LOSS(node_id)`, `ESP_NOW_DEVICE_LOSS(node_id)`, `TRANSIENT`, `INTERMITTENT`, `UNKNOWN_OR_COMBINED`.

For each feeder hypothesis, forward-simulate which downstream buses **should** have low voltage/zero served power; compare to *observed* sensor subset. Use a **compatibility score** (bounded, transparent weights) that rewards matching observations and penalizes contradictions. Report first and second candidates plus a margin. The hypothesis with lowest observed disagreement is not necessarily uniquely identifiable. Example: if all downstream sensors are missing, feeder F2 vs F5 may be observationally identical â†’ **ABSTAIN** and request an independent simulated measurement if available.

**Power/control decisions and diagnosis uncertainty:** A confirmed capacity shortage from trusted source capacity may still permit safe, constrained simulated shedding; an ambiguous feeder fault may require **hold/observe** instead of restoring downstream. Do not shut down essential simulated loads purely because one radio/display node failed.

### 9.3 Recommended two-level state machines
**Fault classifier FSM:** `NORMAL â†’ SUSPECTED â†’ CONFIRMED â†’ CRITICAL`; support `UNVERIFIED`, `RECOVERING`, acknowledgment and latched events per incident. Electrical class, observation quality and physical link health stay independent; simultaneous defects are not one exclusive class. Example initial values: 3 consecutive anomalous ticks to suspect (0.6 s at 5 Hz), â‰¥5 additional ticks to confirm (1.0 s), critical severity after persistent evidence; hard capacity/connectivity guards shed immediately without waiting for diagnostic confirmation; clear only after â‰¥10 stable ticks (2 s). Tune with holdout tests; these are **prototype defaults**, not safety-relay settings.

**Controller FSM:** `MONITORING â†’ DIAGNOSING â†’ SHEDDING â†’ STABILIZING â†’ RESTORING â†’ MONITORING`, plus `DEGRADED`, `MANUAL_PAUSE`, `INFEASIBLE`. Controller state is separate from fault class; comm loss shouldn't force simulated shed.

**Hysteresis:** example source `capacity_drops` can trigger shedding promptly; restoration requires the configured reserve (default **0 W**), fresh stable evidence for **5 s**, per-load min-off **3 s**, and at most one new ON per **1 s**. Capacity/evidence change resets the wait. Solver, validator and all baselines use the same reserve. These are configurable, unvalidated first-pass choices. Do not implement reconnection every UI frame.

### 9.4 Unknown evidence behavior
Missing electrical evidence is not an outage. Unknown branch: forbid new ON transitions and count retained ON demand at its full configured value. Fresh lower source capacity can still trigger shedding. Unknown source capacity: hold/observe, inhibit restoration, show `capacity_unknown` and do not label supply guaranteed feasible. Shed/replan or expose an unresolved condition if retained assumptions violate known constraints.

A fresh open contact is `FEEDER_OPEN_OBSERVED`, not inferred localization. Without contact evidence, keep all compatible feeder/sensor hypotheses and abstain when indistinguishable. Exclude direct-status cases from inferred-location accuracy.

### 9.5 Explainability and provenance in the UI
For every incident: raw/normalized observations, time, sensor/source trust, top hypotheses, **which evidence supports each**, contradictions, missing evidence, score described as *inference score (heuristic, not P(fault))*; what control action was taken, who/what triggered it, constraints, alternative plans rejected, and whether any load was unreachable.

Example rationale: â€œ**52 kW available; 84 kW requested.** Clinic and emergency lights are reachable and T0 priority. Controller served feasible T0/T1 loads and selected additional loads within 52-kW system/branch limits. Lab and classroom may be excluded because of constraints. Action was **simulated**; ESP32 indicators reported ACK.â€ (Specific loads depend on solver output.)

## 10. Mathematical optimization, controlled execution and recovery

### 10.1 Exact policy, solver status and application guard
Binary served requests `x_i` use integer demand W. Total demand must be â‰¤ max(0, source capacity âˆ’ reserve); default reserve=0 W. Enforce every feeder subtree limit, known reachability, lockouts and Â§9.4 unknown-state constraints.

Maximize lexicographically: T0 service count; T0 importance (clinic=2, emergency=1); T1 count; T2 count; T3 count; negative switching count; negative global mask. Earlier objectives dominate all later ones. Count is the benefit; watts are a constraint. The illustrative policy omits clinical validation, interruption duration, partial service and startup surge.

Optimize CP-SAT stages sequentially, fixing proven optimal stages only. Start with a **100-ms total budget**, one worker and fixed seed. FEASIBLE/UNKNOWN is not proof of the full lexicographic optimum; use exact enumeration on timeout/tool failure and identify fallback. Invalid configuration/model is an error. Exact fallback is limited to ten tested loads.

Before application, independently validate capacity, branch constraints, reachability, freshness, cooldown and current control revision. Reject stale/infeasible plans. Modeled delivered power never exceeds available supply; requested demand is separate.

Default is best effort plus explicit unavailable critical IDs/reasons (`capacity`, `feeder`, `unknown_evidence`). Optional strict-critical policy reports `CRITICAL_INFEASIBLE` rather than silently relaxing requirements. At zero supply all loads are unavailable.

Primary 52,000-W case: clinic + emergency + server + hostel = **52,000 W**, mask **23**. Catalog-order priority greedy ties. At 55,000 W: clinic + emergency + server + lab = **54,000 W**, mask **15**, using the stated final tie-break. These are arithmetic expectations, not measured results.

### 10.2 Independent exact-enumeration oracle (for 7 loads)
With 7 binary loads, there are `2^7=128` candidate assignments. Test every combination: reject unreachable/branch/capacity violations, choose lexicographic objective winner. Use this as (a) a fallback, (b) validation that CP-SAT results are correct and (c) a judge-friendly explanation of optimality on small networks. Our project may grow later, where CP-SAT is more scalable.

### 10.3 Fair comparison
Compare fixed catalog-order priority greedy and smaller-demand-first greedy within tiers against exact/CP-SAT, with identical observations, demand, topology, reserve, branch limits and transition eligibility. Retain the six-load regression (Â§3.4). Publish ties and failures, not only favorable examples. Separate service-objective differences from arbitrary final mask tie-breaks. Report critical/important services, switching, shed demand and runtime; never import upstream benchmarks.

### 10.4 Autonomous simulated action policy
**Committed implementation choice for this blueprint:** default `AUTO_SIM` acts automatically only in sandbox. Add UI button `PAUSE_AUTOMATION` and mode `RECOMMEND_ONLY` (if time). Executor validates current snapshot/version, trusted feeder reachability, reserve, cooldown, and manual locks. Reject stale or unsafe plans with audit trail. Hardware LEDs mirror **applied simulated state**, not power authority.

### 10.5 Restoration
When source capacity returns: no instant â€œall onâ€. Wait stable 5 s with fresh evidence; compute a feasible plan; apply necessary OFF transitions first, then at most one new ON per 1 s with 3 s minimum OFF dwell and ensure feeder constraints remain satisfied. If capacity drops again, **cancel pending restoration**, mark `RECOVERY_INTERRUPTED` and reoptimize. Clear a latched event only when resolved and acknowledged if configured; acknowledgment does not repair its cause. Backend restart creates a new paused run/session and reconciles devices instead of resuming old pending commands.

### 10.6 Counterfactual decision log
Store best solution plus up to two alternatives (greedy baseline and one manually forced/illustrative candidate), with `why rejected`: insufficient capacity, violates branch, unreachable due to open feeder, lower-priority objective, or cooldown. This differentiates the product without adding an unrelated chatbot.

## 11. Embedded firmware and physical demo
## 12. Backend API, WebSocket and persistence

### 12.1 REST endpoints â€” contract targets
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | process, DB, simulation clock, serial bridge status |
| GET | `/api/state` | authoritative complete current snapshot |
| GET | `/api/topology` | static topology/config for React Flow |
| GET | `/api/scenarios` | scenario IDs, descriptions and demo order |
| POST | `/api/scenarios/{id}/run` | queue scenario start; seeded; return run ID |
| POST | `/api/simulation/pause` | pause/unpause playback |
| POST | `/api/simulation/reset` | restore initial defined state; increment version |
| POST | `/api/injections` | inject typed event (`CAPACITY_DERATE` etc.) |
| GET | `/api/incidents` | paginated incident list |
| GET | `/api/incidents/{id}` | evidence, decisions, state transitions |
| GET | `/api/actions` | history of proposed/applied/rejected control actions |
| POST | `/api/control/mode` | `AUTO_SIM`, `RECOMMEND_ONLY`, `PAUSED` |
| POST | `/api/control/acknowledge` | operator acknowledge latched simulated incident |
| GET | `/api/hardware` | gateway/peer/command/heartbeat status |
| GET | `/api/evaluations` | measured benchmark summaries; no hand-filled figures |
| POST | `/api/evaluations/run` | **optional** async benchmark run / return run ID |
| GET | `/api/replays/{incident_id}` | scenario seed + saved state/evidence trace |
| WS | `/ws/live` | initial snapshot plus sequenced event updates |

Use Pydantic models for every request/response, static enums for injection types, and error responses for invalid IDs/negative capacity. Requests from physical buttons and dashboard become the same typed commands. Bind to `127.0.0.1`; validate Host/HTTP Origin/WebSocket Origin against the local app and prefer same-origin serving or Vite proxy. CORS alone is not authentication. If LAN mode is explicitly enabled, restrict exposure and require an operator token on mutations/WebSocket access. Apply run/revision/idempotency checks to every mutation, including buttons. Bound serial/WS/history/queue input, use parameterized SQL and keep serial/solver work off the publication loop. Expose writer/backpressure failures instead of silently dropping incidents.

### 12.2 SQLite entities (minimum)
| Table | Required data |
|---|---|
| `scenario_runs` | ID, scenario, seed, start/end, config snapshot, source label |
| `grid_snapshots` | run ID, time, version, serialized state (downsampled) |
| `observations` | run, time, node, field, value, provenance, quality |
| `incidents` | open/closed, label, inferred class, rank/score, evidence JSON, abstain |
| `decisions` | incident ID, solver status, constraints, objective, rejected alternatives |
| `actions` | decision ID, attempted/applied/rejected, reason, before/after state, timestamps |
| `hardware_events` | node/session, seq, commands, ACKs, RSSI if available, link failures |
| `evaluation_runs` | seeds/splits, confusion matrix and measured timing fields |

SQLite WAL; bounded write queue; version the schema; a disposable development DB is acceptable, but never overwrite/delete existing user data or results to resolve migration. Back up/export before destructive reset. Keep an append-only JSONL mirror for incident/action logs if easy. Avoid per-200ms full-db writes on every load in critical loop.

### 12.3 Replay contract
Replay reads saved state/observation stream and **restores pipeline's pre-incident baseline/FSM state**. Re-run pure functions with same configuration and seed; compare generated diagnosis/action trace to stored original. A â€œplay historical snapshotsâ€ UI is acceptable at MVP even if true deterministic re-execution is delayed; label the mode honestly (`HISTORY_PLAYBACK` versus `DETERMINISTIC_REEXECUTION`). Replay must not send physical LED commands by default. Persist raw observations, golden/adaptive baseline, filter windows, per-incident FSM, prior masks, cooldown/restoration timers, config/policy version and event order; seed alone is insufficient for stateful re-execution. Compare logical outcomes, not radio timing.


