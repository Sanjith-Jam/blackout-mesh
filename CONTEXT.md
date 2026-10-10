# Handoff

Short working notes for whoever picks the project up next. Current status and evidence: [PROGRESS_REPORT.md](PROGRESS_REPORT.md). Planned work: [docs/ROADMAP.md](docs/ROADMAP.md).

## Ground rules that keep the demo honest

- The six-service, 14 kW catalog is the single source of truth. Hospital and classroom equipment are its leaves; change `backend/sites/default_campus.json` and the leaf tables together, or startup fails.
- Diagnosis and allocation read observations only, never scenario names. Fault scenarios live in `backend/app/simulation/sensors.py`.
- Benchmarks: the diagnosis held-out split has been opened (see `backend/benchmarks/diagnosis/data/UNSEALED.log`); treat it as development data from now on and generate a new held-out set before the next final evaluation.
- Schema changes update Python models, `openapi.json`, `frontend/src/schema.d.ts` and fixtures in one commit (`npm run generate-client`, `backend/scripts/export_frontend_fixtures.py`).
- UI typography uses the tokens in `frontend/src/App.css` (`--font-sans`, `--font-mono`, `--step-*`). Do not add page-local font sizes.

## Last session (2026-10-10)

- Re-ran the full audit, added `docs/ROADMAP.md` with the remaining work as implementation items.
- Bundled IBM Plex fonts, unified the type scale, rewrote landing copy and status labels, removed dead pages.
- Removed historical planning, delivery and handoff markdown; rewrote this file, the status report and the README.
- Checks: backend 195 passed / 2 skipped; frontend 18 tests, build passes.

## Next step

Pick the top item in `docs/ROADMAP.md`. Hardware (B5) still needs a person with both boards.
