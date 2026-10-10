"""Same-input district recovery benchmark (#71 step 3). Synthetic graphs only.

    PYTHONPATH=backend python -m benchmarks.run_district_recovery [--scenarios 120]   # from repository root

Every method sees identical topology, loads, faults and candidate ties, and every proposal passes
through the same unbalanced AC gate. A rejected proposal falls back to the current switches.
Exits non-zero if any *accepted* plan violates a declared constraint.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

from app.district import electrical
from app.district.profile import DistrictProfile
from app.district.recovery import config_problem, critical_served_w, evaluate, optimize

OUT = Path(__file__).resolve().parent / "results"
PROTOCOL = {"version": "district-recovery-v1", "seed_base": 7100, "scenarios": 120, "bootstrap_draws": 2000,
            "interval_hours": 1, "objective": "lexicographic critical served W, served W, switching actions, tie IDs",
            "gate": "unbalanced three-phase AC (power-grid-model), declared synthetic parameters",
            "frozen_before_measurement": True}
METHODS = ("no_reconfiguration", "first_benefit", "critical_first_greedy", "optimized")
PARAMS = electrical.load_params(Path(electrical.__file__).with_name("data") / "gnitc_electrical.json")


def scenario(seed):
    """Radial 400 V tree, 1-4 declared ties (some long), 1-2 line faults, low or high demand, some phase imbalance."""
    rng = random.Random(seed)
    count = rng.randint(3, 12)
    names = [f"L{i:02d}" for i in range(count)]
    nodes = [{"id": "S", "role": "source", "voltage_v": 400}]
    edges = []
    for index, name in enumerate(names):
        parent = "S" if index == 0 or rng.random() < .25 else names[rng.randrange(index)]
        amps = rng.choice([60, 100, 160])
        edges.append({"id": f"e{index:02d}", "from": parent, "to": name, "kind": "branch", "component_type": "DistributionBranchBase",
                      "voltage_v": 400, "length_m": float(rng.randint(20, 120)), "rating_a": amps,
                      "limit_w": int(math.sqrt(3) * 400 * amps), "normally_open": False})
    for index in range(rng.randint(1, 4)):
        a, b = rng.sample(names, 2)
        amps = rng.choice([40, 100])
        edges.append({"id": f"tie:{index}", "from": a, "to": b, "kind": "tie", "component_type": "DistributionBranchBase",
                      "voltage_v": 400, "length_m": float(rng.choice([60, 150, 900, 1600])), "rating_a": amps,
                      "limit_w": int(math.sqrt(3) * 400 * amps), "normally_open": True})
    for name in names:
        nodes.append({"id": name, "role": "load", "voltage_v": 400, "building_id": name})
    high = rng.random() < .5
    loads = {name: rng.randint(2_000, 25_000 if high else 9_000) for name in names}
    critical = set(rng.sample(names, max(1, count // 4)))
    capacity = int(sum(loads.values()) * rng.uniform(.6, 1.1))
    profile = DistrictProfile.model_validate({
        "schema_version": "district-profile-v1", "id": f"bench-{seed}", "provenance": "CONFIGURED_SIMULATED_ASSUMPTION",
        "source_capacity_w": capacity, "loss_reserve_w": max(50, capacity // 50), "demand_basis": "hourly_trace_weights",
        "local_supply_mode": "grid_following",
        "buildings": [{"building_id": n, "tier": "critical" if n in critical else "noncritical", "rationale": "benchmark",
                       "demand_weight": w} for n, w in sorted(loads.items())]})
    total = sum(loads.values())
    trace = {"provenance": "BENCHMARK_SYNTHETIC", "profile": [{"demand_w": total, "grid_import_w": total}]}
    splits = {n: (.6, .2, .2) for n in names if rng.random() < .2}
    faults = set(rng.sample([f"e{i:02d}" for i in range(count)], rng.randint(1, min(2, count))))
    return {"seed": seed, "size": count, "ties": sum(e["kind"] == "tie" for e in edges), "faults": sorted(faults),
            "high_demand": high, "imbalanced_loads": len(splits)}, {"nodes": nodes, "edges": edges}, profile, trace, faults, splits


def served_key(profile, loads):
    return (critical_served_w(profile, loads), sum(load["served_w"] for load in loads))


def propose(method, topology, profile, trace, faults, params):
    ties = sorted(e["id"] for e in topology["edges"] if e["kind"] == "tie")
    current = frozenset()
    if method == "no_reconfiguration":
        return current
    if method == "first_benefit":
        _, base, _ = evaluate(topology, profile, trace, 0, faults, current)
        for tie in ties:
            if not config_problem(topology, faults, frozenset({tie})):
                _, loads, _ = evaluate(topology, profile, trace, 0, faults, frozenset({tie}))
                if sum(l["served_w"] for l in loads) > sum(l["served_w"] for l in base):
                    return frozenset({tie})
        return current
    if method == "critical_first_greedy":
        # Conventional greedy restoration: repeatedly close the single tie with the largest
        # (critical, total) gain while the network stays radial.
        chosen = current
        while True:
            _, base, _ = evaluate(topology, profile, trace, 0, faults, chosen)
            best, best_key = None, served_key(profile, base)
            for tie in ties:
                trial = chosen | {tie}
                if tie in chosen or config_problem(topology, faults, trial):
                    continue
                key = served_key(profile, evaluate(topology, profile, trace, 0, faults, trial)[1])
                if key > best_key:
                    best, best_key = trial, key
            if best is None:
                return chosen
            chosen = best
    result = optimize(topology, profile, trace, 0, faults, current, params, electrical.check)
    return None if result["candidate_edge_ids"] is None else frozenset(result["candidate_edge_ids"])


def accepted_violations(topology, profile, faults, config, states, loads):
    """Independent check of an accepted plan; must be empty for every accepted result."""
    problems = []
    if config_problem(topology, faults, config):
        problems.append("not radial / not permitted")
    limits = {e["id"]: e["limit_w"] for e in topology["edges"]}
    problems += [f"{k} over limit" for k, s in states.items() if s["flow_w"] > limits[k]]
    problems += [f"{k} flow across known open edge" for k, s in states.items() if s["faulted"] and s["flow_w"]]
    if sum(l["grid_served_w"] for l in loads) > profile.source_capacity_w - profile.loss_reserve_w:
        problems.append("source budget exceeded")
    problems += [f"{l['building_id']} served above request" for l in loads if l["served_w"] > l["requested_w"]]
    return problems


def run_one(seed):
    meta, topology, profile, trace, faults, splits = scenario(seed)
    params = PARAMS.model_copy(update={"phase_split": splits})
    rows = []
    for method in METHODS:
        started = time.perf_counter()
        proposal = propose(method, topology, profile, trace, faults, params)
        gate = None
        if proposal is not None:
            states, loads, _ = evaluate(topology, profile, trace, 0, faults, proposal)
            gate = electrical.check(topology, params, {l["building_id"]: l["grid_served_w"] for l in loads}, states, profile.source_capacity_w)
        accepted = proposal if gate and gate["status"] == "PASSED" else frozenset()
        states, loads, _ = evaluate(topology, profile, trace, 0, faults, accepted)
        latency_ms = (time.perf_counter() - started) * 1000
        requested_critical = sum(l["requested_w"] for l in loads if l["tier"] == "critical")
        critical = critical_served_w(profile, loads)
        rows.append({**meta, "method": method, "proposed_edge_ids": sorted(proposal) if proposal is not None else None,
                     "gate_status": gate["status"] if gate else "NO_PROPOSAL",
                     "gate_reasons": sorted({v["limit"] for v in gate["violations"]}) if gate else [],
                     "proposed_invalid": int(bool(gate) and gate["status"] != "PASSED" and bool(proposal)),
                     "accepted_edge_ids": sorted(accepted), "switching_count": len(accepted),
                     "critical_unmet_wh": (requested_critical - critical) * PROTOCOL["interval_hours"],
                     "total_unmet_wh": sum(l["unmet_w"] for l in loads) * PROTOCOL["interval_hours"],
                     "served_critical_fraction": round(critical / requested_critical, 4) if requested_critical else None,
                     "accepted_violations": accepted_violations(topology, profile, faults, accepted, states, loads),
                     "latency_ms": round(latency_ms, 3)})
    return rows


def bootstrap(diffs, draws, seed):
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(diffs, k=len(diffs))) for _ in range(draws))
    return [round(means[int(.025 * draws)], 1), round(means[int(.975 * draws) - 1], 1)]


def summarize(rows, protocol):
    by = {(r["seed"], r["method"]): r for r in rows}
    seeds = sorted({r["seed"] for r in rows})
    summary = {}
    for method in METHODS:
        mine = [by[(s, method)] for s in seeds]
        latency = sorted(r["latency_ms"] for r in mine)
        summary[method] = {
            "n": len(mine), "critical_unmet_wh_total": sum(r["critical_unmet_wh"] for r in mine),
            "total_unmet_wh_total": sum(r["total_unmet_wh"] for r in mine),
            "mean_switching_count": round(statistics.fmean(r["switching_count"] for r in mine), 3),
            "proposed_invalid": sum(r["proposed_invalid"] for r in mine),
            "accepted_invalid": sum(bool(r["accepted_violations"]) for r in mine),
            "latency_ms_p50": latency[len(latency) // 2], "latency_ms_p95": latency[min(len(latency) - 1, int(.95 * len(latency)))]}
    paired = {}
    for method in METHODS[:-1]:
        crit = [by[(s, method)]["critical_unmet_wh"] - by[(s, "optimized")]["critical_unmet_wh"] for s in seeds]
        total = [by[(s, method)]["total_unmet_wh"] - by[(s, "optimized")]["total_unmet_wh"] for s in seeds]
        paired[f"{method}_minus_optimized"] = {
            "critical_unmet_wh_mean": round(statistics.fmean(crit), 1),
            "critical_unmet_wh_ci95": bootstrap(crit, protocol["bootstrap_draws"], protocol["seed_base"]),
            "total_unmet_wh_mean": round(statistics.fmean(total), 1),
            "total_unmet_wh_ci95": bootstrap(total, protocol["bootstrap_draws"], protocol["seed_base"] + 1),
            "scenarios_optimized_better_critical": sum(d > 0 for d in crit),
            "scenarios_optimized_worse_critical": sum(d < 0 for d in crit),
            "scenarios_tied_critical": sum(d == 0 for d in crit)}
    return summary, paired


def markdown(report):
    lines = ["# District recovery benchmark", "",
             "Synthetic radial 400 V graphs only. This compares methods on identical modeled inputs; it is not field "
             "evidence, not a real-grid safety result and not a savings claim.", "",
             f"Protocol `{report['protocol']['version']}` frozen before measurement; {report['protocol']['scenarios']} "
             f"scenarios, seeds {report['protocol']['seed_base']}+i; engine {report['engine']}.", "",
             "| Method | n | Critical unmet Wh | Total unmet Wh | Mean switches | Proposed invalid | Accepted invalid | p50 ms | p95 ms |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for method, row in report["summary"].items():
        lines.append(f"| {method} | {row['n']} | {row['critical_unmet_wh_total']:,} | {row['total_unmet_wh_total']:,} | "
                     f"{row['mean_switching_count']} | {row['proposed_invalid']} | {row['accepted_invalid']} | "
                     f"{row['latency_ms_p50']} | {row['latency_ms_p95']} |")
    lines += ["", "Paired differences (baseline minus optimized; positive means the optimizer left less unmet energy), "
              "bootstrap 95% intervals:", "", "| Comparison | Critical Wh mean [CI] | Total Wh mean [CI] | Better / tied / worse (critical) |",
              "|---|---|---|---|"]
    for name, row in report["paired"].items():
        lines.append(f"| {name} | {row['critical_unmet_wh_mean']:,} {row['critical_unmet_wh_ci95']} | {row['total_unmet_wh_mean']:,} "
                     f"{row['total_unmet_wh_ci95']} | {row['scenarios_optimized_better_critical']} / {row['scenarios_tied_critical']} / "
                     f"{row['scenarios_optimized_worse_critical']} |")
    lines += ["", "Not covered: PV/storage limits, incomplete sensors, multi-interval trajectories, protection, inrush and "
              "transients. Latency is single-process host time and includes AC gating.",
              "", f"Reproduce: `{report['command']}` from the repository root."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=int, default=PROTOCOL["scenarios"])
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    try:
        engine = f"power-grid-model {electrical.version('power-grid-model')}"
    except electrical.PackageNotFoundError:
        print("power-grid-model is required (backend/requirements-electrical.txt)", file=sys.stderr)
        return 2
    protocol = {**PROTOCOL, "scenarios": args.scenarios}
    rows = [row for i in range(args.scenarios) for row in run_one(protocol["seed_base"] + i)]
    summary, paired = summarize(rows, protocol)
    report = {"protocol": protocol, "engine": engine, "summary": summary, "paired": paired, "runs": rows,
              "command": "PYTHONPATH=backend python -m benchmarks.run_district_recovery"}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "district_recovery_report.json").write_text(json.dumps(report, indent=1) + "\n")
    (args.out / "district_recovery_report.md").write_text(markdown(report))
    print(markdown(report))
    return 1 if any(row["accepted_invalid"] for row in summary.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
