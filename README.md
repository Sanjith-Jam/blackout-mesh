# Blackout Mesh

![City outage and recovery demo](docs/media/city-demo.gif)

**When the power runs short, decide what stays on, and explain why.**

Blackout Mesh is an offline demo of a small campus grid: a hospital on one feeder, three classrooms on the other. When supply drops it checks all 64 possible plans, always keeps critical hospital circuits and classroom essentials on, ranks everything else by observed room use, and gives every cut a one-sentence reason. Fault diagnosis ranks likely causes and says "I don't know" when sensors disagree or freeze.

| Real | Simulated |
|---|---|
| Allocation, diagnosis and forecasting code; a trained occupancy model; recorded history; the ESP32 card reader, buttons and LEDs when connected | Electrical power, demand, faults and switching. LEDs stand in for contactors. |

## Try it

You need [uv](https://docs.astral.sh/uv/) and Node 22.

```sh
# terminal 1, repository root
uv run --no-project --python 3.14 --with-requirements backend/requirements.txt \
  --with-requirements backend/requirements-ml.txt \
  python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# terminal 2
cd frontend && npm ci && npm run dev
```

Open <http://127.0.0.1:5173/demo>, then: **Request all rooms → 6 kW shortage → Trip feeder A → Restore supply.** No API key or internet connection is needed.

## What the numbers say

Measured locally: 0.17 ms per occupancy prediction, 1.59 ms per allocation decision, 0 constraint violations in 385 simulated runs.

In a 6 kW shortage, essentials-first allocation serves occupied rooms 84.9% of the time versus 61.8% for a fixed priority list. Adding occupancy evidence reaches 85.2%, close to the 85.8% a perfect-knowledge oracle gets. In this setup the protection and explanation do most of the work; occupancy helps most when outages repeat (94.9% vs 91.0%). [Full results](backend/benchmarks/results/allocation_report.md).

## Learn more

- [Demo guide](docs/DEMO_GUIDE.md): the walkthrough, what each view shows, and how to verify it.
- [Status](PROGRESS_REPORT.md) and [roadmap](docs/ROADMAP.md).
- [All documentation](docs/README.md): design notes, model and benchmark reports, hardware guides.

Not for real electrical control or life-safety use.
