# Site catalog inventory and migration table (#3)

Catalog version `site-catalog-2026-10-10.1`. This file records every identifier, load, feeder, room mapping and route command that existed before the three demo authorities were placed under one site authority. It must be updated in the same commit as any catalog change.

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
| 2 | L2 | Water Pump | T2 | A | 3,000 | no |
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

## Hospital zone view (not mapped)

The `/hospital` route is `HospitalPriorityDemo`: ICU, Theatre and Wards behind TX1–TX3, with zone scans, its own 0–7,000 W supply limit (7,000 W normal, 3,000 W overload preset) and essential equipment served first.

| Zone | Essential (W) | Optional (W) | Total |
|---|---|---|---:|
| ICU | ventilator 300, monitor 100, infusion 50, lights 50, O₂ 500 | — | 1,000 |
| Theatre | surgical light 500, anesthesia 200, ESU 800, monitor 100 | climate 1,400 | 3,000 |
| Wards | nurse call 100 | bed lights 200, fans 500, TV 200, AC 2,000 | 3,000 |

These 7,000 W do not reconcile with the campus feeder A services (L0 2,000 + L1 1,000 + L2 3,000 = 6,000 W). There is no reviewed mapping, so the hospital view is not coupled to the campus budget. It shares the site run identity and revision only. The earlier scenario-based transformer sensor fixtures (`hospital_snapshot`) still exist in code but are no longer served by a route.

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
| `POST /api/v1/simulation/capacity` | source capacity | campus (and, through coupling, the classroom budget) |
| `POST /api/v1/simulation/feeder` | feeder availability | campus (and, through coupling, the classroom budget) |
| `POST /api/v1/simulation/classroom-load` | classroom load event | campus |
| `POST /api/v1/activity/observations` | activity evidence | campus |
| `POST /api/v1/replay` | campus replay start/pause/reset | campus |
| `POST /api/v1/visualizers/classrooms` | scan/unscan, classroom limit, presets, replay controls, reset | classroom |
| `POST /api/v1/visualizers/hospital` | zone scan/unscan, hospital supply limit, presets, reset | hospital zone view |

## Coupling introduced in this step

The classroom view now allocates within `min(classroom limit, campus feeder B headroom)`. Headroom is 0 when feeder B is unavailable, otherwise `min(feeder B limit, source capacity − campus-served feeder A watts)`. A campus shortage or feeder B trip therefore reaches the classroom page in the same revision. The classroom limit slider stays as an explicitly named sub-budget (`classroom_limit_w`).

## Remaining migration (not done in this step)

- The campus allocator still decides L3–L5 as whole rooms while the classroom view decides appliances. Both respect the same feeder B budget, but they are two decisions. Next step: derive L3–L5 served watts from the leaf allocation (partial service) and retire whole-room classroom decisions.
- Campus RFID events, classroom-view scan controls and board session events now share `GridState.active_sessions`; these update the same requested campus services and classroom projection (#21). Hardware inputs remain simulated/unconnected unless the explicitly provisioned gateway is present.
- The hospital zone view (7,000 W) is not mapped to campus feeder A (6,000 W).
- `GridState` is still a process-wide singleton (#11).
