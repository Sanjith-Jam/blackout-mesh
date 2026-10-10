# Allocation policies and replay — issue #6

`PUT /api/v1/allocation/policy` accepts a strict JSON object, for example:

```json
{"name":"water_first","version":"allocation-v1","fairness_weight":1,"switching_penalty":1}
```

GET on the same URL reads the current policy without advancing control. Unknown fields/names, booleans in integer fields and out-of-range weights are rejected. Changes pass through SiteAuthority, increment control revision, publish an event and restart the restoration stability window.

The objective is explicitly **lexicographic**, never a weighted trade of critical service against convenience. Immutable T1 circuits come first in catalog order. Soft profiles:

| Profile | Optional preference order |
|---|---|
| activity_first (default) | ACTIVE room count, UNKNOWN room count, water pump, INACTIVE room count |
| water_first | Water pump, ACTIVE room count, UNKNOWN room count, INACTIVE room count |

After these terms, bounded waiting-age credit (up to 3,600 seconds per requested unserved optional load), switching penalty, served watts and lowest numeric mask break ties. Weights range 0–100. Fairness is within equal higher-order objectives; it cannot override critical or evidence tiers. It provides no cross-tier starvation guarantee. UNKNOWN remains above INACTIVE under either profile. Hard source/feeder capacity and open-path constraints are never editable through this API. Classifier labels never remove demand. Infeasible protected minima are explicitly reported as shortfall.

The switching penalty sits after the evidence tiers, so it cannot stop a single wrong classifier reading from reordering rooms. `RankDwell` (`app/core/safety.py`, `RANK_DWELL_READINGS = 3`) therefore holds each room's ranking state until a changed state repeats on three consecutive readings; readings with no valid evidence fall back to UNKNOWN at once. It applies to the campus and classroom views and to the benchmark's `proposed` policies. Measured effect and its remaining cost are in `backend/benchmarks/results/allocation_report.md` (ablation summary).

Protective shedding remains immediate. Additions still wait for five seconds of stable supply/policy, three seconds since shedding, and one second between restored services. Applied state and hardware acknowledgement stay distinct. The policy governs the six campus services; classroom appliance and hospital zone projections retain their own protected-leaf safeguards described in CATALOG_MIGRATION.md. Do not interpret this as a new unified 19-leaf dispatch engine.

Each campus snapshot's `allocation.explanation` contains policy/version, objective order, winning score terms, decision hash, control revision, complete optimization inputs and requested/proposed/applied outcomes for every service. Force-on counterfactuals identify source, feeder or request constraints; physically feasible losers cite lexicographic preference. Staged additions cite the restoration gate. `restoration_replay` records gate state before the step, signature, deterministic order and exact monotonic timestamp; recreate a RestorationGate with these fields and call update to reproduce applied state. The decision hash identifies optimization inputs and masks; gate metadata provides the additional application trace. Site run/revision appears on the surrounding snapshot. Reads are still read-only. These are in-memory traces; durable decision persistence is issue #12.

## Profiling decision

`PYTHONPATH=backend .venv-ml/bin/python backend/scripts/profile_allocation.py`

See `backend/benchmarks/results/allocation_profile.json`. On this host, 50 six-service runs had median **1.59 ms**, maximum **2.17 ms**. Three experimental 19-leaf enumerations examined **524,288 masks** each, median **11.95 s**, maximum **17.59 s**. They decompose the current services without double-counting, but are only a scale probe, not an adopted leaf safety policy. Small samples do not establish a tail guarantee.

Keep the exact 64-mask oracle in the shipped 250-ms control loop. Never put the 19-leaf enumeration there. If a future catalog needs leaf dispatch, this evidence warrants a bounded solver (e.g. OR-Tools), timeout-safe previous feasible/protective fallback and safety-equivalence tests before adoption. Adding an unused solver dependency to today's six-service runtime would not improve its outcome.
