# Issue #14 delivery — generated API contract

**Status:** implemented on `codex/remaining-open-issues`; not merged yet.

FastAPI now publishes concrete request and response models for classroom and hospital visualizers, hardware status, allocation policy, history, health and the existing campus/electrical routes. The exported schema includes a version marker, method/path-derived operation IDs, a common error response, and the named WebSocket snapshot envelope. `frontend/src/schema.d.ts` is generated from `openapi.json`; frontend wire aliases now reference generated models. Visualizer view types retain only the narrow live-state guarantees used by their screens.

Incoming WebSocket data is checked at runtime for envelope type, timestamps, run identity, revisions, source capacity, and service shape before entering the shared query cache. Focused Node assertions reject malformed examples. A CI workflow regenerates the contract, checks both generated files for drift, builds the UI, and runs the envelope checks.

Verification on 2026-10-10:

- `PYTHONPATH=backend .venv-ml/bin/python -m pytest backend/tests -q --tb=short` — **153 passed**.
- `npm run build` — passed; existing large-bundle warning remains.
- `npm run test:contract` — passed.
- Two independent OpenAPI exports compare equal; every HTTP operation has a JSON success schema and documented default error schema; required request bodies and the WebSocket envelope are checked by `backend/tests/test_openapi_contract.py`.
- `git diff --check` — passed.

The pre-existing `npm run test:history` still cannot start in this checkout because `jsdom` is missing from `frontend/node_modules`; it is declared in the package manifest and the new CI workflow installs from the lockfile. No browser-to-backend rehearsal or physical hardware test was performed. TypeScript generation provides compile-time API types; only WebSocket input gets client-side runtime validation.
