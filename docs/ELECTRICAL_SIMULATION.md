# Electrical simulation boundary — issue #7

The campus/classroom/hospital controller remains a **watt-budget decision demo**. Campus snapshots explicitly publish `source.model="watt_budget"` and `source.limitations`. Its integer capacity checks, scenario sensor fixtures and five-second restoration timer are not AC power flow, relay protection, dynamic stability or validated restoration physics. No electrical-study result controls the demo or physical hardware.

An optional `POST /api/v1/studies/electrical` exposes a separate balanced AC study. It returns topology version, engine/version, input copy, units, timestamp, convergence/failure status, source P/Q, losses, line-to-line bus RMS voltage, branch RMS current/P/Q/loading and simulated provenance. Deenergized/islanded or failed quantities are null; the energized flag and solve status distinguish disconnected topology from numeric failure. Missing observations stay missing at diagnosis. **restoration_authorized is always false**, even for converged results. A converged overload means the equations converged, not that the operating point is safe.

Enable the optional engine in the existing ML backend environment (verified here with Python 3.14.7, numpy 2.5.3, sklearn 1.9.1):

```sh
uv pip install --python .venv-ml/bin/python -r backend/requirements-electrical.txt
PYTHONPATH=backend .venv-ml/bin/python -m uvicorn app.main:app --port 8000
```

This adds PGM and NetworkX to the same backend; it creates no second simulation authority. The separate Python 3.12 environment below is only for offline cross-engine benchmarks. If optional dependencies are absent, the study returns unavailable/null observations while the normal watt-budget demo and ML continue running.

Example study input:

```json
{"topology_version":"radial-400v-v1","load_a_w":6000,"load_b_w":8000,"source_on":true,"feeder_a_closed":true,"feeder_b_closed":true,"balanced":true,"power_factor":0.95,"resistance_ohm":0.04,"reactance_ohm":0.015}
```

Strict validation rejects negative/zero resistance, negative reactance, non-finite inputs, unbalanced mode, invalid IDs/versions, strings/booleans masquerading as watts and unknown fields. Source on/off, branch switches and constant-P/Q demand are inputs; generation is a single ideal upstream slack, without PV/storage dispatch. NetworkX determines reachability/islands only. Power Grid Model solves the AC equations. pandapower is an offline cross-check and is not imported by the runtime study path.

Studies execute on a worker thread, serialized independently of the 250-ms controller. A busy request returns 503; a five-second timeout returns 504 without freeing the slot until the actual worker finishes. Output is rejected with 409 if site run/revision changed during computation. No result mutates allocation, issues indicator commands or permits restoration. Native solver iterations are bounded; a timed-out native thread cannot be forcibly killed. For a public/high-volume deployment, isolate studies in a process with resource limits; this local single-worker demo rejects concurrent work.

## Reference network and assumptions

A synthetic 400-V line-to-line, 50-Hz, balanced three-phase source feeds two radial lines A/B and constant-power loads. Each complete line has positive-sequence **R=0.04 Ω, X=0.015 Ω**, zero shunt capacitance, ampacity **A=10 A / B=14 A**, and lagging PF **0.95** (configurable 0.8–1). Nominal loads A=6,000 W and B=8,000 W are total three-phase values. pandapower uses a one-km equivalent line carrying these total impedances, MW/Mvar/kA internally; the adapter converts to SI. PGM uses SI and a near-ideal source with short-circuit strength 1e20 VA to match pandapower's ideal slack.

These values are **declared synthetic engineering assumptions**, not surveyed campus cable or transformer specifications. The source represents an upstream transformer secondary; no transformer winding, rating, vector group, grounding/neutral path, zero-sequence network, harmonics, inrush, asymmetric phase loading, cooling or thermal dynamics is modeled. Grounding does not enter this positive-sequence balanced study. Consequently it cannot infer earth faults, transformer temperature or equipment remaining life. Adding those claims requires actual parameters and a suitable model.

Normal operation checks P independently: source power = energized constant-power loads + sum(3 I² R) line losses, within 0.1 W. `power_balance_residual_w` exposes this residual; larger residuals fail the study. Overload doubles both demands and exceeds the declared branch ampacities. Opening B isolates its load and removes it from supplied demand, with no invented flow. Upstream loss leaves no energized source and produces no AC observations. A high-impedance/high-demand case tests nonconvergence, returning null measurements and diagnostic abstention.

Solver results become the existing validated observation envelopes in `telemetry()`. `diagnose_study()` receives only those observations and declared voltage/current ratings: no scenario labels, switch truth or capacity oracle. Single-study current exceedance is an observation alarm, not a confirmed root cause. Islanded/missing readings lead to abstention; the topology explanation can report disconnection separately. No thermal observations are fabricated.

## Measured comparison

CPython **3.12.15**, power-grid-model **1.13.193**, pandapower **3.5.6**, NetworkX **3.7** installed successfully together on this Linux host. Reproduce:

```sh
uv venv --python 3.12 .venv-electrical
uv pip install --python .venv-electrical/bin/python -r backend/requirements-electrical-benchmark.txt -r backend/requirements.txt
PYTHONPATH=backend .venv-electrical/bin/python backend/scripts/benchmark_electrical.py
```

Full machine-readable output: `backend/benchmarks/results/electrical_report.json`. Normal, overload and open-branch solutions agreed within **0.01 V, 0.001 A and 0.1 W**. Both reject the high-impedance/high-demand case. The source-off case is screened by reachability, so it is not reported as numerical convergence.

| End-to-end latency | Power Grid Model | pandapower |
|---|---:|---:|
| First import/build/solve | 433 ms | 2,434 ms |
| Warm single p50 / p95 (20 trials) | 3.08 / 3.23 ms | 241 / 310 ms |
| Serial batch of 16 p50 / p95 (5 trials) | 51.7 / 57.2 ms | 1,446 / 1,448 ms |

Batch here means serial adapter calls including graph/build/validation, not native vectorized throughput. Five batch trials are a smoke profile, not a reliable production tail estimate. Timing varied with import/warm-up and host load. Select **Power Grid Model** for the optional runtime based on matched accuracy and measured latency; keep pandapower offline. Installation is optional, and absence returns explicit unavailable/null output without inventing numbers.

API conventions were checked against the primary [PGM power-flow example](https://power-grid-model.readthedocs.io/en/stable/examples/Power%20Flow%20Example.html), [pandapower line documentation](https://pandapower.readthedocs.io/en/latest/elements/line.html) and [pandapower quick start](https://www.pandapower.org/start/). No repository code was copied.

Verified installed package metadata: Power Grid Model is MPL-2.0, NetworkX BSD-3-Clause, and pandapower declares the BSD license classifier. These libraries are dependencies, not copied repository implementations; keep their licenses with any redistributed environment.
