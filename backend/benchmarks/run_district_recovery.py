"""Deterministic district restoration evaluation; run with PYTHONPATH=backend."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

from app.district.authority import DistrictAuthority
from benchmarks.district_recovery import act, assert_safe, radial_fixture

OUT = Path(__file__).with_name("results")


def cases():
    # Explicit fault/candidate universes: all 0/1/2 faults on each bounded tree.
    for shape in ("cached", "star", "chain"):
        factory = DistrictAuthority if shape == "cached" else lambda: radial_fixture(shape)
        prototype = factory()
        lines = sorted(edge["id"] for edge in prototype.topology["edges"] if edge["kind"] != "tie")
        for count in range(3):
            for faults in itertools.combinations(lines, count):
                yield f"{shape}:{','.join(faults) or 'normal'}", factory(), faults, None, None
    named = [
        ("feasible-with-unreachable-load", ("a", "load-4"), 6000, 6000, None, "tie-ab", None),
        ("loop", ("load-4", "load-5"), 6000, 6000, None, None, "loop"),
        ("no-benefit", ("a", "b"), 6000, 6000, ["tie-ab"], None, "does not increase"),
        ("source-overload", ("a", "load-4"), 4000, 6000, ["tie-ab"], None, "Source capacity"),
        ("branch-overload", ("a", "load-4"), 6000, 1000, ["tie-ab"], None, "Line capacity"),
        ("unreachable-source", ("trunk", "a"), 6000, 6000, None, None, "does not increase"),
        ("second-declared-tie", ("a", "b"), 6000, 6000, None, "tie-bc", None),
    ]
    for name, faults, capacity, rating, ties, expected, rejection in named:
        district = radial_fixture(source_capacity_w=capacity, tie_limit_w=rating)
        if ties is not None:
            district.topology["edges"] = [edge for edge in district.topology["edges"]
                                          if edge["kind"] != "tie" or edge["id"] in ties]
        yield name, district, faults, expected, rejection


def interval(district):
    assert_safe(district)
    states, loads = district._electrical_state()
    restoration = district._restoration(states)
    assert restoration["physical_confirmed_edge_id"] is None
    critical = [load for load in loads if load["tier"] == "critical"]
    return {"hour": district.hour, "duration_hours": 1,
            "candidate_edge_id": restoration["candidate_edge_id"],
            "applied_edge_id": restoration["applied_edge_id"],
            "physical_confirmed_edge_id": restoration["physical_confirmed_edge_id"],
            "requested_wh": sum(load["requested_w"] for load in loads),
            "unmet_wh": sum(load["unmet_w"] for load in loads),
            "critical_requested_wh": sum(load["requested_w"] for load in critical),
            "critical_unmet_wh": sum(load["unmet_w"] for load in critical)}


def evaluate_case(name, district, faults, expected, rejection):
    district.hour = 0
    digest = hashlib.sha256(json.dumps([district.topology, district.energy_trace["profile"],
                                       district.source_capacity_w], sort_keys=True).encode()).hexdigest()
    assert_safe(district)
    for edge in faults:
        assert act(district, "inject_fault", edge)
        assert_safe(district)  # Protective isolation checked in the same action.
        assert district.stable_evidence_count == 0
    tie_ids = sorted(edge["id"] for edge in district.topology["edges"] if edge["kind"] == "tie")
    evaluations = [{"edge_id": tie, "rejection": district._candidate_reason(tie)} for tie in tie_ids]
    assert act(district, "propose_recovery")
    candidate = district.candidate_tie
    proposal_reason = district.restoration_reason
    before = interval(district)
    assert district.closed_tie is None
    assert not act(district, "apply_recovery")
    for edge in faults:
        assert not act(district, "clear_fault", edge)
    intervals = [before]
    for _ in range(2):
        assert act(district, "advance_hour")
        intervals.append(interval(district))
    before_apply = sum(load["served_w"] for load in district._electrical_state()[1])
    accepted = act(district, "apply_recovery")
    assert_safe(district)
    if accepted:
        assert district.closed_tie == candidate and district.candidate_tie is None
        assert sum(load["served_w"] for load in district._electrical_state()[1]) > before_apply
        assert district.stable_evidence_count == 0
        for edge in faults:
            assert not act(district, "clear_fault", edge)
    else:
        assert district.closed_tie is None
    assert act(district, "advance_hour")
    intervals.append(interval(district))
    if expected is not None:
        assert accepted and district.closed_tie == expected
    if rejection is not None:
        assert not accepted and any(rejection in (item["rejection"] or "") for item in evaluations)
    metrics = {key: sum(row[key] for row in intervals) for key in
               ("requested_wh", "unmet_wh", "critical_requested_wh", "critical_unmet_wh")}
    metrics["unmet_fraction"] = metrics["unmet_wh"] / metrics["requested_wh"] if metrics["requested_wh"] else None
    metrics["critical_unmet_fraction"] = (metrics["critical_unmet_wh"] / metrics["critical_requested_wh"]
                                         if metrics["critical_requested_wh"] else None)
    return {"case": name, "input_sha256": digest, "fault_edges": list(faults),
            "declared_ties": tie_ids, "source_capacity_w": district.source_capacity_w,
            "candidate_evaluations": evaluations, "candidate_edge_id": candidate,
            "applied_edge_id": district.closed_tie,
            "physical_confirmed_edge_id": district._restoration({})["physical_confirmed_edge_id"],
            "accepted": accepted, "reason": proposal_reason,
            "intervals": intervals, "energy": metrics, "constraint_violations": 0}


def run():
    if not __debug__:
        raise RuntimeError("Stress assertions require Python without -O or PYTHONOPTIMIZE.")
    results, failures = [], []
    for name, district, faults, expected, rejection in cases():
        try:
            results.append(evaluate_case(name, district, faults, expected, rejection))
        except (AssertionError, KeyError, ValueError) as exc:
            failures.append({"case": name, "fault_edges": list(faults), "error": str(exc) or type(exc).__name__})
    return {"benchmark_version": "district-recovery-v1", "scope": "MODELED_ONLY",
            "boundary": "Cached pinned SHIFT graph plus generated SHIFT-schema radial fixtures; no new SHIFT execution.",
            "policy": "One applied tie at a time; require full connected grid request within ratings before restoration.",
            "horizon": "Four modeled one-hour intervals: faulted, evidence 1, evidence 2, outcome. No double counting.",
            "case_count": len(results) + len(failures), "passed": len(results), "failed": len(failures),
            "constraint_violations": sum(row["constraint_violations"] for row in results),
            "multi_fault_cases": sum(len(row["fault_edges"]) == 2 for row in results),
            "accepted": sum(row["accepted"] for row in results),
            "rejected": sum(not row["accepted"] for row in results),
            "failures": failures, "cases": results}


def markdown(report):
    lines = ["# District restoration stress evaluation", "",
             report["boundary"], "", report["policy"], "", report["horizon"], "",
             f"Cases: {report['case_count']}; passed: {report['passed']}; failed: {report['failed']}; "
             f"applied: {report['accepted']}; rejected: {report['rejected']}.",
             "Physical confirmation is null in every case. Ratings, faults and energy are synthetic.", "",
             "Reproduce: PYTHONPATH=backend python -m benchmarks.run_district_recovery.", "",
             "| Case | Applied tie | Critical unmet / requested Wh | Total unmet / requested Wh |",
             "|---|---|---:|---:|"]
    for row in report["cases"]:
        if row["case"].startswith(("cached:", "star:", "chain:")):
            continue
        energy = row["energy"]
        lines.append(f"| {row['case']} | {row['applied_edge_id'] or 'Rejected'} | "
                     f"{energy['critical_unmet_wh']} / {energy['critical_requested_wh']} | "
                     f"{energy['unmet_wh']} / {energy['requested_wh']} |")
    lines += ["", "Every case includes faults, declared ties, input digest, rejection explanations, "
              "four interval denominators and proposal/applied/physical fields in the JSON report.",
              "Assertions cover every injection and interval; loops, open-path service, flow conservation, "
              "source/line limits, immediate isolation and apply/clear gating. These are bounded regression "
              "results, not coverage of all topologies or physical feeder acceptance.", ""]
    if report["failures"]:
        lines.append(json.dumps(report["failures"], indent=2))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    report = run()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    header = json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2)
    rows = ",\n".join("    " + json.dumps(row, sort_keys=True) for row in report["cases"])
    (args.output_dir / "district_recovery_report.json").write_text(header[:-2] + ',\n  "cases": [\n' + rows + '\n  ]\n}\n')
    (args.output_dir / "district_recovery_report.md").write_text(markdown(report))
    print(json.dumps({key: report[key] for key in ("case_count", "passed", "failed", "accepted", "rejected", "multi_fault_cases", "constraint_violations")}))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
