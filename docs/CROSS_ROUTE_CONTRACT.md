# Cross-route contract (#24)

Every live projection (`GET /api/v1/snapshot`, `GET|POST /api/v1/visualizers/classrooms`,
`GET|POST /api/v1/visualizers/hospital` and the `/ws/live` snapshot) carries a `contract` object built by
one function, `SiteAuthority.contract()` (`backend/app/core/site.py`). Routes keep their own layouts; the
contract is what they must agree on.

## Identity

| Field | Meaning |
|---|---|
| `site_id` | Site profile name. |
| `run_id` | Current site run. `SiteAuthority.new_run()` replaces it on every route at once. |
| `server_epoch` | Backend process start (Unix seconds). |
| `state_revision` | Site revision: advances when any part (campus, classroom, hospital) publishes. |
| `config_hash`, `catalog_version`, `policy_version`, `model_version` | Versions of the configuration in force. |
| `observation_time` | `generated_at` of the campus model's last published snapshot (UTC ISO 8601). |

Two responses with the same `run_id` and `state_revision` have identical `identity`, `campus_totals` and
`zone_totals` (`backend/tests/test_cross_route_contract.py`).

## Scoped totals

Each total is a `ScopeTotals` with an explicit `scope` and `unit`:

- `campus_totals` (`scope: "campus"`): whole-site source capacity, requested and served power.
- `zone_totals[zone]` (`scope: "zone:<zone>"`): per facility zone. Zones are **additive**: the sum of zone
  `requested_w` and `served_w` equals the campus values. Zones have no capacity of their own, so
  `capacity_w` is `null` (unknown, never zero).
- `view_totals` (`scope: "view:classroom_demo" | "view:hospital_demo" | "view:hospital_rehearsal"`): the
  route's own appliance-level demo, equal to that response's `effective_capacity_w`, `requested_w` and
  `served_w`. It is route-local and **not additive** into campus totals; do not compare a view total with
  `campus_totals` or put them on one axis without the scope label. It is `null` on the campus snapshot.

## Unit rules

- Control budgets and allocation: integer watts (`*_w`), unit `"W"`.
- Sensors: volts (`*_v`), amps (`*_a`), degrees Celsius (`*_c`), as floats; a missing reading is `null`.
- Energy (time-integrated) only as `*_wh` / `*_kwh`.
- Watt totals are real power. The electrical study (`docs/ELECTRICAL_SIMULATION.md`) is the only place that
  converts to reactive power, using its declared `power_factor` input; contract totals never do.

## Known limitations

- The frontend does not yet render `view_totals` or scope labels; pages still format their own numbers.
- There is no HTTP route for an explicit profile switch; `new_run()` is exercised from tests only.
- Hardware-confirmed LED state is applied to the campus snapshot at read time and is not part of the
  contract totals.
