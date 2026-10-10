"""Run the allocation benchmark and write JSON + Markdown reports (#20).

    PYTHONPATH=backend python -m benchmarks.run_allocation            # from repository root
"""
from __future__ import annotations

import json
import statistics
import subprocess
import sys
from pathlib import Path

from benchmarks.allocation import run_benchmark

OUT = Path(__file__).resolve().parent / "results"
METRICS = ("critical_unmet_wh", "essential_unmet_wh", "occupied_service_fraction", "worst_room_starvation_s",
           "switching_count", "recovery_latency_s_max", "constraint_violations")
FOCUS = "proposed[validation_rates]"


def mean(values):
    values = [v for v in values if v is not None]
    return round(statistics.fmean(values), 3) if values else None


def summarize(report: dict) -> dict:
    table, paired = {}, {}
    for run in report["runs"]:
        table.setdefault((run["scenario"], run["policy"]), []).append(run)
    summary = {f"{s}|{p}": {m: mean(r[m] for r in runs) for m in METRICS} | {"n_seeds": len(runs)}
               for (s, p), runs in table.items()}
    by_key = {(r["scenario"], r["seed"], r["policy"]): r for r in report["runs"]}
    for scenario in report["scenarios"]:
        for policy in {r["policy"] for r in report["runs"]}:
            if policy == FOCUS:
                continue
            diffs = {m: [] for m in METRICS}
            for seed in report["seeds"]:
                a, b = by_key[(scenario, seed, FOCUS)], by_key[(scenario, seed, policy)]
                for m in METRICS:
                    if a[m] is not None and b[m] is not None:
                        diffs[m].append(a[m] - b[m])
            paired[f"{scenario}|{policy}"] = {m: {"mean": mean(v), "min": min(v) if v else None,
                                                  "max": max(v) if v else None, "n": len(v)} for m, v in diffs.items()}
    return {"summary": summary, "paired_vs_focus": paired}


def markdown(report: dict, derived: dict, commit: str) -> str:
    lines = [f"# Allocation benchmark ({report['benchmark_version']})", "",
             f"Commit `{commit}` · safety policy `{report['safety_policy_version']}` · {len(report['seeds'])} seeds per scenario · "
             f"{report['duration_s']:.0f} s per run at {report['step_s']:.0f} s steps. Simulated outcomes only: "
             "watt-hours integrate modeled power over simulated time and are not measured savings.", "",
             "Reproduce: `PYTHONPATH=backend python -m benchmarks.run_allocation` from the repository root.", "",
             "Policies: `fixed_priority` (L0→L5), `essentials_first_no_ml` (critical, booked rooms, pump), "
             "`round_robin` (critical, then least-recently-served optional), `proposed[...]` (classifier → ActivityGuard → "
             "exact allocator) with each classifier variant and an always-UNKNOWN no-ML ablation, and "
             "`oracle_occupancy_upper_bound`, which reads true occupancy and is **not deployable**.", "",
             "Every run of a scenario/seed has the same input digest (capacity, feeders, bookings, classifier outputs); "
             "true occupancy is used only by the evaluator.", ""]
    order = ("fixed_priority", "round_robin", "essentials_first_no_ml", "proposed[no_ml_unknown]",
             "proposed_no_dwell[validation_rates]", "proposed[validation_rates]", "proposed_no_dwell[heavy_errors]",
             "proposed[heavy_errors]", "proposed[perfect]", "oracle_occupancy_upper_bound")
    for scenario in ("shortage_6kw", "recovery_chatter"):
        if scenario not in report["scenarios"]:
            continue
        rows = {p: derived["summary"].get(f"{scenario}|{p}") for p in order}
        lines += [f"## Ablation summary: {scenario}", "",
                  "Same inputs for every row. `proposed_no_dwell` is the classifier path without rank hysteresis; "
                  "`proposed` adds `RankDwell` (a changed state must repeat on 3 readings). The oracle row bounds what "
                  "any occupancy signal could add here.", "",
                  "| Policy | Occupied service | Switches | Essential unmet Wh | Critical unmet Wh |", "|---|---:|---:|---:|---:|"]
        for p, row in rows.items():
            if row:
                lines.append(f"| {p} | {row['occupied_service_fraction']:.1%} | {row['switching_count']:.1f} | "
                             f"{row['essential_unmet_wh']:.1f} | {row['critical_unmet_wh']:.1f} |")
        base, oracle = rows["essentials_first_no_ml"], rows["oracle_occupancy_upper_bound"]
        if base and oracle:
            lines += ["", f"Headroom for occupancy evidence in this scenario: the non-deployable oracle serves occupied rooms "
                          f"{oracle['occupied_service_fraction'] - base['occupied_service_fraction']:+.1%} versus "
                          "essentials-first without ML. Any classifier gain is bounded by that.", ""]
    for scenario in report["scenarios"]:
        lines += [f"## {scenario}", "",
                  "| Policy | Critical unmet Wh | Essential unmet Wh | Occupied service | Worst starvation s | Switches | Recovery s (max) | Violations |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for key, row in sorted(derived["summary"].items()):
            s, p = key.split("|")
            if s != scenario:
                continue
            frac = "—" if row["occupied_service_fraction"] is None else f"{row['occupied_service_fraction']:.1%}"
            rec = "—" if row["recovery_latency_s_max"] is None else f"{row['recovery_latency_s_max']:.0f}"
            lines.append(f"| {p} | {row['critical_unmet_wh']:.1f} | {row['essential_unmet_wh']:.1f} | {frac} | "
                         f"{row['worst_room_starvation_s']:.0f} | {row['switching_count']:.1f} | {rec} | {row['constraint_violations']:.0f} |")
        lines.append("")
    lines += [f"## Paired differences: {FOCUS} minus each other policy (mean over seeds, [min, max])", "",
              "Negative is better for unmet Wh, starvation, switches and recovery; positive is better for occupied service.", "",
              "| Scenario | vs policy | Δ critical unmet Wh | Δ essential unmet Wh | Δ occupied service | Δ worst starvation s | Δ switches |",
              "|---|---|---:|---:|---:|---:|---:|"]
    fmt = lambda d: "—" if d["mean"] is None else f"{d['mean']:+.3g} [{d['min']:+.3g}, {d['max']:+.3g}]"
    for key, d in sorted(derived["paired_vs_focus"].items()):
        s, p = key.split("|")
        lines.append(f"| {s} | {p} | {fmt(d['critical_unmet_wh'])} | {fmt(d['essential_unmet_wh'])} | "
                     f"{fmt(d['occupied_service_fraction'])} | {fmt(d['worst_room_starvation_s'])} | {fmt(d['switching_count'])} |")
    return "\n".join(lines) + "\n"


def main():
    report = run_benchmark()
    derived = summarize(report)
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"
    except OSError:
        commit = "unknown"
    OUT.mkdir(exist_ok=True)
    (OUT / "allocation_report.json").write_text(json.dumps({**report, **derived, "commit": commit}, indent=1), encoding="utf-8")
    (OUT / "allocation_report.md").write_text(markdown(report, derived, commit), encoding="utf-8")
    unsafe = sum(r["constraint_violations"] for r in report["runs"])
    print(f"{len(report['runs'])} runs, {unsafe} constraint violations; wrote {OUT}")
    return 1 if unsafe else 0


if __name__ == "__main__":
    sys.exit(main())
