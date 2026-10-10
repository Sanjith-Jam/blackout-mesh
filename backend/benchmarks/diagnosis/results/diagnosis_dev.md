# Diagnosis benchmark: `dev` split

Protocol `diag-bench-protocol-2` · developer-held-out (no independent custodian) · detector: app.diagnosis (telemetry-only, #4). 48 scenarios (32 steps × 3 transformers each). Synthetic telemetry only; this does not establish field accuracy.

| Family | Scenarios | Recall | Precision | False alarms (rate) | Time to detect (median / max steps) | Location errors | Coverage | Correct abstentions | Safety violations | Missed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| normal | 4 | — (0/0) | — (0/0) | 0 (0.0) | — / — | 0 | 1.0 | 0 | 0 | 0 |
| demand_change | 4 | — (0/0) | — (0/0) | 0 (0.0) | — / — | 0 | 1.0 | 0 | 0 | 0 |
| hot_ambient | 4 | 1.0 (4/4) | 1.0 (4/4) | 0 (0.0) | 3.0 / 3 | 0 | 1.0 | 0 | 0 | 0 |
| overload | 4 | 1.0 (4/4) | 1.0 (4/4) | 0 (0.0) | 1.0 / 1 | 0 | 1.0 | 0 | 0 | 0 |
| cooling_failure | 4 | 1.0 (4/4) | 1.0 (4/4) | 0 (0.0) | 3.0 / 3 | 0 | 1.0 | 0 | 0 | 0 |
| overload_and_cooling | 4 | 1.0 (4/4) | 1.0 (8/8) | 0 (0.0) | 1.0 / 1 | 0 | 1.0 | 0 | 0 | 0 |
| upstream_loss | 4 | 1.0 (4/4) | 1.0 (12/12) | 0 (0.0) | 1.0 / 1 | 0 | 1.0 | 0 | 0 | 0 |
| branch_interruption | 4 | 1.0 (4/4) | 1.0 (4/4) | 0 (0.0) | 1.0 / 1 | 0 | 1.0 | 0 | 0 | 0 |
| sensor_dropout | 4 | 1.0 (4/4) | — (0/0) | 0 (0.0) | 0.0 / 0 | 0 | 0.7969 | 78 | 0 | 0 |
| stuck_sensor | 4 | 1.0 (4/4) | — (0/0) | 0 (0.0) | 1.0 / 1 | 0 | 0.9583 | 16 | 73 | 0 |
| delay_reorder | 4 | 1.0 (4/4) | 1.0 (4/4) | 0 (0.0) | 1.5 / 2 | 0 | 0.9948 | 0 | 0 | 0 |
| recovery_chatter | 4 | 1.0 (4/4) | 1.0 (4/4) | 0 (0.0) | 1.0 / 1 | 0 | 1.0 | 0 | 0 | 0 |

## Ranked hypotheses and abstention

Ranking is evaluated on the first faulty asset-step at or after onset + 2 steps. Top-k is cause recall for any accepted expected code; scores are uncalibrated rule evidence, not probabilities.

| Family | Ranked cases | Top-1 | Top-3 | MRR | Candidate precision | Expected abstentions | Abstention precision / recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| normal | 0 | — (0/0) | — (0/0) | — | — (0/0) | 0 | — / — (0/0; 0/0) |
| demand_change | 0 | — (0/0) | — (0/0) | — | — (0/0) | 0 | — / — (0/0; 0/0) |
| hot_ambient | 4 | 1.0 (4/4) | 1.0 (4/4) | 1.0 | 1.0 (4/4) | 0 | — / — (0/0; 0/0) |
| overload | 4 | 1.0 (4/4) | 1.0 (4/4) | 1.0 | 1.0 (4/4) | 0 | — / — (0/0; 0/0) |
| cooling_failure | 4 | 1.0 (4/4) | 1.0 (4/4) | 1.0 | 1.0 (4/4) | 0 | — / — (0/0; 0/0) |
| overload_and_cooling | 4 | 1.0 (4/4) | 1.0 (4/4) | 1.0 | 1.0 (7/7) | 0 | — / — (0/0; 0/0) |
| upstream_loss | 12 | 1.0 (12/12) | 1.0 (12/12) | 1.0 | 1.0 (12/12) | 0 | — / — (0/0; 0/0) |
| branch_interruption | 4 | 1.0 (4/4) | 1.0 (4/4) | 1.0 | 1.0 (4/4) | 0 | — / — (0/0; 0/0) |
| sensor_dropout | 0 | — (0/0) | — (0/0) | — | — (0/0) | 4 | 1.0 / 1.0 (4/4; 4/4) |
| stuck_sensor | 4 | 0.0 (0/4) | 0.0 (0/4) | 0.0 | — (0/0) | 4 | 1.0 / 1.0 (4/4; 4/4) |
| delay_reorder | 4 | 1.0 (4/4) | 1.0 (4/4) | 1.0 | 1.0 (4/4) | 0 | — / — (0/0; 0/0) |
| recovery_chatter | 4 | 1.0 (4/4) | 1.0 (4/4) | 1.0 | 1.0 (4/4) | 0 | — / — (0/0; 0/0) |
