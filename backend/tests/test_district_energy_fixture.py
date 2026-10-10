"""The frozen CityLearn trace has physical accounting, not just plausible charts."""
import json
from pathlib import Path


def test_district_energy_fixture_conserves_power_and_storage():
    data = json.loads((Path(__file__).resolve().parents[1] / "app/district/data/gnitc_energy.json").read_text())
    rows = data["profile"]
    assert data["source_commit"] == "834575c1a0194c8ae9d648ae858376a94dfceb78"
    assert len(rows) == 24 and [r["hour"] for r in rows] == list(range(24))
    soc = data["battery"]["initial_soc_wh"]
    for r in rows:
        assert all(type(r[k]) is int for k in ("demand_w", "pv_w", "baseline_grid_w", "dispatch_grid_w",
                                                "battery_soc_wh", "pv_used_w", "battery_charge_w", "battery_discharge_w", "loss_wh"))
        assert r["baseline_grid_w"] == max(0, r["demand_w"] - r["pv_w"])
        assert r["grid_import_w"] == r["dispatch_grid_w"] >= 0
        assert r["grid_import_w"] + r["pv_used_w"] + r["battery_discharge_w"] == r["demand_w"] + r["battery_charge_w"]
        assert r["battery_charge_w"] <= max(0, r["pv_w"] - r["demand_w"])
        assert r["battery_discharge_w"] <= r["baseline_grid_w"]
        assert r["battery_charge_w"] - r["battery_discharge_w"] == r["battery_soc_wh"] - soc + r["loss_wh"]
        assert 0 <= r["battery_soc_wh"] <= data["battery"]["capacity_wh"] and r["loss_wh"] >= 0
        soc = r["battery_soc_wh"]
    assert any(r["battery_charge_w"] > 0 for r in rows)
    assert any(r["battery_discharge_w"] > 0 for r in rows)
    assert data["totals"]["dispatch_import_wh"] == sum(r["dispatch_grid_w"] for r in rows)
