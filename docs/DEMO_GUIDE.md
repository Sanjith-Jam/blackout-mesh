# Blackout Mesh demo guide

## The software story

Use `/demo` for the city story. All source, feeder A/hospital and feeder B/classroom panels come from one backend snapshot and carry the same revision. The illustrative city retains the six-service 14 kW model. It is not a city-scale power-flow study.

1. **Request all rooms.** This creates observed session requests for CR1/CR2/CR3. It does not assign priority directly.
2. **6 kW shortage.** Protective shedding is immediate. Each requested shed load gets its sentence from `allocation.explanation.decisions[].reason`; inspect More for additional detail.
3. **Select a building.** See its current modeled decision. Commanded, simulated and physical ACKed states remain separate.
4. **Trip feeder A.** Its hospital services lose supply, and the navigator reports the critical shortfall. Zero supply/open feeders can leave critical demand unmet; there is no absolute “never cut” claim.
5. **Repair feeder A**, then **Restore supply**. The existing controller waits for stable evidence/dwell and restores in stages. The guide does not bypass it.
6. Use `/hospital` and `/classrooms` for equipment drawings, or `/console` for history/playback and engineering controls.

The hospital equipment drill-down now shares feeder A’s 6 kW campus catalog and follows its served capacity. Its backend supports persistent simulated fault injection; the separate rehearsal buttons use isolated 100 A teaching fixtures and leave live allocation unchanged.

## Predictive demand

The trained Ridge forecaster uses four past requested-watt observations, sampled every 10 seconds, and predicts six future demand points through 60 seconds. It never uses post-shedding served power, scenario labels, future observations, RFID UIDs or allocation masks as features. The occupancy classifier remains separate and unchanged.

Live mode needs at least 30 seconds of observations. Missing/stale data, gaps and abrupt changes become UNKNOWN; no zero is substituted. A new run clears the history. Forecasts are advisory and cannot change allocation or authorize restoration.

Choose **Synthetic rising-demand rehearsal** to demonstrate immediately. The initial 3-step history is 3,900 → 4,100 → 4,400 → 4,750 W. The +60 s forecast is 6,540 W, with an empirical synthetic error band of 6,242–6,838 W. Against the 6,000 W shortage limit the band warns of possible shortfall within 40 seconds. Next sample advances the rehearsal by 10 simulated seconds. These samples never enter the live grid's observation history.

Training uses 120 reproducible synthetic sessions: 80 train, 20 calibration, 20 held-out test, with complete-session separation. The 60-second MAE is 149.49 W versus 469.59 W persistence on 1,420 test windows from 20 sessions. Synthetic error-band coverage at 60 seconds is 88.31%; it is not field-calibrated confidence. Abrupt new loads and trips cannot be reliably predicted from this smooth-demand training distribution.

Reproduce training with the project's installed ML environment:

```sh
PYTHONPATH=backend .venv-ml/bin/python backend/scripts/train_demand_forecast.py
```

The model coefficients need only the standard library at inference. The script uses the existing sklearn dependency. See [forecast report](../backend/models/DEMAND_FORECAST_REPORT.json) and [artifact](../backend/models/demand-forecast.json).

## Diagnostic examples

The hospital drill-down offers overload, cooling failure, combined overload/cooling, upstream loss, dropout, stuck-sensor and clear examples. These are explicitly separate 100 A transformer fixtures, diagnosed from timestamped readings. Buttons do not inject persistent faults into the city.

The cards show ordered hypotheses, evidence, uncalibrated heuristic scores and the next inspection step. The stuck-current fixture supplies three identical current readings while temperature rises; it returns ABSTAINED and displays sensor evidence as untrusted. Normal cards for other transformers do not clear the affected asset's abstention.

## Hardware

The monitoring panel shows gateway-reported board/reader/radio status, command mask, ACK mask and recent inputs. Disconnected, stale and unconfirmed LED states stay unknown. No physical reading or latency is fabricated. B5 remains on hold: no flashing, enrollment, pairing, physical acceptance or hardware video was performed in this delivery.

When authorized to resume B5, follow [the connection and acceptance guide](ESP32_A_CONNECTION_GUIDE.md). Private card/provisioning files stay ignored. USB-powered low-voltage LEDs only; no mains or relays.

## Evidence

- Occupancy inference: [evaluation JSON](../backend/models/evaluation.json), `runtime_inference.warm_single_prediction_ms`, median 0.171876 ms over 100 warm calls.
- Six-service exact allocation: [profile JSON](../backend/benchmarks/results/allocation_profile.json), median 1.594748 ms over 50 decisions/64 masks. The offline 19-leaf result does not establish live scalability.
- Allocation safety/outcomes: [report JSON](../backend/benchmarks/results/allocation_report.json) and [full table](../backend/benchmarks/results/allocation_report.md), 385 simulated runs and zero constraint violations. This is not a field safety guarantee.
- The live comparison shows fixed-priority and exact-policy candidate masks over the same revision and inputs. The currently applied mask is separate so restoration dwell does not unfairly penalize one candidate.
- The current ML/no-ML benchmark includes switching and essential/critical unmet Wh. The rank-dwell ablation is included; no ML superiority is assumed.
- The README GIF records the browser against an isolated real backend. It is software evidence, not B5's physical backup video.

## Verification

Use a temporary history database; do not modify or commit local production evidence.

```sh
PYTHONPATH=backend .venv-ml/bin/python -m pytest backend/tests -q
cd frontend
npm test
npm run build
npm run test:history
npm run test:contract
```

`npm run test:e2e` starts an isolated backend on 8183 and frontend on 5183. Put a Python environment with project requirements on PATH (for this workspace: `PATH="$PWD/.venv-ml/bin:$PATH" npm run test:e2e --prefix frontend` from the repository root). The city test forwards browser API requests to that isolated backend and uses temporary SQLite history. CI installs the project requirements before the browser checks. No production database or hardware is involved.
