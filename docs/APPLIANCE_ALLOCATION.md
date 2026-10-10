# Appliance-level allocation and the `/demo` power-system view

## What decides

Each of the 31 configured appliances is its own decision. That is 15 hospital appliances in ICU, Theatre and Wards behind transformers TX1–TX3 on feeder A, and 16 classroom appliances in CR1–CR3 on circuits L3–L5 on feeder B. Their demand comes from the site profile and is a configured simulated assumption, not a measurement.

Every tick, `ApplianceController` (`backend/app/core/appliance_control.py`) builds one problem and solves it with OR-Tools CP-SAT (`backend/app/core/appliance_allocator.py`). The applied plan is then projected onto the campus services, the classroom view and the hospital view, so every route shows the same decision in the same revision.

**Hard constraints.** An appliance can be served only if it is requested and has a closed path from the source. The plan must respect the source capacity, each feeder limit (an open feeder serves nothing), each zone budget, and the configured dependencies and indivisible groups.

**Objective.** The objective is lexicographic, with one CP-SAT stage per stage below. Every stage must be proven OPTIMAL.

1. Served watts in each priority class, highest class first. The classes in order are hospital critical, classroom essential, classroom active, classroom unknown, hospital support, classroom inactive and classroom idle. The `water_first` policy moves hospital support ahead of classroom active.
2. Fewest changes from the previous plan.
3. A fixed index tiebreak, so the optimum is unique and reproducible.

**Validation.** `validate()` re-checks every hard constraint independently of the solver. A plan that is not optimal, or that fails validation, is never applied. In that case a conservative fallback keeps the previous plan's still-eligible loads and sheds the lowest classes until the plan validates. That fallback is validated too.

**Oracle.** For problems with 20 or fewer appliances, `exhaustive()` enumerates every plan with the same objective. The tests check CP-SAT against it on 150 random problems plus targeted cases.

**Restoration.** Shedding is immediate. Restoration waits for 5 s of stable constraints and 3 s after the last shed, then adds back one group per second. A group is one priority class in one room, and groups restore highest class first. This is the existing restoration policy, applied per appliance.

A solve takes about 8 ms on the development host (`solve_ms` in `GET /api/v1/power-system`).

The six-service 64-mask enumerator in `GridState` is no longer the deciding allocator. It remains as a regression fixture, and `allocation.explanation.decisions[*].decided_by` is now `appliance_allocation` for L0–L5.

## API

- `GET /api/v1/power-system` returns appliances (configured demand, priority, requested, commanded, applied state, reachability, reason code and text, path, events), rooms, feeders, the source, zone budgets, topology edges with their states, derived constraint checks, injected faults (with provenance), the diagnosis, room LED indicators and the event log.
- `POST /api/v1/appliances/request` with `{appliance_id, requested}` toggles one appliance's request and returns 422 for unknown ids.

**Diagnosis.** The diagnosis is telemetry-only. A missing diagnosis reads `INCONCLUSIVE`, never nominal. The overall status is `CONSTRAINT_ACTIVE` when a derived capacity check is exceeded while telemetry is normal.

## `/demo`

`/demo` has five tabs: Overview, Floor Plan (the default), Electrical Network, Fault Detection and Electrical Laws. The tab lives in `?view=`, and switching tabs never resets the backend run. The old city page moved to `/city`. The landing page and its Launch Demo button are unchanged.

**Floor plan and network.** Both draw only the configured edges. Each wire's state is the backend's edge state, and only energized wires pulse (no pulse with reduced motion). Appliance state is shown by colour, line pattern, glyph and text together. Clicking an appliance opens its details. Room LEDs are room summaries following the board B rule, and are confirmed only by a live board ACK.

**Fault Lab.** Every button goes through the backend: kill and restore feeder A or B, drop capacity to 6,000 W and restore it, inject an ICU sensor dropout, and clear the hospital fault.

**Electrical Laws.** The page covers Ohm's law, power (DC, single-phase and three-phase), Kirchhoff's current law, Kirchhoff's voltage law, energy, capacity and continuity. Each panel is tagged EDUCATIONAL EXAMPLE, LIVE MODEL VALUES or DERIVED. Nothing is presented as a measurement.

## Verified behaviour

Recorded through the browser against the real backend on 2026-10-10:

| Step | Overall status | Served of capacity | Appliance states |
|---|---|---|---|
| Normal | NORMAL | 14,000 of 14,000 W | 31 served |
| Kill feeder A | FAULT_DETECTED (FEEDER_DISCONNECTED at feeder A) | 8,000 W | 15 hospital appliances unreachable, feeder B untouched |
| 1 s after restore | NORMAL | 8,000 W | 15 pending restoration |
| 15 s after restore | NORMAL | 14,000 W | 31 served |
| Drop capacity to 6,000 W | CONSTRAINT_ACTIVE | 6,000 W | 19 served, 12 shed; protected loads kept, each shed load says why |
| 20 s after restoring capacity | NORMAL | 14,000 W | 31 served |

In every step, the floor plan's and network's `data-state` for each appliance and wire matched the API. `frontend/e2e/power-system.spec.ts` asserts the same.

## Limitations

- Watts are configured values. There is no power flow, impedance or fault-current model, so short circuits are explicitly not modeled.
- When feeder A returns at reduced capacity, classroom optional loads shed immediately while hospital loads wait for the restoration gate. This follows the existing safety-first policy.
- The hospital upstream-loss fault still sets reachability from the injected fault itself, which is existing behaviour.
- None of this has been run on physical hardware.
