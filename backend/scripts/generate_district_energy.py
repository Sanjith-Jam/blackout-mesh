"""Freeze one synthetic 24-hour district energy trace using CityLearn's Battery.

Run with the pinned local checkout: PYTHONPATH=sources/CityLearn .venv-citylearn/bin/python
backend/scripts/generate_district_energy.py
"""
from __future__ import annotations

import inspect
import json
import subprocess
from pathlib import Path

from citylearn.base import EpisodeTracker
from citylearn.energy_model import Battery


CITYLEARN_SHA = "834575c1a0194c8ae9d648ae858376a94dfceb78"
OUTPUT = Path(__file__).resolve().parents[1] / "app/district/data/gnitc_energy.json"
DEMAND_W = [4200, 4000, 3900, 3800, 3900, 4300, 5200, 6100, 6500, 6700, 7000, 7200,
            7400, 7200, 6900, 6800, 7000, 7600, 7800, 7200, 6200, 5500, 4900, 4500]
PV_W = [0, 0, 0, 0, 0, 300, 900, 1800, 3200, 4800, 7000, 8500,
        9000, 8500, 7600, 6200, 4100, 1800, 300, 0, 0, 0, 0, 0]


def generate() -> dict:
    source = Path(inspect.getfile(Battery)).resolve().parents[1]
    actual_sha = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if actual_sha != CITYLEARN_SHA:
        raise RuntimeError(f"CityLearn checkout is {actual_sha}, expected {CITYLEARN_SHA}")

    tracker = EpisodeTracker(0, 23)
    tracker.next_episode(24, False, False, 0)
    battery = Battery(capacity=12.0, nominal_power=2.0, initial_soc=0.0,
                      efficiency=0.9, loss_coefficient=0.0, capacity_loss_coefficient=0.0,
                      power_efficiency_curve=[[0.0, 0.9], [1.0, 0.9]],
                      capacity_power_curve=[[0.0, 1.0], [1.0, 1.0]],
                      depth_of_discharge=1.0, episode_tracker=tracker,
                      seconds_per_time_step=3600, time_step_ratio=1.0, random_seed=0)
    battery.reset()
    rows = []
    initial_soc_wh = round(battery.energy_init * 1000)
    for hour, (demand_w, pv_w) in enumerate(zip(DEMAND_W, PV_W, strict=True)):
        baseline_grid_w = max(0, demand_w - pv_w)
        # Charge only from PV otherwise curtailed; discharge only against unmet demand.
        request_wh = (min(1500, max(0, pv_w - demand_w)) if 9 <= hour <= 15 else
                      -min(1500, baseline_grid_w) if 17 <= hour <= 21 else 0)
        soc_before_wh = round(battery.energy_init * 1000)
        battery.charge(request_wh / 1000)
        realized_wh = round(float(battery.energy_balance[hour]) * 1000)
        charge_w, discharge_w = max(0, realized_wh), max(0, -realized_wh)
        soc_wh = round(float(battery.soc[hour]) * 12000)
        pv_used_w = min(pv_w, demand_w + charge_w)
        grid_import_w = demand_w + charge_w - pv_used_w - discharge_w
        loss_wh = realized_wh - (soc_wh - soc_before_wh)
        assert 0 <= grid_import_w and 0 <= soc_wh <= 12000 and loss_wh >= 0
        assert charge_w <= max(0, pv_w - demand_w) and discharge_w <= baseline_grid_w
        assert grid_import_w + pv_used_w + discharge_w == demand_w + charge_w
        rows.append({"hour": hour, "demand_w": demand_w, "pv_w": pv_w,
                     "baseline_grid_w": baseline_grid_w, "dispatch_grid_w": grid_import_w,
                     "battery_soc_wh": soc_wh, "pv_used_w": pv_used_w,
                     "battery_charge_w": charge_w, "battery_discharge_w": discharge_w,
                     "grid_import_w": grid_import_w, "loss_wh": loss_wh})
        if hour < 23:
            battery.next_time_step()

    assert sum(r["battery_charge_w"] - r["battery_discharge_w"] - r["loss_wh"] for r in rows) == rows[-1]["battery_soc_wh"] - initial_soc_wh
    return {"schema_version": "district-energy-v1", "engine": "CityLearn Battery",
            "engine_version": CITYLEARN_SHA, "source_commit": CITYLEARN_SHA,
            "provenance": "CITYLEARN_EXECUTED_ON_SYNTHETIC_DEMO_INPUTS",
            "assumptions": "24 one-hour synthetic demand/PV samples; fixed 0.9 modeled round-trip efficiency (about 0.949 per direction), no standing loss or degradation; PV-surplus charging and load-only discharge; no grid export or RL policy.",
            "battery": {"capacity_wh": 12000, "power_w": 2000, "initial_soc_wh": initial_soc_wh,
                        "round_trip_efficiency": 0.9},
            "profile": rows,
            "totals": {"demand_wh": sum(r["demand_w"] for r in rows),
                       "baseline_import_wh": sum(r["baseline_grid_w"] for r in rows),
                       "dispatch_import_wh": sum(r["dispatch_grid_w"] for r in rows),
                       "battery_loss_wh": sum(r["loss_wh"] for r in rows),
                       "pv_curtailed_wh": sum(r["pv_w"] - r["pv_used_w"] for r in rows)}}


if __name__ == "__main__":
    result = generate()
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}: {len(result['profile'])} hours, baseline {result['totals']['baseline_import_wh']} Wh, dispatch {result['totals']['dispatch_import_wh']} Wh")
