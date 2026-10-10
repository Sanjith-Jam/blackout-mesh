# Activity model evaluation

The backend uses a locally trained `StandardScaler + LogisticRegression` model to estimate office occupancy from four environment readings. This is an activity proxy for recorded office data, not a claim about campus labs or equipment use. The runtime score is a model probability and is not calibrated confidence.

## Data and split

The source is the [UCI Occupancy Detection dataset](https://archive.ics.uci.edu/dataset/357/occupancy+detection), DOI `10.24432/C5X01N`, licensed CC BY 4.0. Attribution: Luis M. Candanedo and Véronique Feldheim, “Accurate occupancy detection of an office room from light, temperature, humidity and CO2 measurements using statistical learning models,” *Energy and Buildings* 112 (2016), 28–39.

Rows were deduplicated by timestamp, four selected feature values, and label. All rows were sorted by timestamp and split into disjoint whole-day blocks:

- Train: February 2–8, 2015; 8,794 rows (6,681 inactive, 2,113 occupied).
- Validation: February 9–11, 2015; 2,566 rows (1,764 inactive, 802 occupied).
- Exploratory test: February 12–18, 2015; 9,200 rows (7,365 inactive, 1,835 occupied).

The first development draft exposed exploratory test metrics before the final selection. Therefore the last block is time-disjoint but must not be called an untouched final test. It was not used to select the final model or operating point.

The only inference features are `temperature_c`, `humidity_pct`, `co2_ppm`, and `humidity_ratio`. `Light`, timestamps, record IDs, labels, classroom/card/scenario IDs, allocation masks, and served power are excluded from model inputs.

Reproduce the selected baseline and its runtime artifact on Python 3.14 with `python3.14 -m venv .venv-ml`, `.venv-ml/bin/pip install -r backend/requirements-ml.txt`, then `.venv-ml/bin/python backend/scripts/train_activity.py --skip-tabicl`. Add `.venv-ml/bin/pip install pytest` and run `PYTHONPATH=backend .venv-ml/bin/python -m pytest backend/tests/test_activity_model.py -q` for the ML checks. To repeat the optional TabICL comparison, first install CPU-only PyTorch with `.venv-ml/bin/pip install torch==2.14.1+cpu --index-url https://download.pytorch.org/whl/cpu`, install `backend/requirements-ml-benchmark.txt`, then run `.venv-ml/bin/python backend/scripts/train_activity.py --sample-limit 256`. The benchmark fetches the pinned checkpoint and UCI archive; it does not put either in the shipped model directory.

## Selection and measured results

The active threshold and abstention band were tuned on validation only. Among points with at least 90% coverage, the procedure maximizes macro-F1 with UNKNOWN counted as an error. If a positive abstention band is within 0.01 macro-F1 of the best point, it chooses the widest such band; remaining ties prefer higher macro-F1, occupancy recall, then coverage. This selected active threshold `0.24` and abstention margin `0.15`, with 94.3% validation coverage. The score is not calibrated confidence.

| Model | Partition | Rows | Macro-F1, UNKNOWN as error | Occupancy recall | False-INACTIVE / occupied | UNKNOWN | Coverage |
|---|---|---:|---:|---:|---:|---:|---:|
| Logistic | Validation | 2,566 | 0.843 | 0.818 | 68 / 802 (8.5%) | 146 (5.7%) | 94.3% |
| Random Forest | Validation | 2,566 | 0.795 | 0.749 | 143 / 802 (17.8%) | 142 (5.5%) | 94.5% |
| Logistic | Exploratory test | 9,200 | 0.496 | 0.676 | 348 / 1,835 (19.0%) | 1,849 (20.1%) | 79.9% |
| Random Forest | Exploratory test | 9,200 | 0.509 | 0.557 | 688 / 1,835 (37.5%) | 1,288 (14.0%) | 86.0% |

The exploratory test drop is substantial. These results support a working software demo, not deployment quality or a strong accuracy claim.

## TabICLv2 CPU trial

The official TabICL implementation was tested at source revision `c91f00df184a5097e584cb376f7e699e9f3444c4`; the official `jingang/TabICL` checkpoint was fetched at repository revision `4dcd344ece2c00be9e831fdd35bed57b5ad83e19`. The 110,368,038-byte checkpoint SHA-256 is `bdc7dbd5e4ff21f8f0456fcf90c6b7cdf72dbea960f2d05b19bec19f9b3d4ed0`. Code and weight card declare BSD-3-Clause. The run used PyTorch `2.14.1+cpu`, one CPU thread, one estimator, and a 512-row context sampled only from training days.

TabICL used the same validation threshold-and-abstention search on its 256 deterministically spaced validation rows. The full run’s result assembly overwrote the stored operating point; a repeat with the same checkpoint, seeded context, and validation rows recovered threshold `0.61` with `0.025` abstention margin and reproduced the recorded confusion matrix and macro-F1. The test metrics use 256 deterministically spaced rows as well; RF and logistic metrics are reported on those same rows for comparison. On the validation sample, TabICL macro-F1 was 0.797 versus 0.843 for logistic on the same rows; TabICL occupancy recall was 0.597 (46/77) versus logistic’s 0.818. TabICL’s single-row CPU inference measured 537 ms on its first prediction and 524 ms median / 553 ms p95 warm. Peak process memory was about 712 MiB in the full run. Logistic was selected because it performed better on the matched validation sample and is roughly three orders of magnitude faster at warm single-row inference.

This was a bounded feasibility trial, not a full-dataset TabICL evaluation. The checkpoint remains in the local Hugging Face cache and is not distributed in this repository. Exact revisions, hashes, denominators, confusion matrices, versions, and latency samples are recorded in [evaluation.json](evaluation.json).

## Runtime and replay

The packaged logistic artifact SHA-256 is recorded in [manifest.json](manifest.json). On this machine, loading the model took 0.733 s, the first prediction took 2.94 ms, and warm single-row prediction took 0.172 ms median / 0.212 ms p95 over 100 calls.

`replay.json` contains 40 observations per CR1/CR2/CR3 drawn only from validation days. For a visibly varied demo, the offline exporter samples 20 rows from each validation truth class per stream with a fixed seed, then sorts them by their original timestamp. Labels are used only for that offline selection; the replay contains no labels or `Light`. The sparse timestamps are compressed into a short replay and do not represent a natural sampling cadence. The model produces ACTIVE, INACTIVE, and UNKNOWN outputs in each stream; each stream is a presentation copy of recorded office observations, not an independent room measurement.

## Temporal audit follow-up — issue #5

See [rolling-origin protocol and results](../benchmarks/occupancy/REPORT.md). Four complete-day rolling folds compared majority, CO2 rule, logistic and tree candidates; an offline Light-feature experiment is reported separately. All UCI results remain exploratory. No candidate was promoted and the shipped artifact, manifest, four-feature schema and replay remain unchanged. Independent campus-room sessions are unavailable, so campus generalization remains unvalidated and conservative UNKNOWN guards stay enabled.

Occupancy means human presence. Room use means an observed/requested session. Equipment demand means configured/requested watts. The office presence labels do not establish the other two quantities.
