from benchmarks.run_district_recovery import run


def test_bounded_stress_report_is_repeatable_and_preserves_denominators():
    first = run()
    assert first == run()
    assert first["case_count"] == first["passed"] == 585
    assert first["failed"] == first["constraint_violations"] == 0
    assert first["multi_fault_cases"] == 532
    assert first["accepted"] > 0 and first["rejected"] > 0
    named = {row["case"]: row for row in first["cases"] if ":" not in row["case"]}
    assert named["second-declared-tie"]["applied_edge_id"] == "tie-bc"
    assert named["unreachable-source"]["energy"]["critical_unmet_wh"] > 0
    for row in first["cases"]:
        assert row["physical_confirmed_edge_id"] is None
        energy = row["energy"]
        assert energy["requested_wh"] > 0 and energy["critical_requested_wh"] > 0
        assert 0 <= energy["critical_unmet_wh"] <= energy["critical_requested_wh"]
        assert 0 <= energy["unmet_wh"] <= energy["requested_wh"]
        assert energy["unmet_wh"] == sum(interval["unmet_wh"] for interval in row["intervals"])
        assert energy["critical_unmet_wh"] == sum(interval["critical_unmet_wh"] for interval in row["intervals"])
        assert len(row["intervals"]) == 4


def test_optimized_python_cannot_disable_the_safety_checks(tmp_path):
    import subprocess
    import sys
    result = subprocess.run([sys.executable, "-O", "-m", "benchmarks.run_district_recovery",
                             "--output-dir", str(tmp_path)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "Stress assertions require Python without -O" in result.stderr
    assert not (tmp_path / "district_recovery_report.json").exists()
