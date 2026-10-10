# Temporal occupancy audit — issue #5

EXPLORATORY_ONLY; campus generalization unvalidated. No replacement model adopted.

All source data are UCI office occupancy observations (Candanedo & Feldheim; DOI 10.24432/C5X01N, CC BY 4.0). These are presence labels, not equipment demand or classroom-use labels. Existing UCI evaluation days were already exposed; every number below is exploratory, not an untouched final test or campus accuracy claim.

## Audit and protocol

The archive contains **20,560 records**, **20,560 unique timestamp/feature/label records**, and **0 exact duplicates**. Conflicting records at one timestamp are rejected. Four expanding chronological folds evaluate whole days, with the first six days for training and two each for validation/evaluation. Training transforms fit training rows only. Day groups proxy sessions because this dataset has no session IDs: this is not proof of independent rooms or independently collected sessions. The incomplete final two-day block is excluded (2015-02-18).

Fixed protocol and gate: [PROTOCOL.md](PROTOCOL.md). Full split dates, row-index fingerprints, class counts, confusion matrices, day variation, operating points and timing: [results.json](results.json). Dataset SHA and protocol SHA bind each replay to the same data and feature order. Overlapping training across rolling folds is intentional; evaluation days never overlap across folds. Later-origin training can include earlier-origin evaluation days, without retroactively changing earlier models or selection.

Candidates fit only prior days. Validation chooses a threshold/abstention point only if coverage ≥90% and false-INACTIVE ≤5% of occupied rows. A failed validation gate forces all-UNKNOWN for that fold. This conservative fallback is counted in coverage and all-row F1; zero false-INACTIVE with zero coverage is not success. Raw ungated 0.5-threshold diagnostics are also recorded separately, never used to override the gate. No probability calibration was attempted: scores remain uncalibrated.

## Pooled evaluation outcomes

9,766 evaluation rows: 2,094 occupied and 7,672 unoccupied. Columns use the same denominators even when predictions abstain.

| Candidate / operating policy | False-INACTIVE / occupied | Coverage | Selective risk on covered rows | All-row macro-F1 |
|---|---:|---:|---:|---:|
| majority | 2094/2094 (100.0%) | 100.0% | 21.4% | 0.440 |
| co2_rule | 1534/2094 (73.3%) | 100.0% | 19.7% | 0.625 |
| logistic | 121/2094 (5.8%) | 40.0% | 27.6% | 0.279 |
| tree | 0/2094 (0.0%) | 0.0% | undefined (no covered rows) | 0.000 |
| logistic_light_experiment | 11/2094 (0.5%) | 70.1% | 1.5% | 0.741 |

## Day variation and resource evidence

| Origin evaluation days | Logistic gate passed | False-INACTIVE / occupied | Coverage | Single p95 ms | Artifact bytes |
|---|---|---:|---:|---:|---:|
| 2015-02-10, 2015-02-11 | True | 121/268 | 91.1% | 0.196 | 1489 |
| 2015-02-12, 2015-02-13 | False | 0/738 | 0.0% | 0.199 | 1489 |
| 2015-02-14, 2015-02-15 | True | 0/0 | 100.0% | 0.197 | 1489 |
| 2015-02-16, 2015-02-17 | False | 0/1088 | 0.0% | 0.199 | 1489 |

Environment: Python 3.14.7, sklearn 1.9.1, numpy 2.5.3. Peak **process** RSS 204.9 MiB includes the evaluation process and imports, not model-only memory. Latencies are warm measurements (30 repetitions); they do not establish deployment SLA or cold-start limits. Batch-128 p50/p95 and per-day confusion matrices are in the JSON.

## Interpretation and next decision

The four-sensor candidates fail temporal stability and/or coverage. In the first logistic evaluation block, 121/268 occupied rows (45.1%) were falsely INACTIVE despite a passing prior validation gate; the smaller pooled rate partly reflects all-UNKNOWN fallbacks in later folds. Retain the shipped logistic artifact and UNKNOWN evidence guards; do not advertise validated generalization. The retained artifact is a demo baseline, not a winner proven safe by these results. Its SHA-256 remains `b552641e908e6c1011c61223401f6e527d9d87aebc247025cf4812c1243efdf9`.

Adding Light to an offline logistic experiment reduces observed false-INACTIVE and increases covered-row quality, but still only covers about 70% overall under the same gate. This supports investigating the omitted signal; it does not prove causation or campus transfer. Light can also change after shedding, so it remains excluded from the runtime causal feature schema. Mean-feature shifts between train/evaluation are recorded as drift diagnostics, not asserted explanations. Environment/session confounding cannot be resolved from one office and requires additional rooms and independent labels.

No independently labeled campus sessions are available. Follow the collection and frozen final-session protocol in PROTOCOL.md before claiming generalization: reserve whole rooms/days, freeze thresholds and manifests before opening final labels, separately label presence/session use/equipment demand, evaluate every occupied session and retain UNKNOWN on failed evidence. The adoption gate includes ≥90% coverage, ≤5% false-INACTIVE in every occupied session, ≥0.01 F1 gain over the frozen baseline, and p95 ≤50 ms. No model is promoted from the exposed UCI data.

## Reproduce

```sh
.venv-ml/bin/python backend/scripts/evaluate_temporal.py --data /path/to/occupancy.zip
PYTHONPATH=backend .venv-ml/bin/python -m pytest backend/tests/test_temporal_evaluation.py -q
```

Download the original archive from https://archive.ics.uci.edu/static/public/357/occupancy+detection.zip and verify its SHA against results.json. The audit writes only its own results.json; it never writes backend/models. The runtime artifact, manifest and replay remain unchanged.
