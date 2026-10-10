# Blackout Mesh

![Software city-grid outage and recovery demo](docs/media/city-demo.gif)

A local, explainable power-allocation demo: forecast requested demand, explore a city grid, trigger an outage, and follow staged recovery. The city drawing uses the existing six-service **14 kW lab model**; it does not claim city-scale electrical physics or multi-hop mesh routing.

**Real software:** a trained occupancy proxy, a synthetic-trained demand forecaster, exact 64-plan allocation, recorded history and an ESP32 USB/ESP-NOW bridge. **Simulated:** city power, demand, faults, switching and recovery. Physical LED confirmation appears only when the connected gateway reports a fresh acknowledgment. Physical end-to-end acceptance remains pending; B5 flashing/pairing/video is on hold.

Recorded local medians: **0.17 ms** occupancy inference (100 warm calls), **1.59 ms** allocation (50 decisions), **0 constraint violations / 280 simulated runs**. These are different tasks, not a competing-controller speed comparison. [Measurement sources](docs/DEMO_GUIDE.md#evidence).

The 60-second demand forecast averaged **149.49 W error** versus **469.59 W** for last-value persistence on 20 held-out **synthetic** sessions. It warns about capacity risk and cannot authorize switching. Neither model establishes campus accuracy.

## Same shortage, simpler controllers

6 kW shortage · five seeds per policy · 40 simulated minutes per run. Switching counts are means.

| Policy | Occupied service | Switches | Essential unmet Wh | Critical unmet Wh |
|---|---:|---:|---:|---:|
| Fixed priority | 61.8% | 6.2 | 380.9 | 0.0 |
| Essentials-first, no ML | 84.9% | 6.6 | 205.1 | 0.0 |
| ML with simulated validation-rate errors | 85.4% | 20.6 | 220.3 | 0.0 |
| Always UNKNOWN | 84.9% | 6.6 | 205.1 | 0.0 |
| Oracle (offline only) | 85.8% | 7.8 | 219.9 | 0.0 |

The small occupied-service gain comes with more switches and unmet essential demand. ML is optional; rank-dwell evaluation from A1 is still pending. [Full results](backend/benchmarks/results/allocation_report.md).

## Run locally

From the repository root:

```sh
uv run --no-project --python 3.14 --with-requirements backend/requirements.txt --with-requirements backend/requirements-ml.txt python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm ci --no-audit --no-fund
npm run dev
```

Open [the city demo](http://127.0.0.1:5173/demo). Request all rooms → 6 kW shortage → trip feeder A → repair it → restore supply. Select the synthetic rising-demand rehearsal to see a forecast warning. No API key, training step or paid service is required.

[Demo guide and checks](docs/DEMO_GUIDE.md) · [Planning](docs/planning/README.md) · [Model evidence](backend/models/MODEL_REPORT.md) · [Progress](PROGRESS_REPORT.md) · [Context](CONTEXT.md) · [Hardware guide](docs/ESP32_A_CONNECTION_GUIDE.md)
