# PriorityGrid — Remaining Hackathon Implementation Plan v2.0

**Intelligent, Fault-Aware and Resilient Power Management Network**
*Detect → Diagnose → Prioritize → Optimize → Act → Explain → Recover*

**Revision:** 2.0 — Adds hospital zone, RFID classroom zone, demo-first scope, and landing page.
**Date:** 2026-10-09
**Supersedes:** `PRIORITYGRID_HACKATHON_REMAINING_PLAN.md` v1.0
**Primary authority:** `PRIORITYGRID_FINAL_IMPLEMENTATION_BLUEPRINT.md` (for architecture, protocol, hardware, optimizer, and fault-diagnosis rules)

> **Change log:**
> - v2.0 (2026-10-09): Integrated three-room hospital zone and three-classroom RFID zone. Separated logical service allocation from physical LED outputs. Added landing page and /demo route. Defined indicator_command_mask vs indicator_confirmed_mask. Preserved six-service optimizer and 64-mask enumeration oracle.
> - v1.0: Initial RFID integration proposal.

---

## 1. Executive Summary

PriorityGrid is a locally hosted, offline decision console for a simulated six-service campus/clinic network. The backend owns one authoritative state. It simulates electrical telemetry, diagnoses faults, allocates capacity using OR-Tools CP-SAT (verified against exhaustive enumeration of all 64 masks), and sends indicator commands to real ESP32 hardware over ESP-NOW.

**This revision adds:**
1. **Hospital Zone** — Three hospital rooms whose essential lighting follows one shared service group (L0).
2. **Classroom Zone** — Three classrooms selectable via RFID, each mapped to services L3/L4/L5.
3. **Separation of logical service masks from physical LED masks** — the `indicator_command_mask` uses a different LED mapping than the `modeled_mask`.
4. **Demo-first landing page** at `/` with an interactive dashboard at `/demo`.

---

## 2. Generalized Facility Architecture

```
Site: PriorityGrid Campus
├── Power Source (SIMULATED, 14000 W)
├── Feeder A (6000 W limit)
│   └── Hospital Zone
│       ├── Hospital Room 1 (lighting → L0 group)
│       ├── Hospital Room 2 (lighting → L0 group)
│       ├── Hospital Room 3 (lighting → L0 group)
│       ├── Emergency Lighting (L1)
│       └── Water Pump (L2)
└── Feeder B (8000 W limit)
    └── Classroom Zone
        ├── Classroom 1 (L3, RFID Card 1)
        ├── Classroom 2 (L4, RFID Card 2)
        └── Classroom 3 (L5, RFID Card 3)
```

---

## 3. Service Catalog (Six Services — Unchanged IDs)

| ID | Name | Zone | Tier | Watts | Feeder | Notes |
|----|------|------|------|-------|--------|-------|
| L0 | Hospital Essential Circuit | Hospital | T1 | 2000 | A | Aggregate rating for required room-lighting group. Not a per-room measurement. |
| L1 | Emergency Lighting | Hospital | T1 | 1000 | A | |
| L2 | Water Pump | Hospital | T2 | 3000 | A | |
| L3 | Classroom 1 | Classroom | T2 | 2000 | B | Mapped to RFID Card 1 |
| L4 | Classroom 2 | Classroom | T2 | 2000 | B | Mapped to RFID Card 2 |
| L5 | Classroom 3 | Classroom | T3 | 4000 | B | Mapped to RFID Card 3 |

**Constraints:**
- Source capacity: 14000 W (initial nominal).
- Feeder A limit: 6000 W.
- Feeder B limit: 8000 W.
- Total nominal demand: 14000 W.

---

## 4. Hospital Zone — Three-Room Model

The hospital contains three separately identified rooms. All three rooms share the same essential lighting service group (L0).

**In this MVP:**
- If L0 is modeled as served → all three hospital room-light LEDs are commanded ON.
- If L0 is shed, unreachable, or unknown → all three hospital room-light LEDs are commanded OFF.
- The three rooms do NOT become three separate optimizer variables. The optimizer still sees six services: L0–L5.
- This keeps the 64-mask exhaustive enumeration oracle intact.

**Hospital rooms are presentation entities, not optimization variables.**

**Future expansion:** To give each room independent load-shedding decisions, add room-level services to the catalog and expand the optimizer from 2^6 to 2^N masks.

---

## 5. RFID Classroom Zone

### 5.1 Card-to-Classroom Mapping

| Registered Card | Classroom | Service | UID |
|-----------------|-----------|---------|-----|
| Card 1 | Classroom 1 | L3 | Pending hardware registration |
| Card 2 | Classroom 2 | L4 | Pending hardware registration |
| Card 3 | Classroom 3 | L5 | Pending hardware registration |

**Actual UIDs** must be obtained from the team's hardware registration process. Placeholder UIDs (`CARD_1_UID`, `CARD_2_UID`, `CARD_3_UID`) are used in configuration until real UIDs are registered.

### 5.2 RFID Behavior Rules

1. **Scanning a registered card:** Sets `active_classroom_id` to the mapped service. A scan alone does NOT activate a simulated load or turn on an LED.
2. **Scanning a different registered card:** Updates `active_classroom_id`. The previous classroom's indicator is commanded OFF. The new classroom's indicator is evaluated.
3. **Scanning an unknown card:** Clears `active_classroom_id`. All classroom indicator bits (3,4,5) are commanded OFF. An `UNKNOWN_CARD` event is recorded.
4. **No card scanned:** All classroom indicator bits remain OFF.
5. **Duplicate scan suppression:** Backend ignores scans of the same UID within a configurable cooldown (default 2 seconds).
6. **RFID reader disconnected:** `rfid_reader_status` is `NOT_CONNECTED`. Active classroom selection is preserved but stale.

### 5.3 Classroom LED Conditions

A classroom LED (bit 3, 4, or 5) may be commanded ON **only if ALL conditions hold:**

1. The card is registered.
2. That classroom is the currently selected (`active_classroom_id`).
3. A simulated load event is active for that classroom.
4. The modeled service is served (its bit is set in `modeled_mask`).
5. Its feeder (B) is reachable.
6. The relevant state is sufficiently current.

If ANY condition fails → that classroom's indicator bit is OFF.

**At most one classroom LED may be ON at any time.**

---

## 6. Physical LED Mapping (Six LEDs)

The physical LED positions use a DIFFERENT mapping from the service `modeled_mask`:

| LED Bit | Physical LED | Represents | Follows |
|---------|-------------|------------|---------|
| 0 | ESP32 #1 GPIO 25 | Hospital Room 1 lighting | L0 modeled state |
| 1 | ESP32 #1 GPIO 26 | Hospital Room 2 lighting | L0 modeled state |
| 2 | ESP32 #1 GPIO 27 | Hospital Room 3 lighting | L0 modeled state |
| 3 | ESP32 #2 GPIO 25 | Classroom 1 indicator | L3 + RFID selection + load active |
| 4 | ESP32 #2 GPIO 26 | Classroom 2 indicator | L4 + RFID selection + load active |
| 5 | ESP32 #2 GPIO 27 | Classroom 3 indicator | L5 + RFID selection + load active |

**Key distinction:**
- `modeled_mask` (bits 0–5) = service allocation decisions for L0–L5.
- `indicator_command_mask` (bits 0–5) = the physical LED commands derived from the allocation AND the additional hospital/RFID rules.

These two masks are NOT identical. The backend computes `indicator_command_mask` from `modeled_mask` plus the hospital room expansion and RFID selection logic.

---

## 7. Mask Semantics

| Mask | Bit Layout | Meaning |
|------|-----------|---------|
| `requested_mask` | L0–L5 | Which services are requested in the plan |
| `modeled_mask` | L0–L5 | Which services the allocator is serving |
| `indicator_command_mask` | LED 0–5 | What LEDs the backend wants driven |
| `indicator_confirmed_mask` | LED 0–5 | What LEDs firmware ACK confirms are actually driven |

Example: If `modeled_mask = 0b111111` (all served), `active_classroom_id = "L3"`, and L3 has an active load event:
- `indicator_command_mask = 0b001_111` = Hospital rooms 0,1,2 all ON (following L0), Classroom 1 ON, Classrooms 2,3 OFF.

If `active_classroom_id = None` (no RFID selection):
- `indicator_command_mask = 0b000_111` = Hospital rooms ON, all classroom LEDs OFF.

---

## 8. Snapshot Schema (v2)

The expanded `SystemSnapshot` response for `GET /api/v1/snapshot`:

```json
{
  "control_revision": 1,
  "generated_at": "2026-10-09T12:00:00+00:00",
  "source": { "kind": "SIMULATED", "capacity_w": 14000 },
  "feeder_limits_w": { "A": 6000, "B": 8000 },
  "requested_mask": 63,
  "modeled_mask": 63,
  "indicator_command_mask": 7,
  "indicator_confirmed_mask": null,
  "indicator_mask": null,
  "hardware_link": "NOT_CONNECTED",
  "services": [ ... ],
  "zones": {
    "hospital": {
      "rooms": [
        { "id": "HR1", "name": "Hospital Room 1", "lighting_service": "L0", "led_bit": 0 },
        { "id": "HR2", "name": "Hospital Room 2", "lighting_service": "L0", "led_bit": 1 },
        { "id": "HR3", "name": "Hospital Room 3", "lighting_service": "L0", "led_bit": 2 }
      ]
    },
    "classroom": {
      "active_classroom_id": null,
      "recent_rfid_scan": null,
      "rfid_reader_status": "NOT_CONNECTED",
      "classrooms": [
        { "id": "CR1", "name": "Classroom 1", "service_id": "L3", "rfid_card_registered": true, "led_bit": 3, "load_event_active": false },
        { "id": "CR2", "name": "Classroom 2", "service_id": "L4", "rfid_card_registered": true, "led_bit": 4, "load_event_active": false },
        { "id": "CR3", "name": "Classroom 3", "service_id": "L5", "rfid_card_registered": true, "led_bit": 5, "load_event_active": false }
      ]
    }
  }
}
```

**Backward compatibility:** The existing `services` array, `requested_mask`, `modeled_mask`, `indicator_mask`, and `hardware_link` fields are preserved. New fields (`zones`, `indicator_command_mask`, `indicator_confirmed_mask`) are additive. The existing frontend will ignore unknown fields and continue to work.

---

## 9. API Contracts

### Existing (preserved)
- `GET /api/v1/health` — `{ "status": "ok", "application": "PriorityGrid" }`
- `GET /api/v1/snapshot` — Full system snapshot (expanded with zones)

### New Endpoints

**`POST /api/v1/rfid/scan`**
```json
Request:  { "uid": "AA:BB:CC:DD", "event_id": "evt_001" }
Response: {
  "accepted": true,
  "active_classroom_id": "L3",
  "classroom_name": "Classroom 1",
  "service_id": "L3",
  "event_type": "CARD_RECOGNIZED"
}
```
Or for unknown card:
```json
Response: {
  "accepted": true,
  "active_classroom_id": null,
  "classroom_name": null,
  "service_id": null,
  "event_type": "UNKNOWN_CARD"
}
```
Duplicate scan (same UID within cooldown):
```json
Response: {
  "accepted": false,
  "active_classroom_id": "L3",
  "event_type": "DUPLICATE_SUPPRESSED"
}
```

**`POST /api/v1/simulation/capacity`**
```json
Request:  { "capacity_w": 8000 }
Response: { "accepted": true, "new_capacity_w": 8000, "control_revision": 2 }
```

**`POST /api/v1/simulation/classroom-load`**
```json
Request:  { "classroom_id": "CR1", "active": true }
Response: { "accepted": true, "classroom_id": "CR1", "load_event_active": true }
```

**`POST /api/v1/simulation/feeder`**
```json
Request:  { "feeder": "B", "available": false }
Response: { "accepted": true, "feeder": "B", "available": false, "control_revision": 3 }
```

---

## 10. Backend Processing Pipeline

```
RFID scan / Button press / Dashboard action (PHYSICAL_INPUT or REST)
  → Event validation and deduplication
  → State update (active classroom, load events, capacity, feeders)
  → Simulator tick
  → Observation generation
  → Fault detection
  → Fault diagnosis
  → Evidence Adapter → ConstraintSet
  → CP-SAT lexicographic allocation (T1 count → T1 importance → T2 → T3)
  → Exhaustive 64-mask verification (oracle)
  → Disagreement check (oracle wins if mismatch)
  → Decision validation (never exceed capacity/feeder limits)
  → Apply to simulated model (modeled_mask)
  → Compute indicator_command_mask from modeled_mask + hospital rules + RFID selection
  → Send indicator command to ESP32
  → Receive firmware ACK → update indicator_confirmed_mask
  → Publish snapshot
  → Persist event to SQLite/JSONL
```

---

## 11. Optimizer (Preserved)

- **Primary:** OR-Tools CP-SAT with lexicographic stages.
- **Oracle:** Exhaustive enumeration of all 64 masks.
- **Disagreement policy:** Oracle result wins, `SOLVER_DISAGREEMENT` event logged.
- **Constraints:** Source capacity, per-feeder capacity, feeder reachability.
- **Priority:** T1 count → T1 importance → T2 count → T3 count → minimize switching.
- **Critical shortfall:** If a T1 service cannot be served, report `CRITICAL_SHORTFALL` with reason codes and binding constraints.

---

## 12. Test Plan

### Automated Backend Tests

| # | Test | Expected |
|---|------|----------|
| 1 | GET /api/v1/health | `{"status": "ok", "application": "PriorityGrid"}` |
| 2 | GET /api/v1/snapshot returns 6 services | All L0–L5 present with correct tier/watts/feeder |
| 3 | Snapshot includes zones.hospital with 3 rooms | HR1, HR2, HR3 all linked to L0 |
| 4 | Snapshot includes zones.classroom with 3 classrooms | CR1→L3, CR2→L4, CR3→L5 |
| 5 | POST /api/v1/rfid/scan with registered UID | active_classroom_id set correctly |
| 6 | POST /api/v1/rfid/scan with unknown UID | active_classroom_id = null, UNKNOWN_CARD |
| 7 | Duplicate scan suppressed | DUPLICATE_SUPPRESSED within cooldown |
| 8 | indicator_command_mask: no RFID selection | Hospital room LEDs follow L0, classroom LEDs all OFF |
| 9 | indicator_command_mask: L3 selected, load active, served | Only LED bit 3 is ON among classroom bits |
| 10 | indicator_command_mask: L3 selected but shed | LED bit 3 is OFF |
| 11 | indicator_command_mask: L3 selected but no load event | LED bit 3 is OFF |
| 12 | indicator_command_mask: L0 shed | Hospital room LEDs (0,1,2) all OFF |
| 13 | Source capacity reduced to 6000W | T3 service (L5) shed first, then T2 |
| 14 | Feeder B unavailable | All Feeder B services (L3,L4,L5) shed |
| 15 | indicator_confirmed_mask remains null without hardware | No fabricated confirmation |
| 16 | Backward compatibility: existing frontend fields present | services, requested_mask, modeled_mask, indicator_mask all present |

### Hardware Tests (Deferred until firmware integration)
- RFID reader reads actual card UIDs
- ESP-NOW ACK carries applied mask
- LED physically illuminates correctly
- Reboot detection and resync

---

## 13. Frontend Plan (Not Implemented in This Stage)

### Route Structure
- `/` — Landing page with project introduction and "Launch Interactive Demo" button
- `/demo` — Interactive dashboard (current App.tsx, extended)

### Landing Page Sections
1. **Hero:** PriorityGrid branding, tagline, CTA button
2. **The Problem:** Supply shortages, feeder interruptions, communication faults
3. **The Solution:** Detect → Diagnose → Prioritize → Optimize → Act → Explain → Recover
4. **Demo Environments:** Hospital zone + Classroom zone descriptions
5. **Technology Stack:** React, FastAPI, OR-Tools, ESP32, ESP-NOW
6. **Truth Boundary:** Prominent disclaimer about simulated vs real
7. **Final CTA:** "Launch Interactive Demo"

### Demo Dashboard Updates
- Two facility zone tabs: Hospital Zone and Classroom Zone
- Hospital: 3 rooms, shared lighting group, emergency lighting, water pump
- Classroom: RFID selection state, load event state, modeled state, indicator command, confirmed indicator
- "Back to Home" link

---

## 14. Hardware Details (Pending)

| Item | Status |
|------|--------|
| RFID reader model | Unverified. Backend expects UID string over serial. Driver isolated. |
| RFID reader pin map | Pending board identification. Likely SPI to ESP32 #1 FIELD. |
| Actual RFID card UIDs | Pending hardware registration. Placeholder config used. |
| ESP32 board variant | Verify with `esptool` at Hour 0. Pin map assumes classic WROOM DevKit. |

---

## 15. Implementation Order (Demo-First)

### Stage 1: Backend Schema & State Management (THIS STAGE)
1. Expand Pydantic schemas for zones, hospital rooms, classrooms, RFID.
2. Implement singleton `GridState` with thread-safe state management.
3. Implement `POST /api/v1/rfid/scan` with UID validation and dedup.
4. Implement `POST /api/v1/simulation/capacity` for capacity changes.
5. Implement `POST /api/v1/simulation/classroom-load` for load events.
6. Implement `POST /api/v1/simulation/feeder` for feeder toggling.
7. Implement `indicator_command_mask` computation.
8. Implement basic priority-aware allocation (greedy by tier, then CP-SAT later).
9. Add automated tests.
10. Verify backward compatibility with existing frontend.

### Stage 2: Frontend Landing Page & Dashboard
1. Add React Router for `/` and `/demo`.
2. Build landing page component.
3. Extend dashboard with hospital/classroom zone views.
4. Connect new API endpoints.

### Stage 3: Firmware & Hardware Integration
1. Flash ESP32 boards.
2. Register actual RFID UIDs.
3. Implement RFID reader driver.
4. Wire LEDs and test indicator commands.
5. Test ESP-NOW ACK flow.

### Stage 4: End-to-End Demo
1. Full workflow: RFID scan → allocation → LED → ACK → dashboard.
2. Fault injection: capacity derate, feeder loss, RFID unknown card.
3. Recovery: staged restoration.
4. Record demo sequence.

---

## 16. Truth Boundary (Preserved)

| Real in the prototype | Simulated / modeled |
|-----------------------|---------------------|
| RFID card scans | Source capacity, feeder state, per-service demand |
| Physical button and potentiometer inputs | All voltage/current/demand/temperature values |
| ESP32 execution | Feeder contacts, sensor faults, observation loss |
| USB serial communication | Load shedding and restoration (the effect) |
| ESP-NOW packets, retries, ACKs | "Protection" and "tripping" |
| LED outputs driven by firmware | Any "kilowatt delivered/removed" |
| Firmware acknowledgements | |

**An illuminated LED indicates a modeled classroom state. It does not prove that real electrical power is flowing.**

---

## 17. Provenance Tags

| Tag | Meaning | Example |
|-----|---------|---------|
| `SIMULATED` | Generated by the simulator | `src.cap_w`, `fdrA.v_pu` |
| `PHYSICAL_INPUT` | Read from a real knob/button/RFID card | `pot_a_raw`, `btn_events`, `rfid_uid` |
| `DERIVED` | Computed from tagged inputs | `g`, `ρV`, `cdfT` |
| `ESTIMATED` | Model output with stated assumptions | `T_est`, `T_post` |
| `MODELED` | Effect of an accepted allocation in the simulator | `served_w`, shed set |
| `PHYSICAL_INDICATOR` | Firmware-confirmed GPIO state | `confirmed_mask` |
| `LINK_MEASURED` | Actual communication measurement | ACK RTT, packet loss |
