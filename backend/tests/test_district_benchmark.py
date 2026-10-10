import json

import pytest


def test_benchmark_has_no_accepted_violations_and_optimizer_never_loses_after_gating(tmp_path):
    pytest.importorskip("power_grid_model")
    from benchmarks.run_district_recovery import main
    assert main(["--scenarios", "12", "--out", str(tmp_path)]) == 0
    report = json.loads((tmp_path / "district_recovery_report.json").read_text())
    assert all(row["accepted_invalid"] == 0 for row in report["summary"].values())
    by = {(r["seed"], r["method"]): r for r in report["runs"]}
    for seed in {r["seed"] for r in report["runs"]}:
        best = by[(seed, "optimized")]
        # Every gated baseline outcome lies in the optimizer's exhaustively searched, AC-validated domain.
        for method in ("no_reconfiguration", "first_benefit", "critical_first_greedy"):
            assert best["critical_unmet_wh"] <= by[(seed, method)]["critical_unmet_wh"]
    assert (tmp_path / "district_recovery_report.md").read_text().startswith("# District recovery benchmark")
