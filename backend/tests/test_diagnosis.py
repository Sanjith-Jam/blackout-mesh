"""Telemetry-derived fault inference (#4)."""
import ast
import math
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

import app.simulation.sensors as sim
from app.diagnosis.infer import (CONFIRM_SAMPLES, FeederRating, ObservationWindow, TransformerRating,
                                 diagnose_campus, diagnose_transformer)
from app.diagnosis.observations import ObservationError, validate
from app.visualizers import HospitalTelemetry

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
DIAGNOSIS_DIR = pathlib.Path(__file__).resolve().parents[1] / "app" / "diagnosis"
FORBIDDEN = ("app.simulation", "app.core.state", "app.core.site", "app.visualizers", "app.main")


def feed(window, readings, samples=CONFIRM_SAMPLES, start=1, now=NOW, step=0.25):
    for k in range(samples):
        at = now - timedelta(seconds=step * (samples - 1 - k))
        for raw in sim.envelopes(readings, start + k, at):
            window.add(validate(raw, set(readings), now))


def tx(**overrides):
    values = dict(zip(sim.TRANSFORMER_FIELDS, sim.NORMAL_SENSORS))
    values.update(overrides)
    return values


def run_hospital(readings, peers=True):
    window = ObservationWindow()
    feed(window, readings)
    rating = TransformerRating()
    low = {a: v["input_voltage_v"] is not None and v["output_voltage_v"] is not None
           and v["input_voltage_v"] < rating.low_input_v and v["output_voltage_v"] < rating.dead_output_v
           for a, v in readings.items()}
    return {a: diagnose_transformer(window, a, rating, NOW, low if peers else None) for a in readings}


# ---- boundary ---------------------------------------------------------------------------

def test_diagnosis_package_never_imports_scenario_truth():
    for path in DIAGNOSIS_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith(FORBIDDEN), f"{path.name} imports {name}"
        source = path.read_text(encoding="utf-8")
        for fixture in ("HOSPITAL_FAULT_FIXTURES", "UPSTREAM_LOSS_SENSORS", "feeder_available", "source_capacity_w"):
            assert fixture not in source, f"{path.name} mentions {fixture}"


def test_campus_state_does_not_read_flags_for_diagnosis():
    state = (DIAGNOSIS_DIR.parent / "core" / "state.py").read_text(encoding="utf-8")
    body = state.split("def compute_fault_diagnosis", 1)[1].split("\n    def ", 1)[0]
    assert "feeder_available" not in body  # flags only reach diagnosis through synthesized telemetry
    assert "diagnose_campus(self.telemetry_window" in body


# ---- labels vs telemetry ----------------------------------------------------------------

def test_relabelled_scenarios_with_identical_telemetry_give_identical_diagnoses(monkeypatch):
    original = sim.hospital_readings("overload", "Theatre")
    swapped = dict(sim.HOSPITAL_FAULT_FIXTURES)
    swapped["cooling_failure"], swapped["overload"] = swapped["overload"], swapped["cooling_failure"]
    monkeypatch.setattr(sim, "HOSPITAL_FAULT_FIXTURES", swapped)
    relabelled = sim.hospital_readings("cooling_failure", "Theatre")
    assert relabelled == original
    assert run_hospital(relabelled) == run_hospital(original)


def test_same_label_different_telemetry_follows_the_telemetry():
    readings = sim.hospital_readings("normal", "Theatre")
    assert run_hospital(readings)["TX2"]["code"] == "NORMAL"
    readings["TX2"]["current_a"] = 130.0
    assert run_hospital(readings)["TX2"]["code"] == "OVERLOAD"


# ---- hypotheses --------------------------------------------------------------------------

def test_cooling_failure_at_normal_current():
    d = run_hospital({"TX": tx(temperature_c=91.0, cooling_ok=False)})["TX"]
    assert d["code"] == "COOLING_FAILURE" and d["status"] == "FAULT_DETECTED"


def test_overload_without_heat_is_still_overload_and_claims_no_thermal_fault():
    d = run_hospital({"TX": tx(current_a=130.0, temperature_c=60.0)})["TX"]
    assert d["code"] == "OVERLOAD" and d["status"] == "FAULT_DETECTED"
    assert [h["code"] for h in d["hypotheses"]] == ["OVERLOAD"]


def test_hot_with_cooling_ok_and_normal_current_is_not_called_a_cooling_failure():
    d = run_hospital({"TX": tx(temperature_c=85.0)})["TX"]
    assert d["code"] == "HIGH_TEMPERATURE"


def test_plausible_demand_change_within_rating_is_normal():
    window = ObservationWindow()
    for seq, current in enumerate((45.0, 70.0, 90.0, 105.0), start=1):
        for raw in sim.envelopes({"TX": tx(current_a=current)}, seq, NOW):
            window.add(validate(raw, {"TX"}, NOW))
    assert diagnose_transformer(window, "TX", TransformerRating(), NOW)["code"] == "NORMAL"


def test_shared_upstream_loss_versus_local_branch_interruption():
    shared = run_hospital(sim.hospital_readings("upstream_loss", "Theatre"))
    assert {d["code"] for d in shared.values()} == {"UPSTREAM_LOSS"}
    local = sim.hospital_readings("normal", "Theatre")
    local["TX3"].update(input_voltage_v=90.0, output_voltage_v=20.0, current_a=0.0)
    result = run_hospital(local)
    assert result["TX3"]["code"] == "LOCAL_SUPPLY_LOSS"
    assert result["TX1"]["code"] == result["TX2"]["code"] == "NORMAL"


def test_single_sample_is_an_alarm_not_a_root_cause():
    window = ObservationWindow()
    feed(window, {"TX": tx()}, samples=3)
    feed(window, {"TX": tx(current_a=130.0)}, samples=1, start=10)
    d = diagnose_transformer(window, "TX", TransformerRating(), NOW)
    assert d["code"] == "ALARM" and d["status"] == "ALARM"


# ---- abstention --------------------------------------------------------------------------

def test_sensor_dropout_and_missing_upstream_voltage_abstain_with_reasons():
    dropout = run_hospital({"TX": tx(current_a=None)})["TX"]
    assert dropout["status"] == "ABSTAINED" and "current" in " ".join(dropout["evidence"])
    no_input = run_hospital({"TX": tx(input_voltage_v=None)})["TX"]
    assert no_input["status"] == "ABSTAINED" and "input_voltage_v" in no_input["missing"]


def test_stale_observations_abstain():
    window = ObservationWindow()
    feed(window, {"TX": tx(current_a=130.0)}, now=NOW - timedelta(seconds=10))
    d = diagnose_transformer(window, "TX", TransformerRating(), NOW)
    assert d["status"] == "ABSTAINED" and d["cause"] == "Stale sensor evidence"


# ---- envelope validation -----------------------------------------------------------------

def test_invalid_envelopes_are_rejected():
    good = sim.envelopes({"TX1": tx()}, 1, NOW)[0]
    with pytest.raises(ObservationError):
        validate({**good, "asset_id": "TX9"}, {"TX1"}, NOW)  # unknown / swapped sensor id
    with pytest.raises(ObservationError):
        validate({**good, "observed_at": NOW + timedelta(seconds=30)}, {"TX1"}, NOW)
    with pytest.raises(ObservationError):
        validate({**good, "value": math.inf}, {"TX1"}, NOW)
    with pytest.raises(ObservationError):
        validate({**good, "value": True}, {"TX1"}, NOW)
    with pytest.raises(ObservationError):
        validate({**good, "observed_at": NOW.replace(tzinfo=None)}, {"TX1"}, NOW)
    with pytest.raises(ObservationError):
        validate({**good, "unit": "mA"}, {"TX1"}, NOW)


def test_out_of_order_samples_are_dropped():
    window = ObservationWindow()
    feed(window, {"TX": tx()}, samples=1, start=5)
    late = validate(sim.envelopes({"TX": tx(current_a=130.0)}, 4, NOW)[0], {"TX"}, NOW)
    assert window.add(late) is False and window.dropped_out_of_order == 1


# ---- campus --------------------------------------------------------------------------------

def campus(capacity=14000, avail=None, samples=2, window=None, start=1):
    window = window or ObservationWindow()
    readings = sim.campus_readings(capacity, avail or {"A": True, "B": True}, {"A": 6000, "B": 8000})
    feed(window, readings, samples=samples, start=start)
    return window, diagnose_campus(window, sim.CAMPUS_BUS, list(sim.CAMPUS_FEEDERS), FeederRating(), NOW)


def test_campus_feeder_trip_is_inferred_from_voltage_after_confirmation():
    window, normal = campus()
    assert normal["has_fault"] is False
    _, first = campus(avail={"A": True, "B": False}, samples=1, window=window, start=10)
    assert first["status"] == "ALARM" and not first["has_fault"]
    _, confirmed = campus(avail={"A": True, "B": False}, samples=1, window=window, start=11)
    assert confirmed["has_fault"] and confirmed["affected_assets"] == ["FEEDER_B"]
    assert confirmed["hypotheses"][0]["code"] == "FEEDER_DISCONNECTED"


def test_campus_capacity_limit_is_not_a_fault():
    _, result = campus(capacity=6000)
    assert result["has_fault"] is False


def test_live_campus_reports_constraint_separately(monkeypatch):
    from fastapi.testclient import TestClient

    import app.main as main
    client = TestClient(main.app)
    client.post("/api/v1/simulation/capacity", json={"capacity_w": 6000})
    fault = client.get("/api/v1/snapshot").json()["fault_diagnosis"]
    assert fault["has_fault"] is False and "not a diagnosed fault" in fault["supply_constraint"]
    client.post("/api/v1/simulation/capacity", json={"capacity_w": 14000})
    client.post("/api/v1/simulation/feeder", json={"feeder": "A", "available": False})
    main.app.state.site.tick()
    fault = client.get("/api/v1/snapshot").json()["fault_diagnosis"]
    assert fault["has_fault"] and fault["affected_assets"] == ["FEEDER_A"] and fault["status"] == "FAULT_DETECTED"


def test_hospital_scenario_pipeline_uses_the_rolling_window():
    telemetry = HospitalTelemetry()
    telemetry.sample("cooling_failure", "ICU", NOW - timedelta(seconds=0.25))
    assert telemetry.diagnoses(NOW - timedelta(seconds=0.25))["TX1"]["status"] in ("ALARM", "FAULT_DETECTED")
    telemetry.sample("cooling_failure", "ICU", NOW)
    result = telemetry.diagnoses(NOW)
    assert result["TX1"]["code"] == "COOLING_FAILURE" and result["TX2"]["code"] == "NORMAL"
