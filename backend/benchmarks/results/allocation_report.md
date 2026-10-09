# Allocation benchmark (alloc-bench-2026-10-10.1)

Commit `9766975` · safety policy `safety-2026-10-10.1` · 5 seeds per scenario · 2400 s per run at 5 s steps. Simulated outcomes only: watt-hours integrate modeled power over simulated time and are not measured savings.

Reproduce: `PYTHONPATH=backend python -m benchmarks.run_allocation` from the repository root.

Policies: `fixed_priority` (L0→L5), `essentials_first_no_ml` (critical, booked rooms, pump), `round_robin` (critical, then least-recently-served optional), `proposed[...]` (classifier → ActivityGuard → exact allocator) with each classifier variant and an always-UNKNOWN no-ML ablation, and `oracle_occupancy_upper_bound`, which reads true occupancy and is **not deployable**.

Every run of a scenario/seed has the same input digest (capacity, feeders, bookings, classifier outputs); true occupancy is used only by the evaluator.

## shortage_6kw

| Policy | Critical unmet Wh | Essential unmet Wh | Occupied service | Worst starvation s | Switches | Recovery s (max) | Violations |
|---|---:|---:|---:|---:|---:|---:|---:|
| essentials_first_no_ml | 0.0 | 205.1 | 84.9% | 541 | 6.6 | 10 | 0 |
| fixed_priority | 0.0 | 380.9 | 61.8% | 815 | 6.2 | 10 | 0 |
| oracle_occupancy_upper_bound | 0.0 | 219.9 | 85.8% | 525 | 7.8 | 10 | 0 |
| proposed[heavy_errors] | 0.0 | 237.6 | 81.3% | 481 | 59.0 | 10 | 0 |
| proposed[no_ml_unknown] | 0.0 | 205.1 | 84.9% | 541 | 6.6 | 10 | 0 |
| proposed[perfect] | 0.0 | 219.9 | 85.8% | 525 | 7.8 | 10 | 0 |
| proposed[validation_rates] | 0.0 | 220.3 | 85.4% | 526 | 20.6 | 11 | 0 |
| round_robin | 0.0 | 348.8 | 66.3% | 530 | 186.2 | 15 | 0 |

## deep_shortage_4kw

| Policy | Critical unmet Wh | Essential unmet Wh | Occupied service | Worst starvation s | Switches | Recovery s (max) | Violations |
|---|---:|---:|---:|---:|---:|---:|---:|
| essentials_first_no_ml | 0.0 | 346.3 | 65.1% | 700 | 8.2 | 13 | 0 |
| fixed_priority | 0.0 | 346.3 | 65.1% | 700 | 8.2 | 13 | 0 |
| oracle_occupancy_upper_bound | 0.0 | 346.3 | 65.1% | 700 | 8.2 | 13 | 0 |
| proposed[heavy_errors] | 0.0 | 346.3 | 65.1% | 700 | 8.2 | 13 | 0 |
| proposed[no_ml_unknown] | 0.0 | 346.3 | 65.1% | 700 | 8.2 | 13 | 0 |
| proposed[perfect] | 0.0 | 346.3 | 65.1% | 700 | 8.2 | 13 | 0 |
| proposed[validation_rates] | 0.0 | 346.3 | 65.1% | 700 | 8.2 | 13 | 0 |
| round_robin | 0.0 | 346.3 | 65.1% | 700 | 8.2 | 13 | 0 |

## feeder_b_loss

| Policy | Critical unmet Wh | Essential unmet Wh | Occupied service | Worst starvation s | Switches | Recovery s (max) | Violations |
|---|---:|---:|---:|---:|---:|---:|---:|
| essentials_first_no_ml | 0.0 | 242.7 | 71.5% | 518 | 6.6 | 12 | 0 |
| fixed_priority | 0.0 | 242.7 | 71.5% | 518 | 6.6 | 12 | 0 |
| oracle_occupancy_upper_bound | 0.0 | 242.7 | 71.5% | 518 | 6.6 | 12 | 0 |
| proposed[heavy_errors] | 0.0 | 242.7 | 71.5% | 518 | 6.6 | 12 | 0 |
| proposed[no_ml_unknown] | 0.0 | 242.7 | 71.5% | 518 | 6.6 | 12 | 0 |
| proposed[perfect] | 0.0 | 242.7 | 71.5% | 518 | 6.6 | 12 | 0 |
| proposed[validation_rates] | 0.0 | 242.7 | 71.5% | 518 | 6.6 | 12 | 0 |
| round_robin | 0.0 | 242.7 | 71.5% | 518 | 6.6 | 12 | 0 |

## feeder_a_loss

| Policy | Critical unmet Wh | Essential unmet Wh | Occupied service | Worst starvation s | Switches | Recovery s (max) | Violations |
|---|---:|---:|---:|---:|---:|---:|---:|
| essentials_first_no_ml | 505.6 | 1.0 | 99.8% | 3 | 8.0 | 15 | 0 |
| fixed_priority | 505.6 | 1.0 | 99.8% | 3 | 8.0 | 15 | 0 |
| oracle_occupancy_upper_bound | 505.6 | 1.0 | 99.8% | 3 | 8.0 | 15 | 0 |
| proposed[heavy_errors] | 505.6 | 1.0 | 99.8% | 3 | 8.0 | 15 | 0 |
| proposed[no_ml_unknown] | 505.6 | 1.0 | 99.8% | 3 | 8.0 | 15 | 0 |
| proposed[perfect] | 505.6 | 1.0 | 99.8% | 3 | 8.0 | 15 | 0 |
| proposed[validation_rates] | 505.6 | 1.0 | 99.8% | 3 | 8.0 | 15 | 0 |
| round_robin | 505.6 | 1.0 | 99.8% | 3 | 8.0 | 15 | 0 |

## insufficient_critical_2kw

| Policy | Critical unmet Wh | Essential unmet Wh | Occupied service | Worst starvation s | Switches | Recovery s (max) | Violations |
|---|---:|---:|---:|---:|---:|---:|---:|
| essentials_first_no_ml | 168.1 | 231.8 | 71.9% | 569 | 9.2 | 23 | 0 |
| fixed_priority | 168.1 | 231.8 | 71.9% | 569 | 9.2 | 23 | 0 |
| oracle_occupancy_upper_bound | 168.1 | 231.8 | 71.9% | 569 | 9.2 | 23 | 0 |
| proposed[heavy_errors] | 168.1 | 231.8 | 71.9% | 569 | 9.2 | 23 | 0 |
| proposed[no_ml_unknown] | 168.1 | 231.8 | 71.9% | 569 | 9.2 | 23 | 0 |
| proposed[perfect] | 168.1 | 231.8 | 71.9% | 569 | 9.2 | 23 | 0 |
| proposed[validation_rates] | 168.1 | 231.8 | 71.9% | 569 | 9.2 | 23 | 0 |
| round_robin | 168.1 | 231.8 | 71.9% | 569 | 9.2 | 23 | 0 |

## zero_supply

| Policy | Critical unmet Wh | Essential unmet Wh | Occupied service | Worst starvation s | Switches | Recovery s (max) | Violations |
|---|---:|---:|---:|---:|---:|---:|---:|
| essentials_first_no_ml | 255.6 | 117.8 | 81.2% | 319 | 12.2 | 23 | 0 |
| fixed_priority | 255.6 | 117.8 | 81.2% | 319 | 12.2 | 23 | 0 |
| oracle_occupancy_upper_bound | 255.6 | 117.8 | 81.2% | 319 | 12.2 | 23 | 0 |
| proposed[heavy_errors] | 255.6 | 117.8 | 81.2% | 319 | 12.2 | 23 | 0 |
| proposed[no_ml_unknown] | 255.6 | 117.8 | 81.2% | 319 | 12.2 | 23 | 0 |
| proposed[perfect] | 255.6 | 117.8 | 81.2% | 319 | 12.2 | 23 | 0 |
| proposed[validation_rates] | 255.6 | 117.8 | 81.2% | 319 | 12.2 | 23 | 0 |
| round_robin | 255.6 | 117.8 | 81.2% | 319 | 12.2 | 23 | 0 |

## recovery_chatter

| Policy | Critical unmet Wh | Essential unmet Wh | Occupied service | Worst starvation s | Switches | Recovery s (max) | Violations |
|---|---:|---:|---:|---:|---:|---:|---:|
| essentials_first_no_ml | 0.0 | 110.8 | 91.0% | 43 | 48.4 | 15 | 0 |
| fixed_priority | 0.0 | 178.9 | 87.1% | 43 | 48.4 | 15 | 0 |
| oracle_occupancy_upper_bound | 0.0 | 124.4 | 95.1% | 43 | 49.2 | 15 | 0 |
| proposed[heavy_errors] | 0.0 | 129.9 | 91.3% | 46 | 71.6 | 18 | 0 |
| proposed[no_ml_unknown] | 0.0 | 110.8 | 91.0% | 43 | 48.4 | 15 | 0 |
| proposed[perfect] | 0.0 | 124.2 | 95.1% | 43 | 49.2 | 15 | 0 |
| proposed[validation_rates] | 0.0 | 124.6 | 94.5% | 44 | 58.0 | 17 | 0 |
| round_robin | 0.0 | 186.7 | 86.7% | 41 | 107.2 | 19 | 0 |

## Paired differences: proposed[validation_rates] minus each other policy (mean over seeds, [min, max])

Negative is better for unmet Wh, starvation, switches and recovery; positive is better for occupied service.

| Scenario | vs policy | Δ critical unmet Wh | Δ essential unmet Wh | Δ occupied service | Δ worst starvation s | Δ switches |
|---|---|---:|---:|---:|---:|---:|
| deep_shortage_4kw | essentials_first_no_ml | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| deep_shortage_4kw | fixed_priority | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| deep_shortage_4kw | oracle_occupancy_upper_bound | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| deep_shortage_4kw | proposed[heavy_errors] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| deep_shortage_4kw | proposed[no_ml_unknown] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| deep_shortage_4kw | proposed[perfect] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| deep_shortage_4kw | round_robin | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_a_loss | essentials_first_no_ml | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_a_loss | fixed_priority | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_a_loss | oracle_occupancy_upper_bound | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_a_loss | proposed[heavy_errors] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_a_loss | proposed[no_ml_unknown] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_a_loss | proposed[perfect] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_a_loss | round_robin | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_b_loss | essentials_first_no_ml | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_b_loss | fixed_priority | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_b_loss | oracle_occupancy_upper_bound | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_b_loss | proposed[heavy_errors] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_b_loss | proposed[no_ml_unknown] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_b_loss | proposed[perfect] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_b_loss | round_robin | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| insufficient_critical_2kw | essentials_first_no_ml | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| insufficient_critical_2kw | fixed_priority | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| insufficient_critical_2kw | oracle_occupancy_upper_bound | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| insufficient_critical_2kw | proposed[heavy_errors] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| insufficient_critical_2kw | proposed[no_ml_unknown] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| insufficient_critical_2kw | proposed[perfect] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| insufficient_critical_2kw | round_robin | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| recovery_chatter | essentials_first_no_ml | +0 [+0, +0] | +13.8 [+2.92, +30.1] | +0.035 [+0, +0.096] | +1 [+0, +5] | +9.6 [+6, +16] |
| recovery_chatter | fixed_priority | +0 [+0, +0] | -54.2 [-65.1, -37.9] | +0.074 [+0.0444, +0.108] | +1 [+0, +5] | +9.6 [+6, +16] |
| recovery_chatter | oracle_occupancy_upper_bound | +0 [+0, +0] | +0.194 [-10.7, +10.7] | -0.005 [-0.0136, +0] | +1 [+0, +5] | +8.8 [+4, +16] |
| recovery_chatter | proposed[heavy_errors] | +0 [+0, +0] | -5.25 [-21.4, +7.78] | +0.032 [+0.0108, +0.0524] | -2 [-5, +0] | -13.6 [-22, +0] |
| recovery_chatter | proposed[no_ml_unknown] | +0 [+0, +0] | +13.8 [+2.92, +30.1] | +0.035 [+0, +0.096] | +1 [+0, +5] | +9.6 [+6, +16] |
| recovery_chatter | proposed[perfect] | +0 [+0, +0] | +0.389 [-10.7, +10.7] | -0.005 [-0.0136, +0] | +1 [+0, +5] | +8.8 [+4, +16] |
| recovery_chatter | round_robin | +0 [+0, +0] | -62 [-70, -48.6] | +0.078 [+0.0521, +0.108] | +3 [-5, +10] | -49.2 [-54, -40] |
| shortage_6kw | essentials_first_no_ml | +0 [+0, +0] | +15.2 [+1.94, +54.4] | +0.004 [-0.013, +0.047] | -15 [-80, +5] | +14 [+2, +36] |
| shortage_6kw | fixed_priority | +0 [+0, +0] | -161 [-174, -122] | +0.236 [+0.167, +0.317] | -289 [-495, +5] | +14.4 [+2, +36] |
| shortage_6kw | oracle_occupancy_upper_bound | +0 [+0, +0] | +0.389 [-16.5, +7.78] | -0.005 [-0.013, +0.0012] | +1 [+0, +5] | +12.8 [+0, +32] |
| shortage_6kw | proposed[heavy_errors] | +0 [+0, +0] | -17.3 [-31.1, +11.7] | +0.041 [+0.022, +0.0763] | +45 [-15, +235] | -38.4 [-66, -20] |
| shortage_6kw | proposed[no_ml_unknown] | +0 [+0, +0] | +15.2 [+1.94, +54.4] | +0.004 [-0.013, +0.047] | -15 [-80, +5] | +14 [+2, +36] |
| shortage_6kw | proposed[perfect] | +0 [+0, +0] | +0.389 [-16.5, +7.78] | -0.005 [-0.013, +0.0012] | +1 [+0, +5] | +12.8 [+0, +32] |
| shortage_6kw | round_robin | +0 [+0, +0] | -129 [-176, -38.9] | +0.19 [+0.141, +0.214] | -4 [-380, +380] | -166 [-178, -144] |
| zero_supply | essentials_first_no_ml | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| zero_supply | fixed_priority | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| zero_supply | oracle_occupancy_upper_bound | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| zero_supply | proposed[heavy_errors] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| zero_supply | proposed[no_ml_unknown] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| zero_supply | proposed[perfect] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| zero_supply | round_robin | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
