# Issue #19 delivery — multi-hypothesis diagnosis

## Implemented behavior

The telemetry diagnosis path calls the structured diagnostic engine. It can return simultaneous supported hypotheses, keeps severity separate from the uncalibrated evidence score, and abstains for missing, contradictory or observationally indistinguishable evidence. Campus and hospital responses carry the structured hypotheses; delivery tests cover simultaneous overload/cooling faults, contradictory readings, missing sensors, indistinguishable causes and deterministic ranking.

## Frozen held-out run

On 2026-10-10, the frozen `diag-bench-protocol-2` held-out split was unsealed and evaluated once. The protocol and manifest hashes are recorded with the benchmark fixtures; the exact per-family results and denominators are in [`diagnosis_heldout.md`](../backend/benchmarks/diagnosis/results/diagnosis_heldout.md) and [`diagnosis_heldout.json`](../backend/benchmarks/diagnosis/results/diagnosis_heldout.json). The run covers 48 synthetic scenarios (four per family), with truth unavailable during detector execution. It is developer-held-out, not independently blinded, and does not establish field accuracy.

Notable results: simultaneous overload-plus-cooling was detected in 4/4 scenarios with 6/6 correct claims; the stuck-sensor family was detected in 2/4 and had 2 misses. Safety violations were nonzero in several fault families (for example, 63 asset-steps for stuck sensors). These are reported as limitations rather than hidden or tuned away.

## Remaining before closure

The held-out runner currently serializes only the primary `code` and `status`, so the held-out artifact does not measure the issue's required ranked-hypothesis top-k performance. The report also does not evaluate hypothesis evolution in incident history. Do not retune against this revealed split; any tuning requires a new frozen held-out set and protocol version.

Issue #19 stays open until the frozen evaluation publishes rank/top-k and abstention results for the actual multi-hypothesis output and the history requirement is verified.
