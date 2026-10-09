# Blackout Mesh — Unified Implementation Blueprint

**Version:** 1.2 (required lab-activity ML; nine-load primary catalog)  
**Updated:** 9 October 2026 · **Execution:** component tasks; human staffing assignments removed  
**Time box:** 24 working hours · **Incremental hardware budget:** ideally ₹0–₹300, ceiling approximately ₹1,500  
**Chosen direction:** intelligent fault-aware power-management product; lightweight digital twin is its supporting simulation/evaluation environment.  
**Project tagline:** **Detect → Diagnose → Optimize → Act → Explain → Recover**

> **Status key:** **COMMITTED** = previously agreed project direction; **SPECIFIED** = concrete engineering choice made in *this* blueprint, to implement unless blocked; **OPTIONAL** = only after core delivery; **NOT CLAIMED** = deliberately outside prototype capabilities. Numeric thresholds and targets below are initial settings or goals, **not measured outcomes**.

## Required lab-activity revision — read first

[Lab activity ML plan](LAB_ACTIVITY_ML_PLAN.md) specifies the current primary catalog, model, features/data/evaluation, objective, hardware and phased delivery. It supersedes conflicting earlier example values below. A trained lab-activity classifier is now required, not optional. The first model candidate is Random Forest, compared with rules and logistic regression on held-out session groups.

The primary has **nine loads / 512 masks**: original lab 16 kW becomes Labs A/B/C at 6/6/4 kW. Configured demand remains 84 kW. ESP32 B displays all nine bits (`0x01ff`); A reads three Lab-ID cards and four controls. Exactly two working ESP32s are available, no Arduino board or displays. Phase 0 is complete by user declaration.

ML estimates ACTIVE/INACTIVE, abstaining to UNKNOWN when evidence is uncertain or stale. A fixed policy maps that estimate into lab priority; clinic/emergency/server priorities and all electrical constraints remain binding. Inputs are simulated or explicitly emulated session/presence/activity observations; no real multi-lab occupancy instrumentation currently exists. RFID identifies a lab; it never directly sets priority or proves occupancy.

The seven-load catalog, 128-mask oracle, B3/C4 split, three-board/display inventory and examples below are **legacy v1.1 regression references**, not the current primary build. The six-load fixture is also historical. General state ownership, fault diagnosis, recovery, replay, validation and measurement rules carry forward unless explicitly revised by the linked ML plan. No manual Balanced/Shelter/Lab card policy is part of the new primary.

## Contents
1. Mission and design contract
2. How the two ideas combine; what does not transfer
3. Exact demo problem, topology, loads, assumptions
4. End-to-end system architecture and authoritative state
5. Locked technical stack and rationale
6. Repository layout, setup, developer workflow
7. Data contracts, events, serial/radio packets
8. Simulator and scenario engine
9. Detection, diagnosis, trust, uncertainty
10. Optimization, autonomous execution, recovery
11. Firmware and physical hardware plan
12. API, WebSocket and database
13. React dashboard and judge experience
14. Component dependencies and integration gates
15. 24-hour build schedule with gates
16. Test suite, benchmark metrics and acceptance criteria
17. Demonstration and three-minute pitch
18. Risk register, fallbacks, scope discipline
19. Component inventory, procurement, electrical safety
20. Prior art, references and license hygiene
21. Decisions, exclusions and explicit claims
22. Immediate startup checklist and future revisions

---

## 1. Mission and design contract

### 1.1 The problem
A campus or small microgrid experiences **supply derating**, **feeder interruptions**, **abnormal sensor reports** or **communications outages**. Simple monitors can raise alarms, but do not determine what to keep running with limited capacity or explain what evidence supports their diagnosis. Our prototype will diagnose the event from **synthetic telemetry** and compute and execute **simulated load assignments**, while **real ESP32 nodes** exchange instructions/acknowledgements and show load status with LEDs.

### 1.2 Single-sentence deliverable
A locally runnable, live-control-room demonstration in which an operator injects a scenario, Blackout Mesh infers what happened without reading scenario ground truth, identifies reachable loads, uses constrained optimization to decide what may run, applies those decisions in the simulated network, sends low-voltage display commands over a real ESP-NOW peer link, and logs/explains/replays the outcome.

### 1.3 Must succeed in a clean 3-minute demo
- Start from normal state: all healthy loads served and green.
- Inject **capacity drop**: noncritical simulated loads shed, essential ones preserved **only if source and feeder capacity allow**.
- Inject **open feeder**: downstream loads are *unreachable*; spare upstream capacity does **not** magically power them.
- Drop an actual radio peer: classify **radio/device link fault** and mark hardware status stale; do **not** label a simulated electric outage by default.
- Restore source/feeder state: wait for hysteresis/stability, then controlled reconnection.
- Open a diagnosis: evidence **for**, evidence **against**, score marked **heuristic, not probability**; event is replayable.
- Show an honest evaluation panel: measured simulation accuracy/latency and a comparison with a greedy baseline (numbers computed, never invented).

### 1.4 Guardrails
- **No mains, no household wiring, no real switching/protection, no solar/battery electrical hardware, no certified safety claims.** LEDs represent decisions only.
- **SIMULATED** tags on synthetic voltage/current/power and power-flow values. A powered LED is a **PHYSICAL INDICATOR**, not evidence of physical kilowatt flow.
- Two/three ESP32s with ESP-NOW form direct peer communication, **not a routing mesh**. No claim of autonomous restoration of an electrically broken feeder.
- Basic local LED/communication behavior may survive a laptop outage; full power optimization **requires the laptop** in this build.
- Optimization is genuine (OR-Tools CP-SAT or independently checkable exact enumeration); required lab-activity ML must be trained and compared with deterministic baselines; optional fault-novelty ML remains separate.

## 2. Combination: what is borrowed and what is deliberately changed

| From BLACKOUT MESH blueprint | Unified PriorityGrid use | Transfer? |
|---|---|---|
| State machine with persistence, hysteresis, recovery, latched simulated trip | **Separate fault FSM and operating/control FSM**; prevent flashing, false alarms and unsafe reconnection | **YES, core** |
| Adaptive EWMA baseline frozen during abnormal events, golden/reference baseline | Apply to **synthetic** voltage proxy and demand/residual telemetry; do not absorb long faults as normal | **YES, core** |
| Multi-signal fusion, evidence weights, contributions, trust gating | Rank fault hypotheses with contradictions and abstain when evidence insufficient | **YES, core** |
| Disambiguate peer radio failure vs load anomaly | Track radio link *from actual ESP-NOW ACK/heartbeats*, electrical faults *from synthetic sensors*; keep failure domains separate | **YES, core** |
| Independent measurement of shared physical bus with dual ADCs | Not applicable to simulated-only grid; create independent **simulated witness streams** with independently sampled noise; label SIMULATED | **NO physical ADC replication** |
| Feeder/shunt Ohm/Kirchhoff residuals, ADC calibration, real 3.3V electrical load emulator | Original blueprint's optional physical sensing extension, **not a requirement**; don't treat synthetic traces as measured | **DEFER** |
| First-order thermal model | Optional **estimated** overload risk (`°C-equivalent`), with stated assumptions, not real measured temperature | **OPTIONAL** |
| Explainable alarms, provenance categories, event timeline, replay | Preserve causality and evidence before/after action | **YES, core** |
| Fault injection, held-out tests, confusion matrix, failure chaos tests | Build deterministic seeded simulation, automatic benchmark suite | **YES, core** |
| Original vanilla-JS UI and two-node sensing topology | Replace with chosen **React + TypeScript + shadcn/UI/React Flow** and gateway + remote LED nodes | **NO, superseded** |
| Simple alarm/trip | Add genuine **OR-Tools prioritization, feeder constraints, autonomous simulated actions, staged restoration** | **PRIORITYGRID contribution** |

**Do not merge two incompatible assumptions:** the source BLACKOUT MESH blueprint is a low-voltage measurement project with ADC-specific claims; this project explicitly uses **simulated electrical data**. Physical component reuse and measurement logic are inspiration, not proof that PriorityGrid measures actual grid conditions.

## 3. Demonstration model: topology and catalog

### 3.1 Power network, explicit limits
Use a **radial campus feeder**, one grid source and seven loads. Backup sources/alternative routes are deferred; at zero source capacity no service is preserved. The graph is **not a real AC load-flow model**.

```text
                                    SOURCE S (100 kW nominal)
                                               |
                                      F0 (100-kW cap)
                                               |
                                            BUS A
                                           /     \
                               F1 (60 kW) /       \ F2 (55 kW)
                                         /         \
                                      BUS B       BUS C
                                      /   \         /   \
                                   F3/     \F4   F5/     \F6
                                    /       \     /       \
                                CLINIC    HOSTEL LAB     CLASSROOM
                                 18 kW     14 kW 16 kW     10 kW

       Additional branch at BUS A: F7 → EMERGENCY LIGHTS 8 kW;
       F8 → SERVER ROOM 12 kW; F9 → AMENITIES 6 kW.
```

Total demand = **84 kW** (18+14+16+10+8+12+6). Nominal source=100 kW. For a visible shortage inject **52 kW** or **55 kW**, not merely 60 unless meaningful shedding follows. **All values are fictional simulated campus demands**; no field metering claim.

| Load ID | Role | Demand (kW) | Tier | Value / reason | Bus |
|---|---|---:|---|---|---|
| L_CLINIC | Clinic equipment | 18 | T0 essential | highest essential service | B |
| L_EMERG | Emergency lighting | 8 | T0 essential | safety service | A |
| L_SERVER | Server/network room | 12 | T1 high | service continuity | A |
| L_LAB | Laboratory | 16 | T2 normal | avoid unnecessary loss | C |
| L_HOSTEL | Hostel common area | 14 | T2 normal | service continuity | B |
| L_CLASS | Classroom | 10 | T3 deferrable | can be shed | C |
| L_AMEN | Decorative/amenities | 6 | T3 deferrable | can be shed first | A |

Internal electrical quantities are **integer watts**; kW is for display. Global load bits follow catalog order: clinic=0, emergency=1, server=2, lab=3, hostel=4, classroom=5, amenities=6. B mirrors bits 0–2; C mirrors bits 3–6.

**Source-to-load reachability is authoritative.** If F2 is open, Lab and Classroom must report **unreachable and unserved**, even if optimization sees unused kilowatts at source. F1/F2 branch limits apply to the sum of accepted downstream loads. Changing a physically broken feeder state is **not** an executable automatic action in this prototype; restoring F2 is a new *simulated event* initiated by the scenario operator.

### 3.2 Two separate incident types that must not be conflated
**Supply shortage:** source `capacity_kw=52` but feeder graph still connected. Optimization sheds loads so `Σ served_kw≤52`. Local LEDs visualize result.  
**Feeder open:** the simulator de-energizes descendants of a severed line; optimizer cannot reconnect them unless a separately represented, reachable source/closed alternative feeder exists. An engineer/judge can trigger *repair/reset* in the simulator; then staged reconnection becomes possible.

### 3.3 Simplification note
The simulator represents connectivity, nameplate capacities, scalar load demand, and **synthetic per-unit voltage proxies**, not a validated nonlinear AC power flow. Do not label a trace “measured voltage”, model line heating or losses as verified, nor infer amperes from kilowatts without voltage and power factor. Optional pandapower is a later, separately validated adapter only.

### 3.4 Retained six-load regression fixture
Keep the earlier six-load example as a separate allocator fixture, not the live campus. Demand W: clinic 2,000; emergency 1,000; pump 3,000; communications 2,000; cold store 2,000; comfort 4,000. Tiers: critical, critical, important, important, important, flexible. The first three share a 6,000-W feeder; the last three an 8,000-W feeder.

At 7,000 W, exact tier-count allocation selects clinic/emergency/communications/cold store (mask 27, 7,000 W). Catalog-order greedy selects clinic/emergency/pump (mask 7, 6,000 W). Smaller-demand-first greedy ties exact. This is a constructed regression, not measured superiority or the seven-load campus result.

## 4. End-to-end architecture and source of truth

```text
  ┌───────────────── React / Vite / shadcn UI / React Flow / ECharts ──────────────────┐
  │ Network, telemetry, incidents, optimization rationale, action panel, replay, eval │
  └──────────┬──────────── REST controls / GET history ──────────────┬────────────────┘
             │                                                       ▲ WS /ws/live
             ▼                                                       │
  ┌─────────────────────────── FastAPI (single process) ─────────────────────────────┐
  │ Ingress queue → authoritative state engine → snapshot store → broadcaster       │
  │              │                              │                                    │
  │      Simulator/scenarios                Event writer (SQLite)                     │
  │              │                              ▲                                    │
  │       synthetic observations                 │                                    │
  │              ▼                              │                                    │
  │  anomaly + trust → hypotheses → diagnosis FSM → capacity/reachability optimizer  │
  │                                                     │                           │
  │                                       guarded action executor                    │
  │                                                     │                           │
  │                                       simulator applies states                   │
  │                                                     │                           │
  │                                  commands sent to hardware bridge               │
  └─────────────────────────────────────────────────────┼───────────────────────────┘
                                                        │ USB JSONL / pyserial
                                              ESP32 A gateway + OLED
                                                  /             \
                                              ESP-NOW          ESP-NOW
                                                /                 \
                                ESP32 B critical indicator     ESP32 C other indicator
                                  LEDs/LCD + buttons             LEDs/LCD + buttons
```

### 4.1 Authoritative state and concurrency
**One Python process owns writable grid state**. The frontend and firmware are *clients/indicators*, not competing grid-state authorities. Implement a single async orchestrator that serializes writes through an `asyncio.Queue` (or lock-protected pure transition function). Every event yields an immutable snapshot with `run_id`, `snapshot_seq`, `control_revision` and `tick`. Publication sequence advances on every publication; control revision changes only for control-relevant input/state changes. Derived pipeline returns a **proposed plan**; executor validates against fresh snapshot before committing. Avoid multiple concurrent simulation loops or one React slider independently calculating load state.

### 4.2 Precise execution order for each tick
1. Advance synthetic world (scenario step, tick, immutable *ground truth*; hidden from inference).
2. Generate independently noisy and potentially stale/missing **observations**. Preserve `origin=SIMULATED` and `sensor_status`.
3. Run signal quality/provenance checks, baseline/anomaly, per-hypothesis diagnosis; update diagnosis FSM.
4. Compute **estimated reachable loads** and available source capacity from trusted operating data. If trust insufficient, permit **observe-only** rather than invent grid status.
5. Run optimizer on observed/validated state; compare greedy candidate and compute objective/binding constraints.
6. Executor checks action preconditions, control policy, version, cooldown, and feeder reachability; applies simulated states. Log rejected/stale proposals too.
7. Persist event/action/snapshot; enqueue display-only command to serial bridge; track actual hardware ACK separately.
8. Broadcast complete current snapshots; bound/downsample chart buffers. Persist event history separately; no delta reconstruction is needed.

**Critical separation:** diagnosis and allocation do not receive `scenario_id` or `truth_fault_edge` from scenario player. Hidden truth is available to simulator/evaluator and labeled delivery/LED projection, never to diagnosis/allocation. A truth-side delivery guard may reject an impossible modeled action but cannot provide the hidden fault answer to the controller.

### 4.3 Refresh rates (initial design)
- Simulator tick **200 ms (5 Hz)**; scenario timestamps in simulation time; 1× playback first, 4× optional. This is enough for the demo; don't claim protection-grade millisecond detection.
- UI state snapshot **5 Hz**; charts optionally buffered to 1–5 Hz. Scenario buttons create immediate queued events.
- ESP32 heartbeat **1 Hz host time**, stale after **3 s host time**; simulation pause never pauses hardware health; action messages on change and response ACKs. For local link-health measurements, optionally transmit heartbeat faster (2–5 Hz) after basic reliability is proven.
- DB write on **state-changing events** plus optional downsampled observations (e.g. 1/s); keep event snapshots for replay.
- Change fast-protection claims in source BLACKOUT MESH (e.g. ≤250 ms) to **aspirational per-subsystem goals**, and do not present them as demonstrated outcomes in this slower, simulated architecture.

## 5. Final technology stack

| Concern | Standard choice | Why / constraints |
|---|---|---|
| Web app | React + TypeScript + Vite | Established Stack A; local build and offline deploy |
| Component system | Tailwind CSS v4 + **shadcn/ui** + Lucide | Fast dashboard, own custom components; install locally ahead of event |
| Topology | **@xyflow/react** (React Flow) | Custom bus/source/feeder/load nodes; manual layout stored in JSON |
| Charts | **Apache ECharts** via echarts-for-react | Multi-series telemetry and incidents; choose **one** chart library |
| Local state | Zustand | Selection, panel state, last WS snapshot; no duplicated simulation |
| REST cache | TanStack Query | Incident history, scenario definitions and saved evaluation |
| Typed REST | FastAPI OpenAPI → openapi-typescript/openapi-fetch | One contract from Pydantic; regenerate on changes |
| Backend | Python 3.11+ + FastAPI + Pydantic | Simulator, diagnosis, optimization in one process |
| Graph | NetworkX | Connectivity/topology/hypothesis traversal, not physical power flow |
| Numerical | NumPy | Deterministic synthetic sensor noise, statistics |
| Optimization | **OR-Tools CP-SAT** | Binary served/shed constraints, hierarchy and cost |
| Required lab activity model | scikit-learn Random Forest first candidate | CPU inference; causal features, grouped holdout and visible abstention; see ML plan |
| Fault model optional | scikit-learn Isolation Forest | Advisory novelty only, held-out comparison required |
| Persistence | SQLite + SQLModel | Local-file event/action persistence; WAL, batch writes |
| Streaming | Native WebSockets | Server-authoritative grid snapshot/events |
| Serial bridge | pyserial | Python ↔ ESP32 A via USB |
| Firmware | Arduino framework + **PlatformIO** | Quick ESP-NOW/LED/display work, version-pinned |
| Python dev | **uv, Ruff, pytest** | Lock dependencies, consistent formatting/tests |
| TS dev | pnpm, TypeScript strict, Vitest | Reproducible integration |
| E2E optional | Playwright | Demo smoke test only if time permits |

**Explicit exclusions:** Convex (extra backend), Drizzle (TypeScript ORM unnecessary with Python owner), Next.js server stack, Postgres/Redis/RabbitMQ, Kubernetes, cloud-only dependencies, autonomous LLM agents, mandatory OAuth, production-grade AI model. Do **not** spend time replacing Stack A during the event.

**Deployment:** `Vite build` and FastAPI static serving if prepared; otherwise two localhost ports with pretested cross-origin config. Bundle CSS/fonts/scripts/icons locally; no external CDN or hosted font needed. Pin versions with committed `pnpm-lock.yaml` and `uv.lock` and PlatformIO toolchain versions. Run the judge demo offline.

## 6. Repository layout, setup and working agreement

```text
prioritygrid/
├─ README.md                     # runbook + offline commands + truth-in-advertising
├─ docs/
│  ├─ UNIFIED_IMPLEMENTATION_PLAN.md
│  ├─ API_CONTRACT.md
│  ├─ HARDWARE_WIRING.md
│  ├─ PITCH.md
│  ├─ LICENSE_ATTRIBUTION.md
│  └─ RESULTS.md                  # generated actual numbers, source labelled
├─ contracts/
│  ├─ schema_examples/            # golden JSON snapshots and event envelopes
│  ├─ sample_topology.json
│  └─ serial_protocol.md
├─ backend/
│  ├─ pyproject.toml
│  ├─ uv.lock
│  ├─ app/
│  │  ├─ main.py                  # FastAPI routes and lifespan
│  │  ├─ api/{routes.py,websocket.py}
│  │  ├─ schemas/{grid.py,events.py,hardware.py,actions.py}
│  │  ├─ core/{orchestrator.py,state.py,clock.py,config.py}
│  │  ├─ simulation/{model.py,topology.py,telemetry.py,scenarios.py}
│  │  ├─ diagnosis/{baseline.py,features.py,hypotheses.py,fsm.py,trust.py,explain.py}
│  │  ├─ control/{optimizer.py,enumeration.py,guardrails.py,executor.py,recovery.py}
│  │  ├─ hardware/{serial_gateway.py,protocol.py,adapter.py}
│  │  └─ storage/{models.py,repository.py}
│  ├─ scenarios/*.yaml
│  ├─ scripts/{run_suite.py,generate_demo_results.py}
│  └─ tests/{test_topology.py,test_diagnosis.py,test_optimizer.py,test_fsm.py,test_api.py,test_replay.py}
├─ frontend/
│  ├─ package.json
│  ├─ pnpm-lock.yaml
│  ├─ src/{app,components,features,hooks,lib,stores,types}/
│  └─ public/demo-assets/
├─ firmware/
│  ├─ platformio.ini
│  ├─ include/{config.h,protocol.h,secrets.example.h}
│  ├─ src/{main.cpp,serial_bridge.cpp,espnow_link.cpp,indicators.cpp,buttons.cpp}
│  └─ test/
└─ tools/{smoke_test.py,port_check.py,export_demo.py}
```

### Integration rules
- One repository; keep the main branch demoable when version control is initialized. Branch by task, not assigned person.
- By hour 2, freeze topology/snapshot fixtures, controller interfaces, device masks and a mock transport message.
- Schema changes update Pydantic, generated TypeScript types, fixtures and serial translation together.
- Every component records its actual startup/check command, result and fallback before integration.
- Keep small coherent commits when this folder is a Git repository. No fabricated results or rewritten history.

### Reproducible startup commands (run inside relevant directories)
```bash
# backend: after creating Python project and committing uv.lock
cd backend && uv sync && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# frontend: initialize once with Vite React TS; install listed deps + shadcn
cd frontend && pnpm install && pnpm dev --host 127.0.0.1

# firmware (when ESP32 board type is confirmed)
cd firmware && pio run -e gateway && pio run -e critical && pio run -e general

# tests / report
cd backend && uv run pytest -q && uv run python scripts/run_suite.py --set heldout --report ../docs/RESULTS.md
```
These commands are **target commands**; create the directories, `pyproject.toml`, `package.json` and `platformio.ini` first. Do not assume firmware env names exist before firmware configuration defines them.

## 7. Contracts: data, events and device protocol

### 7.1 Contract and mutation identity
- Envelope: `schema_version`, `run_id`, `snapshot_seq`, `control_revision`, `tick`, `sim_time_ms`, `simulation=true` and UTC display timestamp.
- Use integer `_w` quantities in controller/API contracts; convert to `_kw` for display. Synthetic voltage is `_pu`. Reject bool/string/non-finite values, unknown IDs and invalid ranges.
- Provenance remains `SIMULATED`, `EMULATED_INPUT`, `DERIVED_SIMULATION`, `PHYSICAL_INDICATOR`, `RADIO_TELEMETRY`, `REPLAY`.
- Mutations include `run_id`, `expected_control_revision`, `request_id`. Reject stale run/revision with HTTP 409; duplicates return the prior outcome without another action. Heartbeat publications do not invalidate valid control requests.
- HTTP acceptance, proposed decision, applied simulation and pending/ACKed/timed-out LED display are distinct states.
- Synthetic freshness uses simulation time. Real heartbeat/ACK latency uses host monotonic receipt time. MCU uptime is diagnostic; do not subtract unsynchronized clocks.

### 7.2 Full snapshot fields
Freeze one complete validated JSON fixture. Include observations (capacity W or null, feeder/bus evidence, provenance, quality and age), modeled delivery (requested/served W, per-load command/delivery), diagnosis (hypotheses, supporting/contradicting/missing evidence, trust/baseline/FSM state), decision (mask, exact objective, reserve, active solver/fallback, shortfall, alternatives), hardware (physical/virtual, session/boot/command/mask/ACK age/timeouts) and bounded recent events.

Keep `TruthState`, `Observation`, `Diagnosis` and `ProposedAction` distinct. The UI snapshot contains evaluator/projection fields that must never become controller input. Unknown is null/unknown, not zero. Connected/commanded is not proof of delivered power; every displayed power total reconciles with the load states.

### 7.3 Full-snapshot streaming and reconnect
`WS /ws/live` sends the same complete schema as `GET /api/state` on connection and at up to 5 Hz. Drop older sequences within a run; replace state explicitly on a new run. No delta merge is required. Reconnect waits for a fresh snapshot before enabling controls. Disconnect retains a visibly stale view and disables mutations. Bound buffers and reject unknown schema versions.

Reset creates a new run/session and invalidates old pending requests/actions. Save events separately for history. All inputs, including physical buttons, enter the same validated command owner.

### 7.4 Serial and application-ACK lifecycle
USB uses bounded UTF-8 newline-delimited JSON at 115200 baud, with a 512-byte line cap and recovery from partial/malformed/oversized input. Translate human-readable host IDs to the numeric radio identity.

1. Queue the latest committed simulated display mask; one in-flight command per peer, coalescing unsent obsolete masks.
2. Send current session, target device boot ID, command sequence and mask. Initial send plus two retries at 200-ms intervals; timeout at 600 ms host time. Retries reuse identity.
3. Receiver validates and applies GPIO outside the radio callback, then ACKs the matching sequence and actual mask.
4. Confirm only a matching node/session/boot/sequence/mask. Wrong-mask ACK is an error; MAC send success is only transport status.
5. Duplicate SET returns cached ACK without reapplying; old commands/sessions cannot overwrite newer state. A heartbeat is not a retroactive command ACK; fresh state reports have separate provenance.
6. HELLO/reconnect clears obsolete pending commands, synchronizes and sends the current mask. A reboot reports fresh boot ID and actual uninitialized state before resync.

Increment a persisted unsigned 32-bit session counter on run/reset/backend restart; require reinitialization rather than wrapping. SYNC binds the session to the receiver boot ID and cannot downgrade an active session. SET cannot establish a different session. Authenticated peer keys are the trust boundary; counters prevent stale application within it.

### 7.5 Radio v1: explicit 26-byte wire contract
Retain magic/version/CRC and add session, boot and application-ACK identity. Serialize little-endian fields explicitly; never rely on native struct padding.

| Bytes | Fields |
|---:|---|
| 1 each | magic 0xA5, version, message kind, node ID |
| 4 each | session, message sequence, receiver boot ID, ACK sequence |
| 2 | local load mask |
| 1 each | status, flags |
| 2 | CRC16/CCITT-FALSE over the preceding 24 bytes |

Total = 4 + 16 + 2 + 2 + 2 = **26 bytes**. Kinds: HELLO, SYNC, SET_LOADS, ACK, HEARTBEAT, BUTTON. Only three B mask bits and four C mask bits are valid (§3). Round-trip the same fields in serial/radio fixtures.

Validate sender allowlist, length, magic/version, CRC and ranges. CRC is not authentication. Use encrypted unicast peers with locally provisioned PMK/LMK; keep secrets out of source. Compile with examples/headers from the pinned core, not an unrelated online callback signature. Bounded queues keep callbacks short. Do not claim industrial security certification.

### 7.6 Hardware command → simulator event linkage
An outbound `SET_LOADS` follows a committed simulated action. On ACK, update **hardware displayed status** but **do not change simulator truth** (already applied). On hardware timeout, mark `INDICATOR_NOT_CONFIRMED`; no recursive simulated shedding because a display board is offline. Physical button events ask FastAPI to queue `INJECT_*` simulation events; source must be `EMULATED_INPUT` and the resulting electrical readings remain `SIMULATED`.

## 8. Simulator and fault injection

### 8.1 Graph and world state
Use NetworkX `DiGraph` or typed tree structures: `Source`, `Bus`, `Edge(id, from, to, max_kw, closed, faulted)`, `Load(id, bus, demand_kw, tier, enabled, min_off_ms, manual_lock)`. Validate on load: exactly one source; DAG/tree for MVP; no negative demand; each load bus exists; no duplicate IDs; constraints are positive. Snapshot world state before each tick for reproducible replay.

### 8.2 Electrical simplification
- **Availability:** energizable if connected by closed, healthy edge path to energized source and local source/feeder constraints can support that assignment.
- **Demand:** `demand_kw` known as a scenario load property; telemetry reports requested/served demand with controlled noise. `available_capacity_kw` from trusted source reporting.
- **Line loading:** for radial lines, calculated `flow_kw(edge) = Σ served demand_kw` in the downstream subtree; require `flow_kw(edge) ≤ max_kw(edge)` for operating plans.
- **Voltage proxy:** e.g. `v_pu = clip(1.0 − 0.02 × (path_loading_fraction) + scenario_depression + Gaussian_noise, 0, 1.10)`; for disconnected/islanded bus without source, `v_pu≈0` with noise floor. This equation is **heuristic telemetry generation**, not Ohm/Kirchhoff power flow. Document generation/noise before held-out evaluation; do not tune the generator to flatter the controller.
- **Sensor faults:** introduce offset, stale stream, freeze or random spikes on one report; never modify world truth when simulating a sensor fault.
- **Communications fault:** drop observation packets on simulated virtual nodes; for actual ESP32 peer failure, loss belongs to physical indicator network and need not alter synthetic grid electrically.
- **Ground truth:** `scenario_truth` stored by evaluation runner in a separate module and withheld from engine. Runtime operator may still view injection instructions in demo panel; dashboard must distinguish *what was injected* from *what the engine inferred*.

### 8.3 Scenario catalog, predefined before testing
| ID | Event | Observable pattern (illustrative) | Correct expected effect |
|---|---|---|---|
| S00 | NORMAL_STEADY | stable source/demand/v_pu | all reachable loads served, no alarm |
| S01 | NORMAL_VARIATION | moderate demand fluctuations | baseline adapts, no confirmed fault |
| S02 | CAPACITY_DERATE | source cap 100→52 kW | capacity-shortage incident; optimize compliant shedding |
| S03 | F2_FEEDER_OPEN | bus C drops to no-source state | L_LAB + L_CLASS unreachable, no false restoration |
| S04 | F1_FEEDER_OPEN | bus B disconnected | L_CLINIC + L_HOSTEL unreachable; show critical coverage risk |
| S05 | SENSOR_BIAS | one `v_pu` shifted independent of peers | degraded sensor trust / uncertain diagnosis |
| S06 | SENSOR_STUCK | identical repeated sensor samples while peers vary | sensor-health alert, no false electrical certainty |
| S07 | VIRTUAL_REPORT_LOSS | simulated downstream stream disappears | stale/communication hypothesis, no electrical claim absent evidence |
| S08 | PHYSICAL_ESP_NOW_LOSS | remote ESP32 off/radio muted | physical device-link failure, simulator electric state unchanged |
| S09 | TRANSIENT_DIP | short voltage-proxy dip | info event; no hard shutdown if below persistence threshold |
| S10 | INTERMITTENT | repeated open/closed telemetry disturbance | repeated-event warning and anti-flap |
| S11 | DUAL_EVENT | capacity shortage + missing sensor | conservative fallback / trust gate |
| S12 | RESTORE_CAPACITY | cap 52→100 and stabilized | ordered re-service after cooldown |
| S13 | FEEDER_REPAIRED | F2 closes explicitly in simulator | newly reachable loads eligible for restoration |
| S14 | RECOVERY_INTERRUPTED | second derate during restoration | cancel/recompute stale plan, no oscillation |
| S15 | CRITICAL_INFEASIBLE | cap < aggregate T0 demand | report inability to preserve all essential loads; never invent capacity |

Define YAML/JSON scripted events (`seed`, `duration_ms`, `steps`, `expected`). Maintain **at least one normal control run** for every fault family. Include event injection time, pre-state and expected truth. Support reset, pause and step first; faster playback and deterministic re-execution are optional. History remains available.

## 9. Fault detection, diagnosis, trust and explainability

### 9.1 Feature and baseline layers
1. Validate samples (`source`, finite values, timestamp order, units, monotonic sequence). Out-of-range/no-data becomes a **quality event**, not proof of an electrical fault.
2. Smoothing: last-3-sample median for spike suppression; keep raw trace for transient detection.
3. Baselines: initial normal window median and robust spread `MAD × 1.4826` with nonzero floor. Keep a fixed **golden profile** and an adaptive normal baseline.
4. Gated EWMA adaptation: record alpha (initial 0.05 at 5 Hz); update only in `NORMAL` with fresh trusted samples and residual within the normal envelope; **freeze on SUSPECTED, CONFIRMED, CRITICAL, SENSOR_UNTRUSTED**. This prevents learning a persistent shortage as “normal”.
5. Compute independent features: `demand/capacity`, `v_pu` residual vs expected synthetic load behavior, neighbor agreement, downstream connectivity consistency, stale/heartbeat age, variance/stuck, rate-of-change and persistence.
Baseline warm-up is explicit. Initialize golden limits from documented configuration/development-normal data; a faulty startup must not redefine normal. Hard capacity guards remain active during warm-up. Constant samples alone do not prove a stuck sensor; require independently expected variation or timestamp/counter inconsistency.

6. Simple change-point/CUSUM advisory for slow drift if time remains; optional Isolation Forest is **not** needed for P0 and must not directly actuate critical decisions.

### 9.2 Explicit hypotheses; no blind single score
`NORMAL`, `SOURCE_CAPACITY_SHORTAGE`, `FEEDER_OPEN(edge_id)`, `VOLTAGE_PROXY_ANOMALY`, `SENSOR_FAILURE(node_id)`, `VIRTUAL_NODE_COMM_LOSS(node_id)`, `ESP_NOW_DEVICE_LOSS(node_id)`, `TRANSIENT`, `INTERMITTENT`, `UNKNOWN_OR_COMBINED`.

For each feeder hypothesis, forward-simulate which downstream buses **should** have low voltage/zero served power; compare to *observed* sensor subset. Use a **compatibility score** (bounded, transparent weights) that rewards matching observations and penalizes contradictions. Report first and second candidates plus a margin. The hypothesis with lowest observed disagreement is not necessarily uniquely identifiable. Example: if all downstream sensors are missing, feeder F2 vs F5 may be observationally identical → **ABSTAIN** and request an independent simulated measurement if available.

**Power/control decisions and diagnosis uncertainty:** A confirmed capacity shortage from trusted source capacity may still permit safe, constrained simulated shedding; an ambiguous feeder fault may require **hold/observe** instead of restoring downstream. Do not shut down essential simulated loads purely because one radio/display node failed.

### 9.3 Recommended two-level state machines
**Fault classifier FSM:** `NORMAL → SUSPECTED → CONFIRMED → CRITICAL`; support `UNVERIFIED`, `RECOVERING`, acknowledgment and latched events per incident. Electrical class, observation quality and physical link health stay independent; simultaneous defects are not one exclusive class. Example initial values: 3 consecutive anomalous ticks to suspect (0.6 s at 5 Hz), ≥5 additional ticks to confirm (1.0 s), critical severity after persistent evidence; hard capacity/connectivity guards shed immediately without waiting for diagnostic confirmation; clear only after ≥10 stable ticks (2 s). Tune with holdout tests; these are **prototype defaults**, not safety-relay settings.

**Controller FSM:** `MONITORING → DIAGNOSING → SHEDDING → STABILIZING → RESTORING → MONITORING`, plus `DEGRADED`, `MANUAL_PAUSE`, `INFEASIBLE`. Controller state is separate from fault class; comm loss shouldn't force simulated shed.

**Hysteresis:** example source `capacity_drops` can trigger shedding promptly; restoration requires the configured reserve (default **0 W**), fresh stable evidence for **5 s**, per-load min-off **3 s**, and at most one new ON per **1 s**. Capacity/evidence change resets the wait. Solver, validator and all baselines use the same reserve. These are configurable, unvalidated first-pass choices. Do not implement reconnection every UI frame.

### 9.4 Unknown evidence behavior
Missing electrical evidence is not an outage. Unknown branch: forbid new ON transitions and count retained ON demand at its full configured value. Fresh lower source capacity can still trigger shedding. Unknown source capacity: hold/observe, inhibit restoration, show `capacity_unknown` and do not label supply guaranteed feasible. Shed/replan or expose an unresolved condition if retained assumptions violate known constraints.

A fresh open contact is `FEEDER_OPEN_OBSERVED`, not inferred localization. Without contact evidence, keep all compatible feeder/sensor hypotheses and abstain when indistinguishable. Exclude direct-status cases from inferred-location accuracy.

### 9.5 Explainability and provenance in the UI
For every incident: raw/normalized observations, time, sensor/source trust, top hypotheses, **which evidence supports each**, contradictions, missing evidence, score described as *inference score (heuristic, not P(fault))*; what control action was taken, who/what triggered it, constraints, alternative plans rejected, and whether any load was unreachable.

Example rationale: “**52 kW available; 84 kW requested.** Clinic and emergency lights are reachable and T0 priority. Controller served feasible T0/T1 loads and selected additional loads within 52-kW system/branch limits. Lab and classroom may be excluded because of constraints. Action was **simulated**; ESP32 indicators reported ACK.” (Specific loads depend on solver output.)

## 10. Mathematical optimization, controlled execution and recovery

### 10.1 Exact policy, solver status and application guard
Binary served requests `x_i` use integer demand W. Total demand must be ≤ max(0, source capacity − reserve); default reserve=0 W. Enforce every feeder subtree limit, known reachability, lockouts and §9.4 unknown-state constraints.

Maximize lexicographically: T0 service count; T0 importance (clinic=2, emergency=1); T1 count; T2 count; T3 count; negative switching count; negative global mask. Earlier objectives dominate all later ones. Count is the benefit; watts are a constraint. The illustrative policy omits clinical validation, interruption duration, partial service and startup surge.

Optimize CP-SAT stages sequentially, fixing proven optimal stages only. Start with a **100-ms total budget**, one worker and fixed seed. FEASIBLE/UNKNOWN is not proof of the full lexicographic optimum; use exact enumeration on timeout/tool failure and identify fallback. Invalid configuration/model is an error. Exact fallback is limited to ten tested loads.

Before application, independently validate capacity, branch constraints, reachability, freshness, cooldown and current control revision. Reject stale/infeasible plans. Modeled delivered power never exceeds available supply; requested demand is separate.

Default is best effort plus explicit unavailable critical IDs/reasons (`capacity`, `feeder`, `unknown_evidence`). Optional strict-critical policy reports `CRITICAL_INFEASIBLE` rather than silently relaxing requirements. At zero supply all loads are unavailable.

Primary 52,000-W case: clinic + emergency + server + hostel = **52,000 W**, mask **23**. Catalog-order priority greedy ties. At 55,000 W: clinic + emergency + server + lab = **54,000 W**, mask **15**, using the stated final tie-break. These are arithmetic expectations, not measured results.

### 10.2 Independent exact-enumeration oracle (for 7 loads)
With 7 binary loads, there are `2^7=128` candidate assignments. Test every combination: reject unreachable/branch/capacity violations, choose lexicographic objective winner. Use this as (a) a fallback, (b) validation that CP-SAT results are correct and (c) a judge-friendly explanation of optimality on small networks. Our project may grow later, where CP-SAT is more scalable.

### 10.3 Fair comparison
Compare fixed catalog-order priority greedy and smaller-demand-first greedy within tiers against exact/CP-SAT, with identical observations, demand, topology, reserve, branch limits and transition eligibility. Retain the six-load regression (§3.4). Publish ties and failures, not only favorable examples. Separate service-objective differences from arbitrary final mask tie-breaks. Report critical/important services, switching, shed demand and runtime; never import upstream benchmarks.

### 10.4 Autonomous simulated action policy
**Committed implementation choice for this blueprint:** default `AUTO_SIM` acts automatically only in sandbox. Add UI button `PAUSE_AUTOMATION` and mode `RECOMMEND_ONLY` (if time). Executor validates current snapshot/version, trusted feeder reachability, reserve, cooldown, and manual locks. Reject stale or unsafe plans with audit trail. Hardware LEDs mirror **applied simulated state**, not power authority.

### 10.5 Restoration
When source capacity returns: no instant “all on”. Wait stable 5 s with fresh evidence; compute a feasible plan; apply necessary OFF transitions first, then at most one new ON per 1 s with 3 s minimum OFF dwell and ensure feeder constraints remain satisfied. If capacity drops again, **cancel pending restoration**, mark `RECOVERY_INTERRUPTED` and reoptimize. Clear a latched event only when resolved and acknowledged if configured; acknowledgment does not repair its cause. Backend restart creates a new paused run/session and reconciles devices instead of resuming old pending commands.

### 10.6 Counterfactual decision log
Store best solution plus up to two alternatives (greedy baseline and one manually forced/illustrative candidate), with `why rejected`: insufficient capacity, violates branch, unreachable due to open feeder, lower-priority objective, or cooldown. This differentiates the product without adding an unrelated chatbot.

## 11. Embedded firmware and physical demo

### 11.1 Three ESP32s if available; two-board fallback
| Board | Role | Hardware | Minimum behavior |
|---|---|---|---|
| A | Gateway / serial ↔ ESP-NOW | OLED, one status LED, optional button | USB JSONL ↔ packed radio packets; peer health/ACK status to PC; no internet AP |
| B | Critical-zone indicators | 3 LEDs, optional LCD #1, button | `SET_LOADS` displays clinic/emergency/server map; local link-loss indicator |
| C | General-zone indicators | 3–5 LEDs, optional LCD #2, button | `SET_LOADS` displays lab/hostel/classroom/amenities map |

**If only two ESP32s boot reliably:** A gateway + B multi-load indicator. Display the other load statuses virtually. This is a complete, acceptable demonstration; do not block software on acquiring a third board.

**Local resilience rule:** if laptop USB/serial drops, hold last displayed indicator state and show `CONTROLLER OFFLINE/STALE` warning; boards may continue radio heartbeat and run a local button-driven **mock safe indicator behavior**, but cannot autonomously reoptimize the simulated electrical network. If ESP-NOW drops, remote node shows communications warning without pretending the electrical supply failed.

### 11.2 Pin guidance — *confirm ESP32 variant first*
For a **classic ESP32 DevKit V1/WROOM32**, initial plan:
- LEDs: GPIO **25, 26, 27** for 3 indicators, each through **220Ω or 330Ω** resistor to LED then ground (verify LED polarity). For 4th/5th use 18/19 if available and free.
- Buttons: GPIO **32/33** with `INPUT_PULLUP`; press to ground. Debounce 30 ms.
- OLED I²C (3.3V-compatible module): SDA **21**, SCL **22**, power at rated voltage; confirm pinout.
- Optional **10k B10K potentiometers**: ADC1 GPIO **34 or 35** on gateway, end pins 3.3V and GND, wiper to ADC; **never 5V into ESP32 GPIO**. Use as physical *simulation controllers* (supply cap, demand), not grid sensors. UI provenance `EMULATED_INPUT`.
- LCD: if 5V I²C backpack, verify safe 3.3V I²C pull-ups or use level shifter. If parallel 1602, pin/wiring workload may not be worth it. **Displays optional**, LED state confirmation is priority.
- No shared-ground wiring required **between independently powered ESP32s over radio**. Each board's LED grounds return to its own board; USB connects the gateway to laptop.

GPIO maps may be incompatible with ESP32-C3/S3 variants; inspect board markings or `esptool` output before flashing. Confirm power budget and LED current; no GPIO should ever touch mains. Don't connect the kit's relay to real AC loads.

### 11.3 Firmware states
`BOOT → SELF_TEST → RADIO_JOINING → ONLINE → LINK_DEGRADED → OFFLINE_LOCAL_INDICATOR`. Boot status-LED test; load indicators remain OFF/uninitialized until synchronization; missing peers show amber; command LED maps idempotently; send application ACK **after** state update. On stale commands, drop and send `REJECTED_STALE`; duplicates resend cached ACK without reapplying physical state. Node reboot announces a fresh boot ID; explicit SYNC establishes the host session before commands are accepted.

### 11.4 Integration milestones
1. Flash 2 boards; print MACs, choose matching ESP-NOW Wi-Fi channel, peer one-way send.
2. Bidirectional ACK and heartbeat; serial gateway forwards parsed commands.
3. Single dashboard toggle reaches B LED and hardware ACK returns into UI.
4. Optimizer `AUTO_SIM` emits live state changes that cause multiple LED states to change correctly.
5. Disconnect B radio/power: link banner shows missing, no electrical alarm unless separate synthetic electrical observation warrants it.
6. **Optional** add C, OLED and LCD only after 1–5 pass.

## 12. Backend API, WebSocket and persistence

### 12.1 REST endpoints — contract targets
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
Replay reads saved state/observation stream and **restores pipeline's pre-incident baseline/FSM state**. Re-run pure functions with same configuration and seed; compare generated diagnosis/action trace to stored original. A “play historical snapshots” UI is acceptable at MVP even if true deterministic re-execution is delayed; label the mode honestly (`HISTORY_PLAYBACK` versus `DETERMINISTIC_REEXECUTION`). Replay must not send physical LED commands by default. Persist raw observations, golden/adaptive baseline, filter windows, per-incident FSM, prior masks, cooldown/restoration timers, config/policy version and event order; seed alone is insufficient for stateful re-execution. Compare logical outcomes, not radio timing.

## 13. Frontend control-room specification

### 13.1 Single-screen layout
- **Top bar:** Blackout Mesh / mode `LIVE_SIMULATION` / incident severity / synthetic-vs-radio provenance / connection indicators.
- **KPI row:** available source kW, requested kW, served kW, shed kW, essential loads served / total requested (including disconnected loads), gateway peers online.
- **Center left:** interactive single-line graph (source, feeder edges, buses, colored loads), legend distinguishing *simulated electric status* and *physical peer connectivity*.
- **Center right:** current incident, ranked hypotheses, missing evidence, uncertainty, chosen action, violated/infeasible constraints.
- **Bottom:** event timeline + telemetry charts + hardware ACK panel; switches for reset/scenario/injection/pause/auto/manual.
- **Tabs:** `Control Room`, `Incidents & Replay`, `FaultLab Evaluation`, `Hardware Health`, `Architecture/About`.

### 13.2 UI behaviors
- Use shadcn `Card`, `Badge`, `Alert`, `Tabs`, `Table`, `Dialog`, `Sheet`, `Tooltip`, `Sonner`.
- React Flow custom node types `sourceNode`, `busNode`, `loadNode`; edge stroke red broken/faulted, amber degraded, grey open, green served; **do not show a light glowing across an unreachable feeder**.
- ECharts: capacity demand/served timeline, per-bus `v_pu` with legend **SIMULATED**, fault score, action stage chart. Plot real ESP-NOW RTT and ACK success separately.
- Disabled/stale values become muted and timestamped; WebSocket reconnect first reloads `/api/state` to prevent out-of-order rendering.
- Hardware visual never changes to “ACKED” before actual firmware ACK; simulation action may be “APPLIED_SIMULATION” first.
- Evidence chips on every value: `SIMULATED`, `DERIVED_SIMULATION`, `EMULATED_INPUT`, `RADIO_TELEMETRY`, `PHYSICAL_INDICATOR`; never make *radio online* synonymous with *electric healthy*.
- Incident UX: “What happened?”, “Why?”, “What did the controller do?”, “What couldn’t it know?”, “What if greedy control was used?”

### 13.3 Engineering speed
Start from a Vite/shadcn admin shell; **custom React Flow graph is the product center**, not decorative graphics. Include local empty/error/loading states. Use mock typed JSON snapshot provided by hour 1; switch transport to backend by hour 4. Build with `pnpm build` offline ahead of final demo. Require keyboard operation, visible focus, text/icons alongside color, readable contrast, local assets and reduced motion. Include a service-table alternative, last-update ages and loading/error/empty states. Keep the decision panel legible at 1366×768; secondary history/charts belong in supporting tabs.

## 14. Component dependencies and integration gates
No human staffing allocation is required. Work is organized by contracts:

| Component | Input → output | Done means |
|---|---|---|
| Simulator/observations | fixtures/events → hidden truth + permitted reports | deterministic; no label leakage |
| Diagnosis/trust | observations + baseline/FSM → evidence/unknown/candidates | sensor, feeder, shortage and comm cases distinct |
| Allocator/executor | observed constraints/policy → validated modeled action | oracle agreement; stale/infeasible plans rejected |
| API/storage | serialized typed events → snapshots/history/checkpoints | one authority; validation; no silent log loss |
| Frontend | schema/snapshots → decision console | stale/reset/error states visible; accessible controls |
| Firmware/bridge | session/boot-bound mask → applied ACK/heartbeat/button | loss, retry, duplicates and reboot handled |
| Evaluation/demo | frozen inputs/traces → results/manifest/rehearsal | claims traceable; synthetic and physical separated |

Order: freeze contracts/topology/masks → check observations and exact allocation → render fixture and exchange real packets → connect full loop → add fault/recovery behavior → evaluate → rehearse.

## 15. Role-free 24-hour execution

| Hours | Deliverable | Exit gate / cutoff |
|---|---|---|
| 0–1 | Inventory/toolchain, seven-load fixture, contracts/masks | Omit incompatible displays |
| 1–3 | Exact allocator, S00/S02 API, fixture UI, peer packet/ACK | Runnable components; table/SVG fallback if needed |
| 3–6 | Scenario → observation → allocation → simulation → UI → serial → radio → LED → ACK | Full loop; stop independent feature work if late |
| 6–9 | Feeder/observation/sensor failures, baselines/FSM, CP-SAT checks | Correct fault-domain distinction |
| 9–12 | Recovery, duplicates/stale messages, restart, history | Repeatable core; cut optional devices/re-execution |
| 12–16 | Held-out suite, fair baselines, real radio tests, usability | Fix correctness and preserve evidence |
| 16 | **Feature freeze** | No new major capability/dependency |
| 16–20 | Offline start, fault/reboot drills, full rehearsals | Remove unreliable optional scenes |
| 20–24 | Results/runbook/attribution/wiring photo/video/pitch | Three clean repetitions; no version upgrades |

Third board, knobs/displays, richer charts, recommend-only mode, active probing and true replay re-execution follow core gates. Software-only fallback remains useful but does not satisfy the real peer-radio gate.

## 16. Test plan, metrics and pass criteria

### 16.1 Automated invariant tests — must all pass
| ID | Assertion |
|---|---|
| T01 | Every served load is source-reachable through closed/healthy feeder path |
| T02 | `sum(served demand) ≤ available source capacity − configured reserve` |
| T03 | Every feeder downstream demand ≤ feeder's capacity if active |
| T04 | `served_kw`, `shed_kw`, `requested_kw` reconcile numerically |
| T05 | Solver matches exact enumeration **lexicographic** optimum on seven-load scenarios |
| T06 | Normal operation/demand variation does not generate repeated confirmed false incidents |
| T07 | Synthetic measurement failure reduces trust or abstains; not automatically an electrical fault |
| T08 | Actual ESP32 link loss does not alter simulated source/feeder electrical truth |
| T09 | Feeder F2 open blocks Lab/Class regardless of spare source capacity |
| T10 | Restoration only reconnects after stability/cooldown; interruption cancels stale plan |
| T11 | No reoptimization action applied if snapshot version changed before commit |
| T12 | Replay/history retains provenance and does not actuate physical LED hardware by default |
| T13 | Duplicate serial/ESP-NOW command only applies once; ACK for exact command seq |
| T14 | Disconnect gateway → UI shows hardware stale, main simulator remains demonstrable |

### 16.2 Experiment suite (held out)
- **Training/tuning seeds**: 1–20. **Held-out evaluation**: 101–120 for each scenario. Don't tune thresholds using held-out labels; record all seeds/config/commit SHA.
- Cases: S00–S15, multiple noise levels, lost virtual observations, at least one multi-event. **Scenario coverage ≠ field validity**.
- Compare: (a) raw threshold-only diagnosis, (b) trust+topology diagnosis, (c) greedy shedding, (d) CP-SAT optimum or exact enumeration.
- Report *event-level* precision, recall, F1, confusion matrix; feeder-edge localization success (only identifiable cases, count ambiguous separately), false critical count on normal runs, detection delay (from injected sim timestamp), abstention rate and correctness among non-abstained, feasible allocation rate, served critical kW, weighted service utility, switching count, optimizer solve time, hardware ACK success and latency.
- Keep **SIM performance** and **physical radio transport measurements** separate; this build has **no physical grid-fault accuracy** result.

### 16.3 Targets vs evidence — provisional, not achievements
| Target | Acceptance condition | Measured result |
|---|---|---|
| Core correctness | 100% invariants T01–T05 on generated scenarios | **TO BE FILLED BY RUNS** |
| Normal stability | 0 confirmed incidents in ten-minute S00/S01 held-out suite | **TO BE FILLED** |
| Classification | Report macro-F1 with confusion matrix (no fixed performance promise) | **TO BE FILLED** |
| Latency | Monitor end-to-end sim event → UI; record p50/p95 and units | **TO BE FILLED** |
| Power allocation | CP-SAT score ≥ greedy and matches exact oracle (for same model) | **TO BE FILLED** |
| Radio | 20 commands acknowledged, loss/latency logged; link-out recognized | **TO BE FILLED** |
| Offline | Run full dashboard, algorithms and radio with internet disconnected | **TO BE FILLED** |
| Demo | 3 clean consecutive end-to-end rehearsals | **TO BE FILLED** |

### 16.4 Testable failure conditions
- Invalid JSON/partial serial frames; CRC/version mismatch; duplicate/reordered radio packets; node reboot resets sequence with boot ID; USB disconnect and reconnect.
- Python backend killed/restarted; SQLite remains consistent; React WebSocket reconnects and resynchronizes.
- Sim input negative or nonsensical `capacity_kw`, stale WS snapshots, emergency source insufficient, F2 open, two simultaneous defects.
- “Impossible to distinguish” case must say **UNVERIFIED** instead of inventing a feeder ID.

## 17. Demo / judge pitch

### 17.1 Three-minute demo sequence
| Time | Demo action | Judge-facing proof |
|---|---|---|
| 0:00–0:25 | Show healthy campus grid and 84-kW demand / 100-kW capacity | product context; provenance is visibly **SIMULATED** |
| 0:25–0:55 | Scenario S02: reduce supply to 52 kW | optimizer applies constrained, priority-respecting shedding; LED zones change; actual ACK recorded |
| 0:55–1:20 | Expand action rationale | binding capacity/feeder rules + greedy comparison; not a hardcoded on/off rule |
| 1:20–1:50 | Scenario S03: open F2 | Lab and Classroom unreachable; no fictional restoration via spare power |
| 1:50–2:15 | Disconnect/disable ESP-NOW peer | hardware comm degraded, **simulated electrical state stays normal** if separately reset; prove failure attribution |
| 2:15–2:40 | Recovery and event replay | stability window, phased re-energization after capacity/feeder reset; evidence timeline |
| 2:40–3:00 | Evaluation dashboard and limits | measured scenario F1/accuracy, power constraints and radio ACK; honest test splits |

### 17.2 Pitch, concise
“**Blackout Mesh** is a low-cost *prototype* for fault-aware power-management decisions. We model a campus network, diagnose disturbances from imperfect simulated telemetry, and optimize which reachable loads receive limited power. Instead of reporting only an outage, the system explains its decisions, reacts in the simulated environment and demonstrates real device-to-device status communication using ESP32s. We measure its performance across repeatable scenarios and clearly distinguish synthetic electrical data from physical radio behavior.”

### 17.3 Questions to preempt
- **“Where are the real grid measurements?”** None: this is a software electrical-network model with real wireless indicator hardware. ADC sensing is a future adapter.
- **“Why call it AI?”** The current required scope adds a trained lab-activity classifier to graph/rule inference and constrained optimization. Claim ML only after the artifact and held-out results exist.
- **“What is ‘self-healing’?”** Staged simulated load reconnection when supply/feeders become available; not physical feeder repair.
- **“How is this different from existing SCADA/FLISR?”** It is an inexpensive educational/proof-of-concept integration with uncertainty gating, explainable constrained allocation and repeatable offline test scenarios; **no world-first claim**.
- **“Is your confidence 92%?”** No: rank/heuristic score, not a calibrated probability.
- **“Does it work with laptop unplugged?”** The ESP32s retain/indicate last state and local communication; full diagnosis/optimization does not.

## 18. Risk register, contingency and feature priority

| Risk | Likelihood / consequence | Mitigation / cutoff |
|---|---|---|
| Hardcoded simulated incidents leaked into inference | High / destroys technical validity | Ground truth in separate module; automated test asserts detector never imports it |
| Unrealistic feeder “restoration” | High / judge criticism | Connectivity constraints and explicit operator repair; T01/T09 tests |
| Realtime race/async inconsistency | Medium / incorrect actions | One authoritative queue, control_revision validation, immutable transitions |
| Data contracts mismatch | High / integration lost | Freeze Pydantic + fixtures by hour 2; generated TypeScript client |
| ESP-NOW or wiring broken | Medium / demo fails | Direct 2-board happy path by hour 4; simulation-only fallback; prerecorded video |
| OR-Tools install or solver issue | Medium / core weakened | Exact enumeration of 128 subsets tested early; feature flag fallback |
| Unnecessary deep ML | High / delays completion | Small trained lab classifier + rules/graph/OR is P0; deep vision models deferred; Isolation Forest advisory only if holdout improves |
| UI CDN/offline failure | Medium / dead demo | Vendor/bundle all front-end dependencies and run offline rehearsal |
| 5V LCD/I²C damage | Medium / hardware risk | Confirm device voltage/pullups and use level shifter where needed; skip LCD if uncertain |
| Unbounded DB/high-frequency writes | Medium / performance | Write only events and downsample; bounded queue, WAL |
| Fabricated metrics / ambiguous 'confidence' | High / credibility | Auto-generate results; mark heuristic; independent held-out seeds |
| Critical load physically cannot be kept alive | High / pitch mismatch | Explicit `CRITICAL_INFEASIBLE`; no guarantees during disconnected feeders |

### Priority labels
**P0** — required trained lab-activity classifier and priority integration (see ML plan); realistic-enough graph connectivity and capacity model; deterministic scenarios; integrity/provenance; source/feeder incident inference; trust gating; CP-SAT+enumeration allocation; React Flow control room; FastAPI WebSocket; ESP-NOW ↔ LED command ↔ app ACK; event log; basic suite.  
**P1** — richer evidence/abstain, phased restoration, greedy comparison and charts, replay/history, second remote ESP32/OLED.  
**P2** — Isolation Forest advisory with real heldout benefit, first-order thermal model, active measurement request, genuine deterministic re-execution of historical states, LCD polish.  
**P3 / DEFER** — pandapower/AC flow integration, LoRa, actual mains sensor/relay control, multi-hop mesh, secure field rollout, Convex, separate microservices, blockchain, solar-energy trading, LLM assistant, sensor hardware replica of original BLACKOUT MESH.

## 19. Component inventory, what to buy, safety

### Owned/available (from user's inventory)
- **2–3 ESP32 boards** (specific chip model to be verified); breadboards, jumper wires, resistors.
- **Two LCD screens**, **one OLED**.
- **Pro-Range UNO R3 Super Starter Kit**; retailer's corresponding kit lists UNO, 5V relay, LEDs, buttons, resistor assortment, buzzer and potentiometer, but **the user explicitly confirmed they do not have a potentiometer**. Do not assume one is present.

### Purchase/verification list
| Item | Buy? | Qty | Purpose |
|---|---|---:|---|
| **B10K 10-kΩ linear potentiometers** | Recommended, optional | 2 | tactile simulation inputs; not sensors |
| Working USB data cables | If absent | 2–3 | independently power and program boards |
| Red/yellow/green LEDs | If kit insufficient | ≥8 | load + link indicators |
| 220Ω/330Ω resistors | If kit insufficient | ≥10 | series LED current limiting |
| Push buttons | If kit insufficient | 3–4 | inject event, ACK, demo reset |
| 3.3↔5V I²C level converter | **Only if needed** | up to 2 | 5V backpack displays with 5V pull-ups |
| PCF8574 LCD I²C adaptor | Optional | up to 2 | reduce wires if LCD1602 without backpack |
| Mounting board, paper labels, tape, tie wraps | Recommended | 1 set | visual clarity, transit robustness |

**Total purchase can be zero** if buttons/LEDs/cables already exist and the physical-input potentiometers are skipped; potentiometer knobs improve demo but are nonessential. Confirm stock and cash before buying. Reserve budget for bad USB cables and last-minute parts, not extra sensors.

### Electrical safety checklist
- Power all boards via USB; never connect grid mains or high-current equipment. LEDs must have series resistors.
- ESP32 GPIO/ADC logic is 3.3V; do not drive ESP32 ADC/GPIO from 5V modules or UNO pins without level compatibility.
- Check I²C LCD backpack voltage/pull-ups. If uncertain, use just OLED + LEDs. Never assume all 1602 modules operate directly at 3.3V.
- Optional potentiometers connect only between board-local 3.3V/GND; wiper to suitable ADC1 pin. Put a simple software deadband and smoothing on hand-set inputs.
- Use **local ground per board** for LEDs. No need to wire the ESP32s together to use ESP-NOW.
- The relay bundled with UNO kit is **not required** and should not switch AC for this project.

## 20. Attribution requirements

Reuse research is maintained outside this repository. Before copying code, verify its license at a pinned revision and preserve legally required notices in the distributed implementation. No external source code has been incorporated here.

## 21. Decisions, honest scope, and claims register

| Statement | Allowed? | Safer wording |
|---|---|---|
| “We simulate a campus electricity network and act on its simulated states.” | YES | Exactly this. |
| “We use optimization, not only hardcoded rules.” | YES **after** CP-SAT/enumeration verified | “We solve constrained binary load assignment and compare with greedy decisions.” |
| “Our hardware switches real electrical loads.” | **NO** | “The ESP32s show applied simulated decisions with real wireless ACKs.” |
| “It measures real voltages, currents or temperature.” | **NO** | “Synthetic telemetry models electrical indicators; source is labelled.” |
| “Fault localization is accurate in real networks.” | **NO** | “Performance measured on held-out synthetic scenarios under our model assumptions.” |
| “Self-healing power grid” | **NO** | “Automated **simulated** allocation and staged restoration after a modeled fault is resolved.” |
| “Internet-independent peer communication.” | YES if tested | “The ESP32 peer link works without router/internet; backend depends on local laptop.” |
| “Mesh routing” | **NO** | “ESP-NOW star/peer link; routed mesh is future work.” |
| “90% probability the feeder failed.” | **NO** | “Heuristic compatibility score; competing hypotheses shown, with abstention.” |
| “Autonomous AI” | CONDITIONAL | “Trained lab-activity estimation, fixed priority policy and constrained optimization; synthetic-data limitations disclosed.” |
| “Unique invention” | **NO** | “Distinctive low-cost integration, focused on explainable action and reproducible evaluation.” |

### Submission alignment
The user confirmed there is no specific problem statement. Optimize for an open-ended hackathon: useful decisions, honest uncertainty, reliable execution and measured evidence. Historic problem IDs are references only, not build gates or claimed organizer requirements.

## 22. First steps and maintenance

### Launch checklist for first 60–90 minutes
- [ ] Confirm whether working ESP32 count is **2 or 3**, exact chip family, LEDs/buttons in kit, USB data cables and laptop OS.
- [ ] Inspect existing code and install/cache selected toolchains while internet is reliable; initialize version control when implementation starts if needed.
- [ ] Commit network fixture, load table, scenario IDs, Pydantic contracts + sample WebSocket snapshot.
- [ ] Freeze component interfaces and share this document version; no person-based role assignment required.
- [ ] Get **one** gateway→remote `SET_LOADS`→application-ACK exchange working.
- [ ] Run **one** backend `GET /api/state` + websocket fake state into React Flow.
- [ ] Run OR-Tools/enum for 52-kW case; assert 84 kW demand and exact capacity constraints.
- [ ] Deliver hour-2 mock integration checkpoint; complete web button → FastAPI → serial → ESP-NOW → LED → ACK → web status by hour 6.

### Final handover packet
`README.md` with exact offline run, `UNIFIED_IMPLEMENTATION_PLAN.md`, source and third-party acknowledgments, wiring photo, all installed dependencies/lockfiles, deterministic evaluation generator, `RESULTS.md` filled with actual outputs, short pitch, prerecorded demo fallback and current limitations.

### Decision register (this revision)
- **COMMITTED:** Blackout Mesh product focus; simulated grid electrical data; Stack A; hardware inventory as reported; hybrid rules+graph+optimization with optimization fallback.
- **SPECIFIED:** single authoritative FastAPI state machine; seven-load radial model; 5-Hz tick; CP-SAT + enumeration oracle; staged autonomous simulated execution; React Flow/shadcn UI; three-board gateway/indicators (two-board fallback); provenance and held-out benchmark standards.
- **OPTIONAL:** two potentiometer physical controls, second LCD/OLED polish, optional fault-novelty ML advisory, deeper active diagnosis, thermal-state model, true replay re-execution.
- **DEFERRED:** BLACKOUT MESH's actual three-channel ADC sensing circuit, 3.3-V physical electrical emulator, industrial sensing and mains switching, multi-hop mesh, pandapower as required architecture, cloud-first database.

### Change log
- **2026-10-09, v1.0:** Unified PriorityGrid and applicable BLACKOUT MESH engineering discipline into a single executable implementation blueprint. Resolved the source discrepancy of *physical 3.3V electrical sensing vs explicitly selected simulated telemetry*, separated world truth from observations, added hierarchy-aware power allocation, device ACK protocol, component interfaces, 24-hour gates, reproducible test coverage, claim controls and procurement checklist. No prototype is represented as already implemented or measured.

---

**Source artifacts consolidated:** `PRIORITYGRID_MASTER_PLAN.md` (original planning decisions), `PRIORITYGRID_HARDWARE_BOM.md`, `PRIORITYGRID_GITHUB_REFERENCE_MAP.md`, and the uploaded `BLACKOUT_MESH_Blueprint.md`. All proposed thresholds, timings and examples remain starting points until validated in actual runs.


## 23. Merge verification and retained requirements
This v1.1 consolidates the original master plan, the v1.0 unified blueprint and the earlier Blackout Mesh implementation plan. The detailed requirement/conflict register is a local-only merge review. The v1.0 plans are retained outside this repository as local history.

Additional mandatory regression checks: stale run/revision/idempotent request; wrong ACK mask/session/boot; backend/device restart; malformed/oversized frames; source capacity unknown; zero capacity; critical deficit; no new restoration on stale evidence; capacity fluctuations reset restoration wait; optional lockout configuration; simulation pause with live hardware monitoring; no radio output during replay. Schema fixtures must round-trip serial/radio fields and preserve null values.

Exhaustively compare 128 masks for capacities 0–100,000 W in 1,000-W steps, feeder configurations and prior masks; vary demand/branch limits and include the retained six-load fixture. Report full objective agreement and distinguish solver timeout/fallback from infeasible critical coverage. Test allocator/configuration rejection beyond the validated fallback ceiling.

Evaluation uses tuning seeds 1–20 and held-out seeds 101–120. S00–S15 × 20 seeds = 320 planned logical runs, not an achieved result. S08 in automated runs is explicitly virtual transport fault injection; real physical radio failure/ACK tests are separate. Freeze thresholds, generator assumptions and policy before held-out evaluation; do not tune against those outcomes. Include changed demand/topology conditions, not only new seeds. Multi-condition labels are scored independently; abstention/coverage/false alarms are reported separately. Direct contact-status interpretation is excluded from inferred-edge accuracy.

Critical service availability = served critical service-seconds / requested critical service-seconds, including disconnected critical services. Report reachable-only coverage as secondary. Modeled critical W·seconds is labeled simulated energy. Policy quality reports tuples/service benefits, ties and failures rather than an arbitrary percentage of tuple values. Real command RTT uses host monotonic send→validated ACK receipt, with median/p95/sample count and failures separately; test at least 30 logical commands per available peer plus loss/reboot cases.

Export `results/metrics.json`, `results/runs.csv` and `results/manifest.json` with code/config/policy versions, seeds, assumptions and measured environment. Until generated, show “benchmarks not run.” No field accuracy, energy savings or upstream results are implied.

### v1.1 change log — 2026-10-09
- Merged missing guarantees, baseline/trust/FSM/replay details and exhaustive failure checks; fixed session/boot/ACK identity and request ordering.
- Kept the newer seven-load/5-Hz model and selected stack, retained the six-load regression, unified restore timings (5 s stable / 3 s OFF / 1 s steps) and moved freeze to hour 16.
- Removed active team-role allocations. Preserved original GitHub reuse recommendations byte-for-byte in local-only archives; excluded their appendix from this repository.
- Implementation and physical performance remain unverified; only the planning merge and arithmetic are checked.
