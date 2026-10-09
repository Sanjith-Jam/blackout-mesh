# Blackout Mesh — implementation context

Updated 2026-10-09. Planning only; targets are not measured results.

## Authority

Follow [unified implementation plan v1.2](PRIORITYGRID_UNIFIED_IMPLEMENTATION_PLAN.md) and [AGENTS.md](AGENTS.md). The plan merges the newer seven-load blueprint with earlier reliability and validation requirements. Active tasks have no team-role allocations.

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
