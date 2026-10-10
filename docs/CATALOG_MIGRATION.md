# Site catalog inventory and migration table (#3)

Catalog version `site-catalog-2026-10-10.1`, now `site-catalog-1.1` from `backend/sites/default_campus.json` (#26: the inventory below is defined by that profile; see `docs/SITE_PROFILES.md`). This file records every identifier, load, feeder, room mapping and route command that existed before the three demo authorities were placed under one site authority. It must be updated in the same commit as any catalog change.

## Before: three independent authorities

| Authority | Where | Owned state | Budget |
|---|---|---|---|
| Campus (`GridState`) | `backend/app/core/state.py` | source capacity, feeder availability, RFID selection, classroom load events, activity evidence, six-service allocation, restoration gate | 14,000 W source; feeder A 6,000 W; feeder B 8,000 W |
| Classroom demo (`ClassroomDemo`) | `backend/app/visualizers.py` | scanned rooms, classroom supply limit, recorded replay cursor, appliance allocation, restoration gate | own 8,000 W limit (0–8,000 W slider, 3,400 W preset) |
| Hospital fixtures | `backend/app/main.py` globals + `hospital_snapshot()` | selected scenario and scanned zone | none (sensor fixtures only) |

## Campus services (unchanged IDs and mask bits)

| Bit | ID | Name | Tier | Feeder | W | Protected (#22) |
|---:|---|---|---|---|---:|---|
| 0 | L0 | Hospital Essential Circuit | T1 | A | 2,000 | yes |
| 1 | L1 | Emergency Lighting | T1 | A | 1,000 | yes |
| 2 | L2 | Water Pump & HVAC | T2 | A | 3,000 | no |
| 3 | L3 | Classroom 1 | T2 | B | 2,000 | lighting + computers |
| 4 | L4 | Classroom 2 | T2 | B | 2,000 | lighting + computers |
| 5 | L5 | Classroom 3 | T3 | B | 4,000 | lighting + computers |

Feeder A requests 6,000 W (= its limit); feeder B requests 8,000 W (= its limit); total 14,000 W (= normal source).

## Classroom appliance leaves decompose L3–L5

The classroom demo's appliances are the leaves of the campus classroom services. Parent and leaves are never both counted: campus totals use services, classroom totals use leaves, and a test asserts the sums agree.

| Room | Parent | Leaves (W) | Sum |
|---|---|---|---:|
| CR1 | L3 | lighting 100*, computers 600*, fans 100, projector 200, AC 1,000 | 2,000 |
| CR2 | L4 | lighting 100*, computers 600*, fans 100, projector 200, AC 1,000 | 2,000 |
| CR3 | L5 | lighting 100*, computers 600*, fans 100, projector 200, AC 1,000, instruments 2,000 | 4,000 |

\* protected essential minimum (#22). Classroom leaves total 8,000 W = feeder B limit.

## Hospital equipment leaves decompose L0–L2

The `/hospital` route is `HospitalPriorityDemo`: ICU, Theatre and Wards behind TX1–TX3, with zone scans and a named 0–6,000 W hospital limit (6,000 W normal, 4,000 W overload preset). Its equipment are the leaves of the campus feeder A services, by tier: essential equipment belongs to T1 services, optional equipment to L2. `reconcile_catalog()` refuses to start if any sum or tier disagrees.

| Parent | Leaves (W) | Sum |
|---|---|---:|
| L0 Hospital Essential Circuit (T1) | ICU ventilator 300, monitor 100, infusion 50, O₂ 500; Theatre anesthesia 200, ESU 650, monitor 100; Wards nurse call 100 | 2,000 |
| L1 Emergency Lighting (T1) | ICU emergency lights 200; Theatre surgical light 500; Wards bed lights 300 | 1,000 |
| L2 Water Pump & HVAC (T2) | Theatre climate 900; Wards fans 300, water pump 600, AC 1,200 | 3,000 |

By zone: ICU 1,150 W, Theatre 2,350 W, Wards 2,500 W; total 6,000 W = feeder A limit.

Injected faults (overload, cooling failure, both, upstream loss, sensor dropout, stuck sensor) are persistent hospital state until `clear_fault` or reset. `app/simulation/sensors.py::apply_fault` turns them into telemetry; diagnosis sees only the resulting observations. Only upstream loss changes allocation, by removing the hospital's incoming supply.

## Room and indicator mappings (unchanged)

| Room | Campus service | LED bit | RFID default UID |
|---|---|---:|---|
| CR1 | L3 | 3 | `CARD_1_UID` |
| CR2 | L4 | 4 | `CARD_2_UID` |
| CR3 | L5 | 5 | `CARD_3_UID` |
| HR1–HR3 | L0 | 0–2 | — |

## Route commands and where they go now

Every command below goes through `SiteAuthority.command()`, which applies it, ticks every part once and returns the site's `run_id` and `revision`.

| Route | Command | Applies to |
|---|---|---|
| `POST /api/v1/rfid/scan` | RFID scan | campus |
| `POST /api/v1/simulation/capacity` | source capacity | campus (and, through coupling, the classroom and hospital budgets) |
| `POST /api/v1/simulation/feeder` | feeder availability | campus (and, through coupling, the classroom and hospital budgets) |
| `POST /api/v1/simulation/classroom-load` | classroom load event | campus |
| `POST /api/v1/activity/observations` | activity evidence | campus |
| `POST /api/v1/replay` | campus replay start/pause/reset | campus |
| `POST /api/v1/visualizers/classrooms` | scan/unscan, classroom limit, presets, replay controls, reset | classroom |
| `POST /api/v1/visualizers/hospital` | zone scan/unscan, hospital supply limit, presets, reset, `inject_fault` / `clear_fault` (the old `scenario` field is an alias) | hospital zone view |
| `POST /api/v1/site/scenario` | named teaching scenario (#33) | campus source and feeders, classroom limit, hospital limit; clears a hospital fault |

## Coupling introduced in this step

The classroom view now allocates within `min(classroom limit, campus feeder B headroom)`. Headroom is 0 when feeder B is unavailable, otherwise `min(feeder B limit, source capacity − campus-served feeder A watts)`. A campus shortage or feeder B trip therefore reaches the classroom page in the same revision. The classroom limit slider stays as an explicitly named sub-budget (`classroom_limit_w`).

The hospital view allocates within `min(hospital limit, campus feeder A served watts)`: the watts of L0–L2 that the campus allocator served, or 0 when feeder A is unavailable. A campus shortage or feeder A trip therefore reaches the hospital page in the same revision, and the hospital view can never serve more than the campus granted feeder A.

## One feeder B decision (#33)

The campus allocator decides the feeder A services (L0–L2) as whole services and grants feeder B a budget: `min(feeder B limit, source capacity − feeder A served)`, or 0 when feeder B is open. The classroom leaf allocation is then the only decision inside feeder B. The campus snapshot publishes L3–L5 from those leaves:

- `requested_w` / `served_w` on each service are the sums of its room's leaves; `served_w` can be partial (for example 2,100 W of essentials across three rooms).
- `modeled_served` and the L3–L5 bits of `modeled_mask` mean "some of this room is energized"; `model_reason` says "Partly served" when it is not all of it.
- Feeder, source, zone and allocation totals add leaf watts, so `/demo`, `/classrooms` and `/hospital` reconcile from leaves to feeders to the source in the same revision.
- `allocation.explanation.decisions` marks L3–L5 `decided_by: classroom_leaf_allocation` with leaf `served_w` and `shortfall_w`. The allocator's own masks stay in `campus_proposed_mask` / `campus_applied_mask`; replay the restoration gate against those.
- Room sessions (RFID, classroom scans, board A) rank rooms for optional loads. They no longer decide whether a whole room is requested, because the classroom view always requests every leaf and protects every room's essentials.

`GridState` used alone (no site authority) keeps whole-service projection.

## Named teaching scenarios (#33)

`GET /api/v1/site/scenarios` lists them; `POST /api/v1/site/scenario {"scenario": name}` applies one as one command and one revision on every route. Each scenario sets every budget below, so switching never leaves part of the previous one behind. Sessions and recorded replay are kept. Values come from the active site profile (#26); a site profile itself is still chosen at startup only. For the default campus:

| Scenario | Source | Feeders | Classroom limit | Hospital limit |
|---|---:|---|---:|---:|
| `normal` (default) | 14,000 W | A, B closed | 8,000 W | 6,000 W |
| `source_shortage` | 6,000 W (feeder A limit) | A, B closed | 8,000 W | 6,000 W |
| `feeder_b_trip` | 14,000 W | B open | 8,000 W | 6,000 W |
| `classroom_overload` | 14,000 W | A, B closed | 3,400 W (feeder B preset) | 6,000 W |
| `hospital_overload` | 14,000 W | A, B closed | 8,000 W | 4,000 W (feeder A preset) |

The site identity's `scenario` names the active scenario, or `custom` after a budget is changed by hand (capacity, feeder, either slider or preset, or a view reset). The per-page presets and sliders remain as documented equivalents.

## Remaining migration

- Feeder A is still decided as whole services by the campus allocator; the hospital view decides equipment within the watts it granted. Deriving L0–L2 from hospital leaves the same way as feeder B is not done.
- The feeder B budget comes from a whole-room campus solve over L3–L5, so the campus may shed L2 to make room for a classroom that the leaves then only partly fill.
