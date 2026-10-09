# Issue #25 delivery — 2026-10-10

Implemented server-backed campus history and read-only recorded-decision playback.
The original theme remains. No push or issue closure was performed.

## Delivered
- Indexed SQLModel/SQLite records scoped to campus/run, stable IDs/revisions,
  UTC timestamps, inclusive time filters and exclusive sequence pagination.
- Independent 1-Hz telemetry; decisions only on meaningful state changes.
- Captured configured inputs, observation provenance, catalog, model hash and
  thresholds, policy, applied snapshot and linked event IDs. ACK/command identity
  remain null. Restart creates a new run while preserving old records.
- Raw 30-day retention, startup/hourly pruning and expired-cursor warning.
- TanStack Query pagination, cancellation, incremental tail queries, ID dedup,
  socket event merging and gap backfill; run/range/playback position survive reload.
- Explicit LIVE/HISTORY selector, previous/next/play/pause, evidence details.
  HISTORY closes its live socket and disables all dashboard mutation controls.
  Playback never invokes POST /api/v1/replay or recomputes the live controller.

## Checks (PowerShell, repository root)
Set PYTHONPATH=backend and PRIORITYGRID_HISTORY_DB to a temporary sqlite3 path.
- python -m pytest backend/tests/test_history.py -q: 5 passed.
- python -m pytest backend/tests/test_history.py backend/tests/test_api.py
  backend/tests/test_ml_integration.py backend/tests/test_activity_model.py -q:
  25 passed before the final fixture test was added; all these tests also pass
  in the final full-suite run.
- python -m pytest backend/tests -q --tb=short: 35 passed, 2 failed.
  Failures are in unchanged upstream hospital tests/code:
  test_hospital_diagnosis_uses_sensor_values_only expects the removed scenario API;
  test_hospital_faults_are_local_except_upstream_loss hits undefined HOSPITAL_LOADS.
  These were not hidden, skipped or repaired as part of #25.
- npm.cmd run test:history --prefix frontend: 4 passed (ordered IDs, pagination/
  backfill/reload, read-only playback, obsolete-request cancellation).
- npm.cmd run build --prefix frontend: passed; existing >500-kB bundle warning.

Windows prerequisites fixed separately: optional Unix resource import for metrics,
and HospitalDemo's missing stylesheet import. The test-runner experiment was
removed; tests use Node's built-in runner, jsdom and the existing esbuild toolchain.
No firmware, radios, private enrollment files or power hardware were changed.

## Installed/tested versions
Python 3.14; Node 26.3.1; SQLModel 0.0.48; SQLAlchemy 2.1.4;
pytest 9.1.1; httpx 0.28.1; TanStack React Query 5.104.1;
jsdom 30.1.2; Vite 5.4.21; TypeScript 5.9.3.
Frontend lockfile records exact artifacts. Tests need a jsdom-supported Node
version (22.22.2+, 24.15.0+, or 26+).
npm audit after removing the experimental runner retains the existing Vite/esbuild
advisories (1 moderate, 1 high); no broad dependency upgrade was attempted.

## Remaining gates — do not close #25 yet
- #12: replace the current public-event/snapshot recorder with the coordinated,
  crash-atomic incident/input/decision journal. Events accepted between sampling
  ticks are captured as inputs but their intermediate decisions are not guaranteed.
- #13: integrate authoritative server publication sequence/reset identity.
  This delivery guards frontend reconnect cleanup and backfills history, but
  does not claim the complete transport lifecycle implementation.
- #14: history/event TS interfaces are manually synchronized with this contract;
  upstream OpenAPI generation still needs integration.
- Hardware command/ACK association cannot be verified while transport is paused.
  The trail shows unknown; no fake command identity or ACK is generated.
- Playback is deterministic display of recorded outputs and evidence, not causal
  re-execution of historical models or what-if simulation. No fork endpoint exists.
- Separate hospital/classroom visualizers are not merged into campus history.
- Browser/device E2E, stress testing, crash recovery and transactional migration
  acceptance remain unverified. The targeted DOM tests and build are not those tests.

See HISTORY_CONTRACT.md for API and retention details. Restart backend and frontend,
open /demo, cause a campus capacity change in LIVE, then select HISTORY and replay.
Only records created after this delivery can be recovered.

