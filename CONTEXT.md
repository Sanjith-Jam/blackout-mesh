# Blackout Mesh — implementation context

Updated 2026-10-09. ESP32 A software is built/tested; physical and application/ML gates remain pending.

## Authority

Follow [unified implementation plan v1.2](PRIORITYGRID_UNIFIED_IMPLEMENTATION_PLAN.md) and [AGENTS.md](AGENTS.md). The plan merges the newer seven-load blueprint with earlier reliability and validation requirements. Current user scope: Person A input gateway. Person B output/controller integration remains pending.

The latest user instruction requires an ML classifier for which labs are in use. [LAB_ACTIVITY_ML_PLAN.md](LAB_ACTIVITY_ML_PLAN.md) takes precedence for catalog/model/objective/hardware. Random Forest is the first candidate, with rules/logistic-regression comparison; no specific JEV/JEPA architecture was requested.

## Confirmed scope

- Open-ended hackathon; approximately 24 hours and ₹1,500 spending ceiling.
- Nine-load primary, 84 kW configured: split the old 16-kW lab into 6/6/4-kW Labs A/B/C. Exact 512-mask oracle; old seven/six catalogs are separate 128/64-mask regressions.
- React/TypeScript/Vite frontend, Python/FastAPI state authority, NetworkX/NumPy, OR-Tools, SQLite and ESP32/ESP-NOW as specified in the plan.
- Simulated power and observations, real radio/LED feedback. No mains switching, backup supply or implemented multi-hop mesh claim.
- Phase 0 complete by user declaration. Two ESP32s answered chip/flash queries; user reports two working and one broken. No Arduino or displays. RFID reader/three cards, four buttons, LEDs/resistors/breadboards, servo and ultrasonic sensor available; exact peripheral ratings and clean-firmware bring-up remain pending. No potentiometer. Do not buy hardware by default.
- Code reuse is authorized; verify upstream licenses and preserve required notices when incorporating code. Research recommendations remain in local-only archives.
- Graphify and Security Auditor are installed for explicit on-demand use only.

## Validation and next action

Plan review checked allocation arithmetic, packet field widths, links and unchanged local reuse recommendations. No application/model/solver/firmware integration was validated. Local Phase 0 ROM/flash queries succeeded on two ESP32s; these are not RF/GPIO/model tests.

Implement ML plan phases M0–M5 alongside the unified component gates: causal observation schema, grouped synthetic data, baselines/trained artifact, validated priority/allocator, then real card/LED integration. Model training/evaluation remain pending. Hardware cards identify labs rather than select a forced priority profile. Update this file and README with commands and actual results as implementation progresses.

Historical plans and review records are outside the repository. The inherited blueprint reference was not independently available; do not treat it as separately verified evidence.

## Person A implementation — first piece

Added production input/button state machines and explicit 26-byte v2 codec. Host sanitizer assertions pass (`python3 tools/test_esp32_a.py`). Board carrier/reader unidentified; no wiring or flashing performed. Next: serial and radio lifecycle, Arduino adapters, compile and bring-up guide.

Radio lifecycle piece: host assertions cover one in-flight packet, latest-unsent coalescing, 200/400-ms retries, 600-ms timeout, boot/session/ACK identity and physical projection. `python3 tools/test_esp32_a.py` passes. Actual B integration remains pending.

Serial lifecycle piece: bounded 512-byte frames, strict host fields, reconnect epochs, persistent-session floor, event acknowledgments and freshness checks added. Host assertions including malformed/oversized/trailing data and stale events pass. Connected `/dev/ttyUSB0` is inaccessible to current process (permission denied); no chip query or flash succeeded.

Recovery checks: RESET now raises the persisted session floor; old B boot reports cannot overwrite a newer boot; CR is accepted only as a terminal frame delimiter. Native sanitizer assertions pass, including all 512 mask projections. The two firmware targets compile with the reported RC522 pins.

Arduino adapter piece: RC522 pins use the user-reported wiring, buttons use the new 25/26/27/32 guide (not wired yet), UID/peer credentials stay local. Reader task isolates synchronous driver waits. Both normal and enrollment targets compiled successfully; encrypted-radio path also linked successfully using temporary synthetic peer provisioning (never flashed; removed afterward).

Gateway loop piece: compiled the nonblocking Arduino event loop, persisted boot/session counters, host acknowledgments, two-second reset and bounded serial/radio queues. Reader errors are distinct from unknown UIDs. Both PlatformIO environments pass; physical checks are blocked by serial permissions.

Contract fixtures piece: explicit serial/radio v2 agreement, Python codec and six golden wire fixtures added. `python3 tools/test_radio_protocol.py` passes one test including all 512 masks; production C++ golden fixture matches. Person B must adopt this previously unimplemented contract before integration.

Host utilities piece: local exclusive-create UID enrollment and synchronized input-only console added. `python3 tools/test_host_tools.py`: 3 tests pass (fake serial, no hardware); registration preserves A+B and repeated events are deduplicated. No allocation/output claims from this console.

## Person A handoff

Done: firmware, private UID/peer templates, RC522 task, four button state machines,
bounded JSONL, host sync/event ACK, encrypted radio adapter, strict v2 codec,
retries/projection/boot guards, enrollment/input-only console and bring-up docs.
`python3 tools/test_esp32_a.py`: C++ sanitizer assertions pass, including all 512
mask projections. `python3 tools/test_radio_protocol.py`: 1 test passes with all
512 round trips. `python3 tools/test_host_tools.py`: 3 tests pass using fake serial.
`pio run -d firmware -e esp32-a -e esp32-a-enroll`: both SUCCESS (7.061s / 3.543s).
Encrypted-radio code path also compiled with temporary synthetic provisioning,
removed afterward; no flashing or real radio test. Versions pinned after builds.

Failure remaining: `/dev/ttyUSB0` root:uucp 0660 denies this process access. No chip
query/flash succeeded. User supplied RC522 wiring SS21/SCK18/MOSI23/MISO19/RST22
and reports it powered; board carrier and actual reader operation remain unverified.
User has not wired buttons; guide uses 25/26/27/32 to GND, internal pull-ups.

Next: user resolves serial membership and restarts the app; verify board labels,
wire buttons with USB removed, flash enrollment, capture cards locally, flash
normal firmware and run input console. Then agree contract/provision peers with
Person B and record physical acceptance. Never run input console alongside the
real controller. Classifier, allocator, UI and B firmware remain unimplemented
in this repository. See ESP32_A_STATUS.md for outputs, limits and exact commands.
