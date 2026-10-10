# Site profiles (#26)

A site profile is one JSON file that defines everything site-specific the controller and the three views use: the source, both feeders, the campus services, classrooms and their appliances, hospital zones (one transformer each) and their equipment, LED bits, board A room letters and shortage presets. No Python edit is needed to run a different site.

```bash
# validate one or more profiles without starting the server
PYTHONPATH=backend python -m app.core.config backend/sites/default_campus.json backend/sites/small_test_site.json

# run the backend on another profile
SITE_PROFILE=backend/sites/small_test_site.json PYTHONPATH=backend uvicorn app.main:app
```

The profile is loaded and validated once, at startup (`app/core/active_site.py`). Changing it means a restart, which starts a new run with a new config hash. There is no live partial mutation.

## Shipped profiles

| File | Services | Classrooms | Hospital zones | Source |
|---|---:|---:|---:|---:|
| `default_campus.json` | 6 (L0–L5) | 3 (CR1–CR3) | 3 (ICU, Theatre, Wards) | 14,000 W |
| `small_test_site.json` | 4 (S0–S3) | 2 (LAB, SEM) | 2 (Clinic, Pharmacy) | 6,000 W |

`default_campus.json` reproduces the reference catalog in `docs/CATALOG_MIGRATION.md` exactly; `backend/tests/test_config.py` pins it.

## Asset types

| Type | Parent | Required | Optional |
|---|---|---|---|
| `source` | none | `capacity_w` | |
| `feeder` | source | `capacity_w` | `shortage_preset_w` (the zone view's overload preset) |
| `service` | feeder | `rating_w`, `tier` (T1–T3), `zone` (`hospital` or `classroom`) | |
| `classroom` | classroom service | `led_bit` | `hardware_room` (board A letter A–Z) |
| `hospital_room` | hospital service | `led_bit` | |
| `transformer` | feeder A | `zone` (the hospital zone it serves) | `rated_current_a` |
| `load` | classroom or transformer | `rating_w`, `essential` | `key`; `service_id` (required under a transformer) |

All assets take `id`, `name`, and optionally `coords` and `policy_refs`. Unknown fields are rejected. A load's `key` defaults to its id without the `L_<parent>_` prefix.

## What validation rejects

Every problem is listed at once, each naming the asset to fix:

- wrong JSON types (strict: `2000.5` or `"2000"` watts are refused), negative or non-finite numbers, unknown fields;
- duplicate ids, dangling parents, cycles, an asset under the wrong parent type;
- fields in the wrong unit for the asset (for example `rating_w` on a transformer, whose rating is `rated_current_a`);
- children whose declared capacity or watts exceed their parent;
- classroom or hospital leaves that do not sum to their service's watts, essential equipment on a non-T1 service;
- a repeated LED bit or board A room letter, an LED bit outside the 9-bit radio mask, more than 9 services;
- a `fault_zone` that is not a transformer zone.

## Identity

`get_config_hash()` is a SHA-256 over the validated profile's canonical JSON (first 12 hex digits). It appears in every snapshot's `contract.identity.config_hash`, in every view's `site.config_hash`, and in the context of every persisted allocation decision.

## Card enrollment stays private

Profiles never contain card UIDs. `backend/sites/rfid_enrollment.json` holds placeholders only; put real UIDs in the untracked `backend/sites/rfid_enrollment.local.json` (git-ignored), which wins when present. `RFID_ENROLLMENT` points at another file. Cards enrolled for rooms the active site does not have are ignored.

## Limits

- The controller models a two-feeder radial campus: feeder `A` serves hospital services and transformers, feeder `B` the classroom services. Profiles with other feeder ids are refused with that message.
- Each classroom service decomposes into exactly one classroom.
- The classroom, hospital and city pages take their scan buttons, room requests and full-supply labels from the API. The campus dashboard's L0–L2 cards, the classroom and hospital blueprint drawings and the city map are not generated from asset types yet; they are still drawn for the default campus (tracked as a follow-up issue).
- The allocation policy's "water" objective term still recognizes `L2` by id when no service has zone `water`.
- The optional electrical study keeps its own feeder ratings in amps (`app/simulation/electrical.py`).
