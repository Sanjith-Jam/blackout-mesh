# Allocation benchmark (alloc-bench-2026-10-10.2)

Commit `409a2eb` · safety policy `safety-2026-10-10.1` · 5 seeds per scenario · 2400 s per run at 5 s steps. Simulated outcomes only: watt-hours integrate modeled power over simulated time and are not measured savings.

Reproduce: `PYTHONPATH=backend python -m benchmarks.run_allocation` from the repository root.

Policies: `fixed_priority` (L0→L5), `essentials_first_no_ml` (critical, booked rooms, pump), `round_robin` (critical, then least-recently-served optional), `proposed[...]` (classifier → ActivityGuard → exact allocator) with each classifier variant and an always-UNKNOWN no-ML ablation, and `oracle_occupancy_upper_bound`, which reads true occupancy and is **not deployable**.

Every run of a scenario/seed has the same input digest (capacity, feeders, bookings, classifier outputs); true occupancy is used only by the evaluator.

## Ablation summary: shortage_6kw

Same inputs for every row. `proposed_no_dwell` is the classifier path without rank hysteresis; `proposed` adds `RankDwell` (a changed state must repeat on 3 readings). The oracle row bounds what any occupancy signal could add here.

| Policy | Occupied service | Switches | Essential unmet Wh | Critical unmet Wh |
|---|---:|---:|---:|---:|
| fixed_priority | 61.8% | 6.2 | 380.9 | 0.0 |
| round_robin | 66.3% | 186.2 | 348.8 | 0.0 |
| essentials_first_no_ml | 84.9% | 6.6 | 205.1 | 0.0 |
| proposed[no_ml_unknown] | 84.9% | 6.6 | 205.1 | 0.0 |
| proposed_no_dwell[validation_rates] | 85.4% | 20.6 | 220.3 | 0.0 |
| proposed[validation_rates] | 85.2% | 15.0 | 221.9 | 0.0 |
| proposed_no_dwell[heavy_errors] | 81.3% | 59.0 | 237.6 | 0.0 |
| proposed[heavy_errors] | 83.0% | 21.0 | 218.4 | 0.0 |
| proposed[perfect] | 85.7% | 7.8 | 220.7 | 0.0 |
| oracle_occupancy_upper_bound | 85.8% | 7.8 | 219.9 | 0.0 |

Headroom for occupancy evidence in this scenario: the non-deployable oracle serves occupied rooms +0.9% versus essentials-first without ML. Any classifier gain is bounded by that.

## Ablation summary: recovery_chatter

Same inputs for every row. `proposed_no_dwell` is the classifier path without rank hysteresis; `proposed` adds `RankDwell` (a changed state must repeat on 3 readings). The oracle row bounds what any occupancy signal could add here.

| Policy | Occupied service | Switches | Essential unmet Wh | Critical unmet Wh |
|---|---:|---:|---:|---:|
| fixed_priority | 87.1% | 48.4 | 178.9 | 0.0 |
| round_robin | 86.7% | 107.2 | 186.7 | 0.0 |
| essentials_first_no_ml | 91.0% | 48.4 | 110.8 | 0.0 |
| proposed[no_ml_unknown] | 91.0% | 48.4 | 110.8 | 0.0 |
| proposed_no_dwell[validation_rates] | 94.5% | 58.0 | 124.6 | 0.0 |
| proposed[validation_rates] | 94.9% | 51.6 | 118.0 | 0.0 |
| proposed_no_dwell[heavy_errors] | 91.3% | 71.6 | 129.9 | 0.0 |
| proposed[heavy_errors] | 93.1% | 54.8 | 116.7 | 0.0 |
| proposed[perfect] | 95.0% | 49.2 | 123.9 | 0.0 |
| oracle_occupancy_upper_bound | 95.1% | 49.2 | 124.4 | 0.0 |

Headroom for occupancy evidence in this scenario: the non-deployable oracle serves occupied rooms +4.1% versus essentials-first without ML. Any classifier gain is bounded by that.

## shortage_6kw

| Policy | Critical unmet Wh | Essential unmet Wh | Occupied service | Worst starvation s | Switches | Recovery s (max) | Violations |
|---|---:|---:|---:|---:|---:|---:|---:|
| essentials_first_no_ml | 0.0 | 205.1 | 84.9% | 541 | 6.6 | 10 | 0 |
| fixed_priority | 0.0 | 380.9 | 61.8% | 815 | 6.2 | 10 | 0 |
| oracle_occupancy_upper_bound | 0.0 | 219.9 | 85.8% | 525 | 7.8 | 10 | 0 |
| proposed[heavy_errors] | 0.0 | 218.4 | 83.0% | 499 | 21.0 | 10 | 0 |
| proposed[no_ml_unknown] | 0.0 | 205.1 | 84.9% | 541 | 6.6 | 10 | 0 |
| proposed[perfect] | 0.0 | 220.7 | 85.7% | 527 | 7.8 | 10 | 0 |
| proposed[validation_rates] | 0.0 | 221.9 | 85.2% | 483 | 15.0 | 10 | 0 |
| proposed_no_dwell[heavy_errors] | 0.0 | 237.6 | 81.3% | 481 | 59.0 | 10 | 0 |
| proposed_no_dwell[perfect] | 0.0 | 219.9 | 85.8% | 525 | 7.8 | 10 | 0 |
| proposed_no_dwell[validation_rates] | 0.0 | 220.3 | 85.4% | 526 | 20.6 | 11 | 0 |
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
| proposed_no_dwell[heavy_errors] | 0.0 | 346.3 | 65.1% | 700 | 8.2 | 13 | 0 |
| proposed_no_dwell[perfect] | 0.0 | 346.3 | 65.1% | 700 | 8.2 | 13 | 0 |
| proposed_no_dwell[validation_rates] | 0.0 | 346.3 | 65.1% | 700 | 8.2 | 13 | 0 |
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
| proposed_no_dwell[heavy_errors] | 0.0 | 242.7 | 71.5% | 518 | 6.6 | 12 | 0 |
| proposed_no_dwell[perfect] | 0.0 | 242.7 | 71.5% | 518 | 6.6 | 12 | 0 |
| proposed_no_dwell[validation_rates] | 0.0 | 242.7 | 71.5% | 518 | 6.6 | 12 | 0 |
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
| proposed_no_dwell[heavy_errors] | 505.6 | 1.0 | 99.8% | 3 | 8.0 | 15 | 0 |
| proposed_no_dwell[perfect] | 505.6 | 1.0 | 99.8% | 3 | 8.0 | 15 | 0 |
| proposed_no_dwell[validation_rates] | 505.6 | 1.0 | 99.8% | 3 | 8.0 | 15 | 0 |
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
| proposed_no_dwell[heavy_errors] | 168.1 | 231.8 | 71.9% | 569 | 9.2 | 23 | 0 |
| proposed_no_dwell[perfect] | 168.1 | 231.8 | 71.9% | 569 | 9.2 | 23 | 0 |
| proposed_no_dwell[validation_rates] | 168.1 | 231.8 | 71.9% | 569 | 9.2 | 23 | 0 |
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
| proposed_no_dwell[heavy_errors] | 255.6 | 117.8 | 81.2% | 319 | 12.2 | 23 | 0 |
| proposed_no_dwell[perfect] | 255.6 | 117.8 | 81.2% | 319 | 12.2 | 23 | 0 |
| proposed_no_dwell[validation_rates] | 255.6 | 117.8 | 81.2% | 319 | 12.2 | 23 | 0 |
| round_robin | 255.6 | 117.8 | 81.2% | 319 | 12.2 | 23 | 0 |

## recovery_chatter

| Policy | Critical unmet Wh | Essential unmet Wh | Occupied service | Worst starvation s | Switches | Recovery s (max) | Violations |
|---|---:|---:|---:|---:|---:|---:|---:|
| essentials_first_no_ml | 0.0 | 110.8 | 91.0% | 43 | 48.4 | 15 | 0 |
| fixed_priority | 0.0 | 178.9 | 87.1% | 43 | 48.4 | 15 | 0 |
| oracle_occupancy_upper_bound | 0.0 | 124.4 | 95.1% | 43 | 49.2 | 15 | 0 |
| proposed[heavy_errors] | 0.0 | 116.7 | 93.1% | 43 | 54.8 | 15 | 0 |
| proposed[no_ml_unknown] | 0.0 | 110.8 | 91.0% | 43 | 48.4 | 15 | 0 |
| proposed[perfect] | 0.0 | 123.9 | 95.0% | 43 | 49.2 | 15 | 0 |
| proposed[validation_rates] | 0.0 | 118.0 | 94.9% | 42 | 51.6 | 15 | 0 |
| proposed_no_dwell[heavy_errors] | 0.0 | 129.9 | 91.3% | 46 | 71.6 | 18 | 0 |
| proposed_no_dwell[perfect] | 0.0 | 124.2 | 95.1% | 43 | 49.2 | 15 | 0 |
| proposed_no_dwell[validation_rates] | 0.0 | 124.6 | 94.5% | 44 | 58.0 | 17 | 0 |
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
| deep_shortage_4kw | proposed_no_dwell[heavy_errors] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| deep_shortage_4kw | proposed_no_dwell[perfect] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| deep_shortage_4kw | proposed_no_dwell[validation_rates] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| deep_shortage_4kw | round_robin | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_a_loss | essentials_first_no_ml | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_a_loss | fixed_priority | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_a_loss | oracle_occupancy_upper_bound | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_a_loss | proposed[heavy_errors] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_a_loss | proposed[no_ml_unknown] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_a_loss | proposed[perfect] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_a_loss | proposed_no_dwell[heavy_errors] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_a_loss | proposed_no_dwell[perfect] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_a_loss | proposed_no_dwell[validation_rates] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_a_loss | round_robin | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_b_loss | essentials_first_no_ml | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_b_loss | fixed_priority | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_b_loss | oracle_occupancy_upper_bound | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_b_loss | proposed[heavy_errors] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_b_loss | proposed[no_ml_unknown] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_b_loss | proposed[perfect] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_b_loss | proposed_no_dwell[heavy_errors] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_b_loss | proposed_no_dwell[perfect] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_b_loss | proposed_no_dwell[validation_rates] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| feeder_b_loss | round_robin | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| insufficient_critical_2kw | essentials_first_no_ml | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| insufficient_critical_2kw | fixed_priority | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| insufficient_critical_2kw | oracle_occupancy_upper_bound | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| insufficient_critical_2kw | proposed[heavy_errors] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| insufficient_critical_2kw | proposed[no_ml_unknown] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| insufficient_critical_2kw | proposed[perfect] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| insufficient_critical_2kw | proposed_no_dwell[heavy_errors] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| insufficient_critical_2kw | proposed_no_dwell[perfect] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| insufficient_critical_2kw | proposed_no_dwell[validation_rates] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| insufficient_critical_2kw | round_robin | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| recovery_chatter | essentials_first_no_ml | +0 [+0, +0] | +7.19 [+0, +29.2] | +0.039 [-0.0016, +0.096] | -1 [-5, +0] | +3.2 [+0, +8] |
| recovery_chatter | fixed_priority | +0 [+0, +0] | -60.9 [-68.1, -38.9] | +0.078 [+0.0428, +0.108] | -1 [-5, +0] | +3.2 [+0, +8] |
| recovery_chatter | oracle_occupancy_upper_bound | +0 [+0, +0] | -6.42 [-22.4, +0.972] | -0.001 [-0.0058, +0] | -1 [-5, +0] | +2.4 [+0, +6] |
| recovery_chatter | proposed[heavy_errors] | +0 [+0, +0] | +1.36 [-14.6, +26.3] | +0.018 [-0.0016, +0.0444] | -1 [-5, +5] | -3.2 [-12, +4] |
| recovery_chatter | proposed[no_ml_unknown] | +0 [+0, +0] | +7.19 [+0, +29.2] | +0.039 [-0.0016, +0.096] | -1 [-5, +0] | +3.2 [+0, +8] |
| recovery_chatter | proposed[perfect] | +0 [+0, +0] | -5.83 [-22.4, +0.972] | -0.001 [-0.0016, +0] | -1 [-5, +0] | +2.4 [+0, +6] |
| recovery_chatter | proposed_no_dwell[heavy_errors] | +0 [+0, +0] | -11.9 [-22.4, +6.81] | +0.036 [+0.0092, +0.0567] | -4 [-10, +0] | -20 [-26, -12] |
| recovery_chatter | proposed_no_dwell[perfect] | +0 [+0, +0] | -6.22 [-22.4, +0.972] | -0.001 [-0.0058, +0] | -1 [-5, +0] | +2.4 [+0, +6] |
| recovery_chatter | proposed_no_dwell[validation_rates] | +0 [+0, +0] | -6.61 [-11.7, -0.972] | +0.004 [-0.0016, +0.0136] | -2 [-5, +0] | -6.4 [-12, -2] |
| recovery_chatter | round_robin | +0 [+0, +0] | -68.6 [-77.8, -49.6] | +0.082 [+0.0505, +0.108] | +1 [-5, +10] | -55.6 [-60, -50] |
| shortage_6kw | essentials_first_no_ml | +0 [+0, +0] | +16.7 [+0, +69] | +0.003 [-0.0114, +0.0352] | -58 [-230, +0] | +8.4 [+0, +16] |
| shortage_6kw | fixed_priority | +0 [+0, +0] | -159 [-176, -107] | +0.235 [+0.167, +0.305] | -332 [-725, +0] | +8.8 [+0, +18] |
| shortage_6kw | oracle_occupancy_upper_bound | +0 [+0, +0] | +1.95 [-2.92, +7.78] | -0.006 [-0.0118, +0.0012] | -42 [-230, +20] | +7.2 [-2, +16] |
| shortage_6kw | proposed[heavy_errors] | +0 [+0, +0] | +3.5 [-21.4, +49.6] | +0.022 [+0, +0.0536] | -16 [-45, +0] | -6 [-12, +0] |
| shortage_6kw | proposed[no_ml_unknown] | +0 [+0, +0] | +16.7 [+0, +69] | +0.003 [-0.0114, +0.0352] | -58 [-230, +0] | +8.4 [+0, +16] |
| shortage_6kw | proposed[perfect] | +0 [+0, +0] | +1.17 [-4.86, +7.78] | -0.004 [-0.0114, +0.0035] | -44 [-230, +10] | +7.2 [-2, +16] |
| shortage_6kw | proposed_no_dwell[heavy_errors] | +0 [+0, +0] | -15.8 [-32.1, +26.2] | +0.04 [+0.0243, +0.0779] | +2 [+0, +5] | -44 [-66, -26] |
| shortage_6kw | proposed_no_dwell[perfect] | +0 [+0, +0] | +1.95 [-2.92, +7.78] | -0.006 [-0.0118, +0.0012] | -42 [-230, +20] | +7.2 [-2, +16] |
| shortage_6kw | proposed_no_dwell[validation_rates] | +0 [+0, +0] | +1.56 [-3.89, +14.6] | -0.001 [-0.0118, +0.0046] | -43 [-230, +20] | -5.6 [-24, +0] |
| shortage_6kw | round_robin | +0 [+0, +0] | -127 [-178, -24.3] | +0.189 [+0.141, +0.216] | -47 [-380, +150] | -171 [-180, -162] |
| zero_supply | essentials_first_no_ml | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| zero_supply | fixed_priority | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| zero_supply | oracle_occupancy_upper_bound | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| zero_supply | proposed[heavy_errors] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| zero_supply | proposed[no_ml_unknown] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| zero_supply | proposed[perfect] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| zero_supply | proposed_no_dwell[heavy_errors] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| zero_supply | proposed_no_dwell[perfect] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| zero_supply | proposed_no_dwell[validation_rates] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
| zero_supply | round_robin | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] | +0 [+0, +0] |
