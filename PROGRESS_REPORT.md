# Blackout Mesh — status

Updated 2026-10-10 against `main` after #46–#48. Older per-issue notes live in git history.

## What works today

| Area | Delivered | Evidence |
|---|---|---|
| One site model | Campus source → feeder A (hospital, 6 kW) and feeder B (classrooms, 8 kW). Hospital and classroom equipment are the leaves of the six campus services; startup fails if they disagree. One event updates every view in the same revision. | `backend/app/core/site.py`, `docs/CATALOG_MIGRATION.md`, `backend/tests/test_site.py` |
| Allocation | Exact search over all 64 plans. Critical circuits and classroom essentials first; occupancy only reorders optional loads; rank dwell stops single-reading flips. Staged restoration. Every load has a reason and counterfactual. | `docs/ALLOCATION_POLICIES.md`, `backend/benchmarks/results/allocation_report.md` (385 runs, 0 constraint violations) |
| Occupancy model | Logistic regression on temperature, humidity, CO₂ and humidity ratio (UCI office data as a proxy). Uncertain readings become UNKNOWN; INACTIVE needs two readings. | `backend/models/MODEL_REPORT.md`, `backend/benchmarks/occupancy/REPORT.md` |
| Demand forecast | Ridge model, 60-second horizon, trained on synthetic sessions. Warns only; never switches loads. | `docs/DEMO_GUIDE.md#predictive-demand` |
| Diagnosis | Ranked, simultaneous hypotheses from telemetry only. Abstains on missing, contradictory or frozen sensors. Persistent fault injection on the hospital view. | `backend/benchmarks/diagnosis/results/` (held-out opened twice; both logged) |
| History | SQLite record of commands, decisions, transitions, incidents and ACKs; read-only playback. | `docs/HISTORY_CONTRACT.md` |
| Hardware link | Board A (RFID + buttons) and board B (LEDs) share contract v2; the backend bridge is tested against contract-following fakes. | `contracts/serial_protocol.md`, `backend/tests/test_gateway.py` |
| Website | City demo, hospital and classroom drill-downs, engineering console. One self-hosted type system (IBM Plex). | `frontend/` |

## Checks

```sh
PYTHONPATH=backend uv run --no-project --python 3.14 \
  --with-requirements backend/requirements-test.txt --with-requirements backend/requirements-ml.txt \
  python -m pytest backend/tests -q          # 195 passed, 2 skipped (optional electrical engine)
cd frontend && npm test && npm run build    # 18 tests pass; build passes
```

CI (`.github/workflows/api-contract.yml`) runs the backend suite, generated-type sync, frontend build, unit tests and a Playwright browser test on every push.

## Honest limits

- Power, demand and faults are simulated. LEDs stand in for contactors; nothing switches real loads.
- Occupancy accuracy drops on later days of the office dataset. No campus-room labels exist yet.
- In the benchmark's steady shortage, even perfect occupancy adds under one point of service; ML helps more in repeated outages (94.9% vs 91.0%).
- Exact search is exponential: 1.6 ms at 6 services, about 12 s at 19.
- Physical acceptance with both boards has not been recorded.

## Next work

See [docs/ROADMAP.md](docs/ROADMAP.md).
