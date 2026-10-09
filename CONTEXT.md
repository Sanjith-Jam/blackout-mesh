# Blackout Mesh — implementation context

Updated 2026-10-09. Remote application/Board B work and local ESP32 A work are merged. See [progress report](PROGRESS_REPORT.md) for current evidence, blockers and next actions; [ESP32 A handoff](ESP32_A_STATUS.md) retains its original build/physical limits.

## Current state

Frontend production build, 10 backend API tests, 16 B simulation tests, A native assertions, Python fixtures/tools and both A firmware builds pass. The repository includes a prior B USB log reporting 15/15 checks; it was not rerun during synchronization. No new physical tests or device flashing occurred.

The prototype is not integrated: A/B serial/radio contracts differ; backend and bench use different state owners, catalogs and RFID semantics. No trained classifier exists. Backend ACK fields remain unconfirmed. Do not label individual passing suites as end-to-end success.

## Scope and authority

- Remote current application plan: [remaining plan v2.0](PRIORITYGRID_HACKATHON_REMAINING_PLAN.md) and [blueprint](PRIORITYGRID_FINAL_IMPLEMENTATION_BLUEPRINT.md).
- [Required ML plan](LAB_ACTIVITY_ML_PLAN.md) preserves the user's explicit trained-classifier requirement. Its nine-load catalog differs from the web app's six-load catalog; resolve this explicitly, keeping all values labeled by configuration.
- Physical first milestone: two ESP32s, one RFID reader, three cards, three classroom LEDs and four buttons. Full two-person plan is local-only in `/home/bread/blackout-mesh-local/`. Phase 0 stays complete.
- Simulated power; real radio/LEDs only after verified. No real occupancy accuracy, power delivery, savings or multi-hop mesh claim.
- Approximately 24-hour hackathon and ₹1,500 ceiling; no Arduino/displays. Unknown 12 V/amp/motor modules stay outside baseline.
- Reuse recommendations unchanged and local-only; keep keys, UIDs, device backups and raw local logs out of Git. Graphify/Security Auditor are explicit on-demand only.

## Next action

Agree and implement one A/B host/radio contract with shared golden fixtures. Resolve catalog and RFID behavior, then integrate the single backend authority, required classifier and actual card/LED ACK flow. Fix incompatibility before attempting an unchanged A-to-B radio demo. Commands and precise results are in PROGRESS_REPORT.md and AGENTS.md.

The old unified implementation plan was removed upstream; its prior local revision is preserved in the local archive. Historical details in the A handoff describe its original scope and should be read with the new progress report.
