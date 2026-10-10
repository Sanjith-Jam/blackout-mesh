# Issue #15 delivery: cleanup and dependency drift

Baseline: `origin/main` at `37f3188` (2026-10-10). Cleanup only; no behaviour changes.

## Inventory

Every tracked script, module and placeholder outside `frontend/src`, `backend/tests` and `docs/` was checked for callers with `rg` (module name across the repository, excluding the file itself).

| Path | Class | Evidence |
| --- | --- | --- |
| `backend/allocator_check.py` | already gone | Not in the tree at the baseline. |
| `frontend/tsconfig.tsbuildinfo` | generated, already untracked | Not tracked; `*.tsbuildinfo` is in `.gitignore`. |
| `backend/app/core/.gitkeep`, `backend/app/schemas/.gitkeep` | empty scaffold, **removed** | Both directories now hold real modules; nothing references the placeholders. |
| `contracts/examples/.gitkeep` | empty scaffold, **removed** | Directory had no other files and no references; examples live in `contracts/schema_examples/`. |
| `backend/scripts/export_frontend_fixtures.py`, `export_openapi.py`, `train_demand_forecast.py` | maintained | Imported or invoked by `backend/tests` and frontend `check-client`. |
| `backend/scripts/train_activity.py`, `evaluate_temporal.py` | maintained | Reproduction steps in `backend/models/MODEL_REPORT.md`. |
| `backend/scripts/benchmark_electrical.py`, `profile_allocation.py` | maintained, optional study | Documented in `docs/ELECTRICAL_SIMULATION.md` and `docs/ALLOCATION_POLICIES.md`. |
| `backend/benchmarks/diagnosis/run_ranked.py` | maintained | Exercised by `backend/tests/test_diagnosis_benchmark.py`. |
| `firmware/` (board A) and `hardware/firmware/` (board B) | maintained, both kept | Two boards, one contract; `test_hardware_files.py` enforces the shared `protocol.h`. |
| `tools/*.py`, `hardware/tools/check_board_b.py` | maintained | Entry points listed in `AGENTS.md` and `hardware/README.md`. |
| `ESP32_A_STATUS.md` | historical reference, kept | Linked from `CONTEXT.md` as the original board A handoff. |
| `backend/benchmarks/**/UNSEALED.log`, `results/` | intentional evidence, kept | Held-out audit trail and committed benchmark results. |
| `openapi.json` | generated, kept | Checked for drift by `npm run check-client` in CI. |

## Dependencies

- `backend/requirements.txt` and `requirements-test.txt` are now pinned to the versions a clean CPython 3.14.6 install resolved: fastapi 0.143.0, uvicorn 0.54.0, pydantic 2.14.0, websockets 17.2, sqlmodel 0.0.48, pyserial 3.5, pytest 9.1.1, httpx2 2.13.1. No version was raised beyond what the old ranges already installed.
- `httpx2` stays: starlette's `TestClient` imports `httpx2` first and deprecates plain `httpx`. The `--with httpx` hint in `AGENTS.md` was stale and now points at `requirements-test.txt`.
- ML (`requirements-ml.txt`), TabICL benchmark (`requirements-ml-benchmark.txt`) and electrical studies (`requirements-electrical*.txt`) stay separate, unchanged, from the default runtime.
- `.gitignore` already covers SQLite databases, `*.tsbuildinfo`, local card/hardware/secret headers and virtualenvs. Nothing tracked matched those patterns.

## Verification

- Fresh venv, `uv pip install -r backend/requirements-test.txt -r backend/requirements-ml.txt`, then `PYTHONPATH=backend python -m pytest backend/tests -q`: **195 passed, 2 skipped** (electrical engine not installed). `uv pip check`: all compatible.
- `cd frontend && npm ci && npm run build && npm test && npm run test:contract`: build passes (existing large-bundle warning), 18 tests pass, contract check passes.

## Limitations

- The optional electrical and TabICL study environments were not reinstalled here.
- Frontend dependencies are already locked by `package-lock.json`; no frontend changes.
- Firmware was not recompiled (no firmware files touched).
