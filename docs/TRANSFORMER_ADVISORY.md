# Transformer advisory evaluation (#66)

Status: synthetic interface/compatibility check only. No trained model is served.
The district threshold diagnosis remains authoritative for its existing display;
this offline module has no control, allocation, isolation or restoration caller.
It returns UNKNOWN with a null probability even for complete compatible features.

## Source and permission

Selected source: roshini0108/Transformer-Health-Intelligence-System,
commit `78aeea0381a066fd97d9e00cce5a176a7af6b0ed`.
https://github.com/roshini0108/Transformer-Health-Intelligence-System/tree/78aeea0381a066fd97d9e00cce5a176a7af6b0ed
The user reports that the owner granted code reuse permission (issue #66 and
GNITC_DISTRICT_MVP_PLAN.md). This is user-provided authorization, not an inferred
license or independently verified permission document. The pinned tree has no
repository license. The source headers identify the files and purpose but contain
no copyright/license notice. Attribution is retained in the adapter header and here.
No upstream file is copied verbatim. The adapted feature vocabulary and rolling
semantics come from `ml/src/preprocessor.py:FEATURE_COLUMNS, engineer_features`.

Reviewed, excluded runtime symbols: `split_by_transformer`,
`ml/src/prediction_model.py:train_failure_model`,
`backend/services/prediction_service.py:get_latest_features`, and
`ml/src/health_scorer.py:compute_health_score`.
No CSV, dataset, joblib weights, video, ZIP, frontend, database or model artifacts
were downloaded/copied. Code permission does not establish their rights.
The earlier local sources checkout is absent in this workspace; the pinned GitHub
code/tree were inspected directly, without importing the upstream application.

## Findings and input boundary

Upstream training uses a 168-reading load mean, but serving uses its whole fetched
history for load_7d_mean. Serving anchors freshness to MAX(recorded_at), permits
partial history and defaults age/capacity. Training uses test-set medians and
passes the test set to fit; no independent validation/calibration partition exists.
These behaviors are not reused. Published upstream synthetic metrics are not app
accuracy evidence.

`features_at` is the single batch/serving feature interface: 720 consecutive hourly
UTC observations ending less than one hour before decision time; 24/168/720 sample
windows include the current reading. The latest timestamp supplies hour/month.
Only the seven bounded raw/metadata fields in BOUNDS and a boolean observed trip
are accepted. Metadata must be supplied as known-at-decision values, never defaulted.
Trip provenance must be OBSERVED_TRIP; synthetic fixtures use that vocabulary only
to exercise the interface, not to assert physical evidence. Future and other-device
rows are excluded. Wrong types, nonfinite/range violations, duplicate/irregular
cadence, missing history/status and unsupported trip evidence abstain.

The district has only oil temperature, voltage, current and cooling observations;
it has no verified load percentage, ambient temperature, PF, THD, asset age or trip
history. Current, synthetic flow, fault/scenario IDs, topology truth and outcomes
must not fill these gaps. No API/schema/UI change or accuracy claim is introduced.

## Evaluation and evidence gate

Run: `PYTHONPATH=backend python -m benchmarks.transformer_compatibility`.
Three synthetic fixtures: normal, overload, cooling failure. Compatible features:
3/3; advisory UNKNOWN: 3/3; interface failures: 0/3. Threshold baseline outputs:
UNKNOWN, SUSPECTED, SUSPECTED respectively. These compare interface behavior only;
the baseline diagnoses immediate threshold suspicion, not a 30-day failure target.
Real transformers/readings: 0/0. Train/validation/test denominators: 0/0/0.
Predictive failures, calibration, threshold selection and accuracy: unavailable,
not zero. Ten focused tests cover invalid/incomplete/stale data and causality.

Before evaluation proceeds, obtain separately rights-cleared, timestamped real
history, asset metadata, observed trips, and independently adjudicated outcomes.
Freeze disjoint transformer cohorts and chronological train/validation/test windows;
exclude overlapping feature windows and embargo at least the 30-day outcome horizon
between windows. Fit preprocessing/model only on training. Choose calibration and
inspection threshold only on validation, then freeze before held-out testing.
Report transformers, readings, positive/negative outcomes, coverage, abstentions,
errors, confusion counts, calibration/Brier score and baseline comparison on the
same eligible observations. Never tune on held-out outcomes. Until then, no model
weights are loaded and no risk score or maintenance classification is produced.
