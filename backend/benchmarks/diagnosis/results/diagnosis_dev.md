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
| stuck_sensor | 4 | 0.0 (0/4) | — (0/0) | 0 (0.0) | — / — | 0 | 1.0 | 0 | 85 | 4 |
| delay_reorder | 4 | 1.0 (4/4) | 1.0 (4/4) | 0 (0.0) | 1.5 / 2 | 0 | 0.9948 | 0 | 0 | 0 |
| recovery_chatter | 4 | 1.0 (4/4) | 1.0 (4/4) | 0 (0.0) | 1.0 / 1 | 0 | 1.0 | 0 | 0 | 0 |
