# Blackout Mesh — implementation context

Updated 2026-10-09. Remote application/Board B work and local ESP32 A work are merged. See [progress report](PROGRESS_REPORT.md) for current evidence, blockers and next actions; [ESP32 A handoff](ESP32_A_STATUS.md) retains its original build/physical limits.

## Current state

UI: the original light graph-paper theme remains. `/classrooms` now presents one compact tiled game-style campus map with three classrooms, small equipment sprites and a prominent shared current-flow overlay; `/hospital` independently shows three transformers, sensors and likely-cause evidence. The original `/demo` React Flow nodes now have explicit dimensions and render visibly. Model/replay presentation remains available through the API. Frontend production build passes with its existing large-bundle warning.

Software work is active and hardware work is paused. A trained four-feature local occupancy proxy, observation/model/replay APIs, exact 64-mask allocator, restoration gate and responsive command center are now integrated. The software freezes the existing six-service 14-kW catalog; the historical nine-load catalog remains deferred. No paid keys are required.

The selected logistic pipeline beat Random Forest on validation; the tested CPU TabICL configuration was too slow for live inference. Later-day exploratory performance is much weaker than validation; do not claim real campus accuracy or untouched test results. Full measurements and data attribution are in `backend/models/MODEL_REPORT.md` and `evaluation.json`.

Hardware is not integrated: A/B serial/radio contracts differ, physical ACK fields stay null and the link stays NOT_CONNECTED. No device flashing or fresh physical testing occurred during this software delivery.

## Scope and authority

- Remote current application plan: [remaining plan v2.0](PRIORITYGRID_HACKATHON_REMAINING_PLAN.md) and [blueprint](PRIORITYGRID_FINAL_IMPLEMENTATION_BLUEPRINT.md).
- [Required ML plan](LAB_ACTIVITY_ML_PLAN.md) preserves the user's explicit trained-classifier requirement. Its nine-load catalog differs from the web app's six-load catalog; resolve this explicitly, keeping all values labeled by configuration.
- Physical first milestone: two ESP32s, one RFID reader, three cards, three classroom LEDs and four buttons. Full two-person plan is local-only in `/home/bread/blackout-mesh-local/`. Phase 0 stays complete.
- Simulated power; real radio/LEDs only after verified. No real occupancy accuracy, power delivery, savings or multi-hop mesh claim.
- Approximately 24-hour hackathon and ₹1,500 ceiling; no Arduino/displays. Unknown 12 V/amp/motor modules stay outside baseline.
- Reuse recommendations unchanged and local-only; keep keys, UIDs, device backups and raw local logs out of Git. Graphify/Security Auditor are explicit on-demand only.

## Next action

Rehearse the software demo, gather independently labeled local room observations, and evaluate on new sessions before making accuracy claims. Use `/classrooms`: reset, scan CR1, then overload (3,400 W). CR1 retains 2,000 W; CR2 and CR3 each retain 700 W essential computers/lighting. This separate 8,000-W classroom catalog does not change the six-service campus catalog. Use `/hospital` for overload, cooling failure, upstream loss and missing-sensor scenarios. Diagnosis reads sensor values, uses transparent demonstration thresholds and is not a trained transformer model. Use `/demo` for original shortage and feeder-fault controls; inspect the API at port 8000 `/docs`. Train only when updating evidence/model, not on every start. Detailed current checks are in PROGRESS_REPORT.md.

When hardware resumes, agree one A/B transport and physical mapping before linking the backend. Phase 0 remains complete; physical detailed plans stay local under `/home/bread/blackout-mesh-local/`.

Issue #25 foundation: indexed SQLModel/SQLite ordered history, deduplication and explicit pruning added. Check: PYTHONPATH=backend python -m pytest backend/tests/test_history.py -q � 3 passed. Next: attach recording and read-only API; no history UI delivered yet.
