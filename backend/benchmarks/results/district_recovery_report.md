# District recovery benchmark

Synthetic radial 400 V graphs only. This compares methods on identical modeled inputs; it is not field evidence, not a real-grid safety result and not a savings claim.

Protocol `district-recovery-v1` frozen before measurement; 120 scenarios, seeds 7100+i; engine power-grid-model 1.13.193.

| Method | n | Critical unmet Wh | Total unmet Wh | Mean switches | Proposed invalid | Accepted invalid | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| no_reconfiguration | 120 | 683,118 | 4,012,029 | 0.0 | 0 | 0 | 5.478 | 6.319 |
| first_benefit | 120 | 592,463 | 3,641,658 | 0.3 | 22 | 0 | 5.82 | 6.83 |
| critical_first_greedy | 120 | 609,109 | 3,744,003 | 0.283 | 28 | 0 | 5.916 | 7.054 |
| optimized | 120 | 582,582 | 3,581,444 | 0.358 | 0 | 0 | 11.326 | 25.136 |

Paired differences (baseline minus optimized; positive means the optimizer left less unmet energy), bootstrap 95% intervals:

| Comparison | Critical Wh mean [CI] | Total Wh mean [CI] | Better / tied / worse (critical) |
|---|---|---|---|
| no_reconfiguration_minus_optimized | 837.8 [379.2, 1420.5] | 3,588.2 [2247.8, 5185.2] | 15 / 105 / 0 |
| first_benefit_minus_optimized | 82.3 [0.0, 240.9] | 501.8 [70.0, 1079.7] | 2 / 118 / 0 |
| critical_first_greedy_minus_optimized | 221.1 [0.0, 641.0] | 1,354.7 [287.9, 2784.2] | 2 / 118 / 0 |

Not covered: PV/storage limits, incomplete sensors, multi-interval trajectories, protection, inrush and transients. Latency is single-process host time and includes AC gating.

Reproduce: `PYTHONPATH=backend python -m benchmarks.run_district_recovery` from the repository root.
