# Issue #19 delivery — multi-hypothesis diagnosis

## Implemented behavior

The telemetry diagnosis path calls the structured diagnostic engine. It can return simultaneous supported hypotheses, keeps severity separate from the uncalibrated evidence score, and abstains for missing, contradictory or observationally indistinguishable evidence. Campus and hospital responses carry the structured hypotheses; delivery tests cover simultaneous overload/cooling faults, contradictory readings, missing sensors, indistinguishable causes and deterministic ranking.

## Frozen held-out run

On 2026-10-10, the frozen `diag-bench-protocol-2` held-out split was unsealed and evaluated once. The protocol and manifest hashes are recorded with the benchmark fixtures; the exact per-family results and denominators are in [`diagnosis_heldout.md`](../backend/benchmarks/diagnosis/results/diagnosis_heldout.md) and [`diagnosis_heldout.json`](../backend/benchmarks/diagnosis/results/diagnosis_heldout.json). The run covers 48 synthetic scenarios (four per family), with truth unavailable during detector execution. It is developer-held-out, not independently blinded, and does not establish field accuracy.

Notable results: simultaneous overload-plus-cooling was detected in 4/4 scenarios with 6/6 correct claims; the stuck-sensor family was detected in 2/4 and had 2 misses. Safety violations were nonzero in several fault families (for example, 63 asset-steps for stuck sensors). These are reported as limitations rather than hidden or tuned away.

## Ranked held-out runs

`diag-bench-ranked-v1` (seeds 3000–3007) was unsealed once on 2026-10-10 with the detector of that time; its report is kept unchanged in [`diagnosis_ranked_heldout.md`](../backend/benchmarks/diagnosis/results/diagnosis_ranked_heldout.md). The stuck-sensor rule changed afterwards, and `diag-bench-ranked-v2` (seeds 4000–4007) was frozen against a working-tree detector that changed again before it was ever run, so its recorded detector hash matches no committed detector and it can no longer be unsealed. It was never evaluated.

`diag-bench-ranked-v3` (seeds 5000–5007, same held-out regime) was generated and committed with the current detector hash (`04864dc3…`) before being run, then unsealed once with no rule changes in between. Results: [`diagnosis_ranked_v3_heldout.md`](../backend/benchmarks/diagnosis/results/diagnosis_ranked_v3_heldout.md) and `.json`. 96 scenarios, 8 per family:

- Every fault family detected 8/8 with no false alarms, location errors or safety violations.
- Top-1 = top-3 = MRR = 1.0 on every family that should produce a ranked cause (80 ranked cases), including 8/8 simultaneous overload-plus-cooling cases with 16/16 correct candidates.
- Sensor dropout and stuck sensor are expected to abstain: abstention precision and recall are 1.0 (8/8) for both. Stuck-sensor cases therefore have no ranked cause, so their top-k row reads 0/8 by construction.
- Coverage is 0.77 (dropout) and 0.82 (stuck sensor) because those asset-steps abstain.

Incident history: campus hypotheses open, update and resolve `Incident` rows and emit `INCIDENT_OPENED`, `INCIDENT_RESOLVED` and `DIAGNOSIS_UPDATED` events carrying the ranked list (`backend/app/core/state.py`, covered by `backend/tests/test_history.py`).

## Limitations

Synthetic telemetry only; developer-held-out with no independent custodian; scores are uncalibrated evidence, not probabilities. Held-out v3 is now revealed: any retuning needs a new frozen set and protocol version.
