# District restoration stress evaluation

Cached pinned SHIFT graph plus generated SHIFT-schema radial fixtures; no new SHIFT execution.

One applied tie at a time; require full connected grid request within ratings before restoration.

Four modeled one-hour intervals: faulted, evidence 1, evidence 2, outcome. No double counting.

Cases: 585; passed: 585; failed: 0; applied: 232; rejected: 353.
Physical confirmation is null in every case. Ratings, faults and energy are synthetic.

Reproduce: PYTHONPATH=backend python -m benchmarks.run_district_recovery.

| Case | Applied tie | Critical unmet / requested Wh | Total unmet / requested Wh |
|---|---|---:|---:|
| feasible-with-unreachable-load | tie-ab | 6000 / 12000 | 10000 / 24000 |
| loop | Rejected | 0 / 12000 | 8000 / 24000 |
| no-benefit | Rejected | 12000 / 12000 | 16000 / 24000 |
| source-overload | Rejected | 8000 / 12000 | 12000 / 24000 |
| branch-overload | Rejected | 8000 / 12000 | 12000 / 24000 |
| unreachable-source | Rejected | 12000 / 12000 | 24000 / 24000 |
| second-declared-tie | tie-bc | 11000 / 12000 | 14000 / 24000 |

Every case includes faults, declared ties, input digest, rejection explanations, four interval denominators and proposal/applied/physical fields in the JSON report.
Assertions cover every injection and interval; loops, open-path service, flow conservation, source/line limits, immediate isolation and apply/clear gating. These are bounded regression results, not coverage of all topologies or physical feeder acceptance.
