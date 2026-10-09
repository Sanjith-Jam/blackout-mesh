# Occupancy temporal audit protocol v1 — issue #5

Written before running this new audit, after the original UCI results were exposed.
All UCI data are development/exploratory. No UCI result can validate campus generalization.

- Freeze the shipped artifact and manifest; this audit must not overwrite either.
- Deduplicate exact timestamp/feature/label records; reject conflicting labels/features at the same timestamp.
- Hold out complete calendar days, including any gaps: days are the conservative session proxy because true session IDs are absent.
- Expanding origins: first six available days for training, next two for operating-point selection, next two for evaluation; advance two days. No random row split. Every training transform fits training only.
- Compare training-majority, fixed CO2 >=1000 ppm rule, balanced logistic regression and balanced depth-6 tree (seed42). Repeat logistic with Light as an offline omitted-variable experiment; Light is not a proposed runtime input.
- Select thresholds from {0.15,0.24,0.35,0.5}, abstention margins {0,0.05,0.15}. Require >=90% coverage and <=5% false-INACTIVE among occupied validation rows; among passing points maximize all-row macro-F1, then coverage, then lower false-INACTIVE. If none passes, abstain on every row. Do not tune from evaluation days.
- Report each evaluation day and pooled folds: class counts, confusion matrices, false-INACTIVE numerator/occupied denominator, coverage, selective risk, single/batch latency, artifact bytes and process peak RSS. Feature mean shifts are descriptive; do not claim they cause failure.
- Adoption gate: separately collected, independently labeled campus sessions, day/room disjoint from development; >=90% coverage, <=5% false-INACTIVE in every occupied session, >=0.01 macro-F1 gain over the frozen baseline, p95 <=50 ms. Until that exists: retain baseline and conservative UNKNOWN guards.
- No calibration with evaluation labels. Scores remain uncalibrated. No future/time, truth, RFID/card IDs, scenario IDs, served power, mask or load labels in features.

Occupancy is human presence; room use is a session/request signal; equipment demand is configured/requested watts. This dataset measures only the first. New-room collection needs consented independent occupancy labels, timestamped causal sensors, room/date/session IDs for splitting only, and equipment/session labels kept separate. Freeze a manifest before opening final labels; collect occupied, empty, changing and sensor-failure periods. Never label presence from RFID alone.
