# PriorityGrid: Remaining Hackathon Implementation Plan (Revised)

*This document supersedes conflicting sections in the original blueprints (`PRIORITYGRID_FINAL_IMPLEMENTATION_BLUEPRINT.md` and `PRIORITYGRID_UNIFIED_IMPLEMENTATION_PLAN.md`) by incorporating the new RFID classroom requirements while preserving the foundational architecture.*

## 1. Executive Summary & New RFID Scope
The PriorityGrid project now includes an RFID reader and three registered RFID cards representing three distinct classrooms. The core mission remains: a fault-aware, capacity-constrained power allocation simulation where a FastAPI backend is the authoritative decision-maker.

**New Requirement:**
* The RFID reader provides a `PHYSICAL_INPUT` that selects the "Active Classroom".
* The dashboard displays the status of all services, but **only the LED associated with the currently selected classroom** may illuminate.
* An LED illuminates **only if** its classroom is selected AND the backend simulator/allocator determines that the modeled classroom service is currently powered.
* Scanning a new recognized card changes the active classroom.
* Scanning an unregistered card clears the selection (no LEDs illuminate).

## 2. Service Catalog & RFID Mapping
To cleanly integrate the classrooms without breaking the existing constraints (14kW source, 6kW Feeder A, 8kW Feeder B), the three classrooms map directly to services L3, L4, and L5 on Feeder B. The electrical properties and priorities are preserved.

**Revised Catalog:**
* **L0:** Clinic Essential Circuit — T1, 2000 W, Feeder A
* **L1:** Emergency Lighting — T1, 1000 W, Feeder A
* **L2:** Water Pump — T2, 3000 W, Feeder A
* **L3:** Classroom 1 (formerly Communications Room) — T2, 2000 W, Feeder B  *(Mapped to RFID Card 1)*
* **L4:** Classroom 2 (formerly Cold Storage) — T2, 2000 W, Feeder B *(Mapped to RFID Card 2)*
* **L5:** Classroom 3 (formerly Comfort Cooling) — T3, 4000 W, Feeder B *(Mapped to RFID Card 3)*

**Note on LEDs:**
The 6 LEDs are still available. However, for the classrooms, LEDs 3, 4, and 5 represent Classroom 1, 2, and 3. LEDs 0, 1, and 2 can remain bound to L0, L1, L2 persistently, OR all LEDs can be conditionally driven. For this plan, **only the active classroom's LED** (from L3, L4, L5) will illuminate based on selection, while L0, L1, L2 LEDs behave normally.

## 3. Architecture & Truth Boundary
The project maintains a strict truth boundary:
* **PHYSICAL_INPUT:** RFID card scans, which determine the `active_classroom` state in the backend.
* **SIMULATED:** The overall power constraints, grid capacity, and individual service demands.
* **MODELED:** The output of the CP-SAT allocator determining which services (L0-L5) actually receive power.
* **PHYSICAL_INDICATOR:** The ESP32-driven LEDs reflecting the `indicator_mask` sent by the backend.

**The ESP32 is a thin client:** It reads the RFID scanner, sends the UID to the backend, and drives LEDs based *only* on the backend's explicit `indicator_mask` command. It makes no optimization decisions.

## 4. End-to-End Workflow
1. **Startup:** Backend starts, Simulator initializes with 14kW capacity, ESP32 gateway connects via USB.
2. **Idle State:** No RFID card is scanned. Simulator runs and allocates power (e.g., all 6 services served). Dashboard shows all services modeled as served. **Classroom LEDs (3,4,5) are OFF.**
3. **RFID Scan:** User scans Card 1 (Classroom 1).
4. **Validation:** ESP32 sends UID. Backend validates UID -> Classroom 1 (L3).
5. **Mask Generation:** Backend sets `active_classroom = "L3"`. The allocator's `modeled_mask` has bit 3 high (L3 is served). The backend calculates the `indicator_mask`. For the classroom bits, only bit 3 is allowed to mirror the `modeled_mask`. Bits 4 and 5 are forced low.
6. **Hardware Command:** Backend sends the new `indicator_mask` to the ESP32.
7. **Confirmation:** ESP32 illuminates LED 3, turns off 4 and 5. It sends an ACK back to the backend.
8. **Dashboard Update:** Frontend receives the updated snapshot. It independently displays the `active_classroom` (Classroom 1), the `modeled_mask` (all served), and the `indicator_confirmed` mask (LED 3 is ON).

## 5. API & Data Contracts
### Snapshot Schema Updates
The `SystemSnapshot` must be expanded to include RFID selection state:
* `active_classroom_id: Optional[str]` (e.g., "L3", "L4", "L5", or `None` if unregistered/cleared).
* `recent_rfid_scan: Optional[str]` (The raw UID of the last scan, for debugging/registration).

### New Endpoint
* **`POST /api/v1/rfid/scan`**
  * **Payload:** `{ "uid": "xx:xx:xx:xx" }`
  * **Action:** Validates the UID against a configured map (e.g., `{"AA:BB:CC:DD": "L3"}`). Updates `active_classroom_id`. If unknown, clears `active_classroom_id`.

## 6. Testing Strategy
**Acceptance Criteria:**
* **Selection:** Scanning Card 1, 2, or 3 exclusively sets `active_classroom_id` to L3, L4, or L5.
* **LED Isolation:** If Classroom 1 (L3) is active and powered, LED 3 is ON. LEDs 4 and 5 MUST be OFF, even if the allocator serves L4 and L5.
* **Power Truth:** If Classroom 1 (L3) is active but its power is shed (e.g., capacity drops to 6kW and Feeder B is unpowered), LED 3 MUST be OFF. An RFID scan cannot force the LED ON without power.
* **Unknown Cards:** Scanning an unregistered card clears the `active_classroom_id` and forces LEDs 3, 4, and 5 OFF.
* **Dashboard Integrity:** The UI clearly separates the "Modeled Service State" (what the simulation is doing) from the "Indicator State" (which physical LED is glowing).

## 7. Pending Hardware Details
* **RFID Reader Model:** Assuming standard SPI (e.g., RC522) or UART reader. Pin map pending final physical assembly. The Python backend expects a simple UID string, decoupling it from driver specifics.
* **Debouncing:** The ESP32 firmware must debounce the RFID reader (e.g., 2-second cooldown between identical reads) to prevent spamming the backend API.

## 8. Implementation Order
1. **API Update:** Update the FastAPI `SystemSnapshot` and create the `POST /api/v1/rfid/scan` endpoint.
2. **Frontend Update:** Update the React dashboard to display the `active_classroom_id` prominently and differentiate the modeled state from the LED indicator state.
3. **Allocator Integration:** Update the backend simulation loop to calculate the `indicator_mask` based on the `modeled_mask` and the `active_classroom_id`.
4. **Firmware:** Integrate the RFID driver on the ESP32. Send the scanned UIDs to the backend via Serial.
5. **Testing:** Execute the E2E workflow with physical cards and LEDs.
