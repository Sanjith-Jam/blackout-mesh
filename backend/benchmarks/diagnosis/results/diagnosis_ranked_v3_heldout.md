# Diagnosis benchmark: `ranked heldout` split

Protocol `diag-bench-ranked-v3` · developer-held-out frozen before first ranked-metric run; no independent custodian · detector: app.diagnosis (telemetry-only, #4). 96 scenarios (32 steps × 3 transformers each). Synthetic telemetry only; this does not establish field accuracy.

| Family | Scenarios | Recall | Precision | False alarms (rate) | Time to detect (median / max steps) | Location errors | Coverage | Correct abstentions | Safety violations | Missed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| normal | 8 | — (0/0) | — (0/0) | 0 (0.0) | — / — | 0 | 1.0 | 0 | 0 | 0 |
| demand_change | 8 | — (0/0) | — (0/0) | 0 (0.0) | — / — | 0 | 1.0 | 0 | 0 | 0 |
| hot_ambient | 8 | 1.0 (8/8) | 1.0 (8/8) | 0 (0.0) | 2.0 / 3 | 0 | 1.0 | 0 | 0 | 0 |
| overload | 8 | 1.0 (8/8) | 1.0 (8/8) | 0 (0.0) | 1.0 / 1 | 0 | 1.0 | 0 | 0 | 0 |
| cooling_failure | 8 | 1.0 (8/8) | 1.0 (8/8) | 0 (0.0) | 2.0 / 3 | 0 | 1.0 | 0 | 0 | 0 |
| overload_and_cooling | 8 | 1.0 (8/8) | 1.0 (10/10) | 0 (0.0) | 1.0 / 1 | 0 | 1.0 | 0 | 0 | 0 |
| upstream_loss | 8 | 1.0 (8/8) | 1.0 (24/24) | 0 (0.0) | 1.0 / 1 | 0 | 1.0 | 0 | 0 | 0 |
| branch_interruption | 8 | 1.0 (8/8) | 1.0 (8/8) | 0 (0.0) | 1.0 / 1 | 0 | 1.0 | 0 | 0 | 0 |
| sensor_dropout | 8 | 1.0 (8/8) | — (0/0) | 0 (0.0) | 0.0 / 0 | 0 | 0.7708 | 176 | 0 | 0 |
| stuck_sensor | 8 | 1.0 (8/8) | 1.0 (6/6) | 0 (0.0) | 1.0 / 1 | 0 | 0.8229 | 136 | 0 | 0 |
| delay_reorder | 8 | 1.0 (8/8) | 1.0 (8/8) | 0 (0.0) | 1.5 / 3 | 0 | 0.9961 | 0 | 0 | 0 |
| recovery_chatter | 8 | 1.0 (8/8) | 1.0 (8/8) | 0 (0.0) | 1.0 / 1 | 0 | 1.0 | 0 | 0 | 0 |

## Ranked hypotheses and abstention

Ranking is evaluated on the first faulty asset-step at or after onset + 2 steps. Top-k is cause recall for any accepted expected code; scores are uncalibrated rule evidence, not probabilities.

| Family | Ranked cases | Top-1 | Top-3 | MRR | Candidate precision | Expected abstentions | Abstention precision / recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| normal | 0 | — (0/0) | — (0/0) | — | — (0/0) | 0 | — / — (0/0; 0/0) |
| demand_change | 0 | — (0/0) | — (0/0) | — | — (0/0) | 0 | — / — (0/0; 0/0) |
| hot_ambient | 8 | 1.0 (8/8) | 1.0 (8/8) | 1.0 | 1.0 (8/8) | 0 | — / — (0/0; 0/0) |
| overload | 8 | 1.0 (8/8) | 1.0 (8/8) | 1.0 | 1.0 (8/8) | 0 | — / — (0/0; 0/0) |
| cooling_failure | 8 | 1.0 (8/8) | 1.0 (8/8) | 1.0 | 1.0 (8/8) | 0 | — / — (0/0; 0/0) |
| overload_and_cooling | 8 | 1.0 (8/8) | 1.0 (8/8) | 1.0 | 1.0 (16/16) | 0 | — / — (0/0; 0/0) |
| upstream_loss | 24 | 1.0 (24/24) | 1.0 (24/24) | 1.0 | 1.0 (24/24) | 0 | — / — (0/0; 0/0) |
| branch_interruption | 8 | 1.0 (8/8) | 1.0 (8/8) | 1.0 | 1.0 (8/8) | 0 | — / — (0/0; 0/0) |
| sensor_dropout | 0 | — (0/0) | — (0/0) | — | — (0/0) | 8 | 1.0 / 1.0 (8/8; 8/8) |
| stuck_sensor | 8 | 0.0 (0/8) | 0.0 (0/8) | 0.0 | — (0/0) | 8 | 1.0 / 1.0 (8/8; 8/8) |
| delay_reorder | 8 | 1.0 (8/8) | 1.0 (8/8) | 1.0 | 1.0 (8/8) | 0 | — / — (0/0; 0/0) |
| recovery_chatter | 8 | 1.0 (8/8) | 1.0 (8/8) | 1.0 | 1.0 (8/8) | 0 | — / — (0/0; 0/0) |
