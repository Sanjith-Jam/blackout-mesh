"""Sensor synthesis: hidden scenario truth -> timestamped observation envelopes (#4).

This is the only module that knows scenario names and fixture values. The diagnosis package
receives the envelopes it produces and nothing else.
"""
from __future__ import annotations

from datetime import datetime

from app.diagnosis.observations import QUANTITIES

HOSPITAL_ZONES = ("ICU", "Theatre", "Wards")
HOSPITAL_ASSETS = {f"TX{i}": zone for i, zone in enumerate(HOSPITAL_ZONES, start=1)}

# (current_a, temperature_c, input_voltage_v, output_voltage_v, cooling_ok); None = sensor dropout
NORMAL_SENSORS = (45.0, 58.0, 230.0, 220.0, True)
HOSPITAL_FAULT_FIXTURES = {
    "overload": (130.0, 72.0, 230.0, 218.0, True),
    "cooling_failure": (45.0, 91.0, 230.0, 220.0, False),
    "missing_sensor": (None, 55.0, 230.0, 220.0, True),
}
UPSTREAM_LOSS_SENSORS = (0.0, 40.0, 90.0, 20.0, True)
TRANSFORMER_FIELDS = ("current_a", "temperature_c", "input_voltage_v", "output_voltage_v", "cooling_ok")

CAMPUS_BUS = "SRC"
CAMPUS_FEEDERS = ("A", "B")
NOMINAL_V = 230.0


def hospital_readings(scenario: str, zone: str) -> dict[str, dict]:
    """Ground-truth sensor values per transformer for a named teaching scenario."""
    target = {"ICU": "TX1", "Theatre": "TX2", "Wards": "TX3"}.get(zone, "TX2")
    readings = {}
    for asset in HOSPITAL_ASSETS:
        if scenario == "upstream_loss":
            values = UPSTREAM_LOSS_SENSORS
        elif asset == target:
            values = HOSPITAL_FAULT_FIXTURES.get(scenario, NORMAL_SENSORS)
        else:
            values = NORMAL_SENSORS
        readings[asset] = dict(zip(TRANSFORMER_FIELDS, values))
    return readings


def zone_readings(served_w: dict[str, float], demand_w: dict[str, float]) -> dict[str, dict]:
    """Transformer telemetry implied by served zone load (hospital zone view). No faults are modeled here."""
    readings = {}
    for asset, served in served_w.items():
        load = served / demand_w[asset] if demand_w.get(asset) else 0.0
        readings[asset] = {"current_a": round(served / NOMINAL_V, 2), "temperature_c": round(35.0 + 25.0 * load, 1),
                           "input_voltage_v": NOMINAL_V, "output_voltage_v": round(NOMINAL_V - 10.0 * load, 1),
                           "cooling_ok": True}
    return readings


# Faults the hospital zone view can inject into its live telemetry (A4). The allocation never sees them.
HOSPITAL_FAULTS = ("overload", "cooling_failure", "overload_cooling", "upstream_loss", "sensor_dropout", "stuck_sensor")


def apply_fault(readings: dict[str, dict], fault: dict | None, rated_current_a: dict[str, float], steps: int) -> dict[str, dict]:
    """Hidden truth of an injected fault, applied on top of zone telemetry. `steps` counts samples since injection.

    stuck_sensor is a real overload whose current sensor stays frozen at its pre-fault value.
    """
    if not fault:
        return readings
    out = {asset: dict(values) for asset, values in readings.items()}
    kind, target = fault["kind"], fault["asset"]
    ramp = min(1.0, (steps + 1) / 4)
    if kind == "upstream_loss":
        for asset in out:
            out[asset] = dict(zip(TRANSFORMER_FIELDS, UPSTREAM_LOSS_SENSORS))
        return out
    values = out[target]
    if kind in ("overload", "overload_cooling", "stuck_sensor"):
        values["current_a"] = round(1.3 * rated_current_a[target], 2)
        # A hidden overload warms the transformer, but (in the stuck case) not yet past the 80 °C alarm.
        values["temperature_c"] = round(values["temperature_c"] + ramp * (15.0 if kind == "stuck_sensor" else 20.0), 1)
    if kind in ("cooling_failure", "overload_cooling"):
        values["cooling_ok"] = False
        values["temperature_c"] = round(values["temperature_c"] + ramp * 35.0, 1)
    if kind == "sensor_dropout":
        values["current_a"] = None
    if kind == "stuck_sensor":
        values["current_a"] = fault["frozen_current_a"]
    return out


def add_noise(readings: dict[str, dict], sequence: int, frozen: set[tuple[str, str]] = frozenset()) -> dict[str, dict]:
    """Small deterministic measurement noise: real sensors never repeat a reading exactly. A frozen sensor does."""
    import random
    rng = random.Random(f"hospital-sensors:{sequence}")
    jitter = {"current_a": 0.05, "temperature_c": 0.2, "input_voltage_v": 0.5, "output_voltage_v": 0.5}
    out = {asset: dict(values) for asset, values in readings.items()}
    for asset, values in out.items():
        for quantity, span in jitter.items():
            if values.get(quantity) is not None and (asset, quantity) not in frozen:
                values[quantity] = round(max(0.0, values[quantity] + rng.uniform(-span, span)), 2)
    return out


def campus_readings(source_capacity_w: int, feeder_available: dict, served_w_by_feeder: dict) -> dict[str, dict]:
    """Bus and feeder-head telemetry implied by the simulated campus state."""
    bus_v = NOMINAL_V if source_capacity_w > 0 else 0.0
    readings = {CAMPUS_BUS: {"bus_voltage_v": bus_v}}
    for feeder in CAMPUS_FEEDERS:
        alive = bus_v > 0 and feeder_available.get(feeder, False)
        readings[feeder] = {"feeder_voltage_v": NOMINAL_V if alive else 0.0,
                            "feeder_current_a": round(served_w_by_feeder.get(feeder, 0) / NOMINAL_V, 3) if alive else 0.0}
    return readings


def envelopes(readings: dict[str, dict], sequence: int, observed_at: datetime) -> list[dict]:
    """Raw observation envelopes (validated later by app.diagnosis.observations.validate)."""
    out = []
    for asset, values in readings.items():
        for quantity, value in values.items():
            out.append({"asset_id": asset, "quantity": quantity, "value": value, "unit": QUANTITIES[quantity][0],
                        "observed_at": observed_at, "received_at": observed_at, "sequence": sequence,
                        "quality": "GOOD" if value is not None else "MISSING", "provenance": "SIMULATED_SENSOR"})
    return out
