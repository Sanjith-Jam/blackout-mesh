# Diagnosis benchmark: `heldout` split

Protocol `diag-bench-protocol-2` · developer-held-out (no independent custodian) · detector: app.diagnosis (telemetry-only, #4). 48 scenarios (32 steps × 3 transformers each). Synthetic telemetry only; this does not establish field accuracy.

| Family | Scenarios | Recall | Precision | False alarms (rate) | Time to detect (median / max steps) | Location errors | Coverage | Correct abstentions | Safety violations | Missed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| normal | 4 | — (0/0) | — (0/0) | 0 (0.0) | — / — | 0 | 1.0 | 0 | 0 | 0 |
| demand_change | 4 | — (0/0) | — (0/0) | 0 (0.0) | — / — | 0 | 1.0 | 0 | 0 | 0 |
| hot_ambient | 4 | 1.0 (4/4) | 1.0 (4/4) | 0 (0.0) | 2.5 / 4 | 0 | 1.0 | 0 | 7 | 0 |
| overload | 4 | 1.0 (4/4) | 0.8 (4/5) | 0 (0.0) | 2.5 / 6 | 0 | 1.0 | 0 | 13 | 0 |
| cooling_failure | 4 | 1.0 (4/4) | 1.0 (4/4) | 0 (0.0) | 4.0 / 5 | 0 | 1.0 | 0 | 19 | 0 |
| overload_and_cooling | 4 | 1.0 (4/4) | 1.0 (6/6) | 0 (0.0) | 1.0 / 1 | 0 | 1.0 | 0 | 2 | 0 |
| upstream_loss | 4 | 1.0 (4/4) | 1.0 (12/12) | 0 (0.0) | 1.0 / 1 | 0 | 1.0 | 0 | 0 | 0 |
| branch_interruption | 4 | 1.0 (4/4) | 1.0 (4/4) | 0 (0.0) | 1.0 / 1 | 0 | 1.0 | 0 | 0 | 0 |
| sensor_dropout | 4 | 1.0 (4/4) | — (0/0) | 0 (0.0) | 0.0 / 0 | 0 | 0.7734 | 87 | 0 | 0 |
| stuck_sensor | 4 | 0.5 (2/4) | 1.0 (2/2) | 0 (0.0) | 14.5 / 18 | 0 | 1.0 | 0 | 63 | 2 |
| delay_reorder | 4 | 1.0 (4/4) | 1.0 (4/4) | 0 (0.0) | 2.5 / 8 | 0 | 0.9922 | 0 | 11 | 0 |
| recovery_chatter | 4 | 1.0 (4/4) | 1.0 (4/4) | 0 (0.0) | 1.0 / 1 | 0 | 1.0 | 0 | 7 | 0 |
