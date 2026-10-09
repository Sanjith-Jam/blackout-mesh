"""Observation envelopes: the only input the diagnosis package accepts (#4).

Nothing here (or anywhere in app.diagnosis) may import scenario truth or simulator state.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

FUTURE_TOLERANCE = timedelta(seconds=2)

# quantity -> (unit, accepted physical range); booleans use (None) range
QUANTITIES = {
    "current_a": ("A", (0.0, 10_000.0)),
    "temperature_c": ("degC", (-40.0, 250.0)),
    "input_voltage_v": ("V", (0.0, 1_000.0)),
    "output_voltage_v": ("V", (0.0, 1_000.0)),
    "cooling_ok": ("bool", None),
    "bus_voltage_v": ("V", (0.0, 1_000.0)),
    "feeder_voltage_v": ("V", (0.0, 1_000.0)),
    "feeder_current_a": ("A", (0.0, 10_000.0)),
}
QUALITIES = ("GOOD", "SUSPECT", "MISSING")


class ObservationError(ValueError):
    pass


@dataclass(frozen=True)
class Observation:
    asset_id: str
    quantity: str
    value: float | bool | None
    unit: str
    observed_at: datetime
    received_at: datetime
    sequence: int
    quality: str = "GOOD"
    provenance: str = "SIMULATED_SENSOR"
    uncertainty: float | None = None
    extra: dict = field(default_factory=dict, compare=False)


def validate(raw: dict, known_assets: set[str], now: datetime | None = None) -> Observation:
    """Strictly validate one raw envelope. Missing values are kept as None with quality MISSING."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(raw, dict):
        raise ObservationError("observation must be an object")
    asset = raw.get("asset_id")
    if asset not in known_assets:
        raise ObservationError(f"unknown asset {asset!r}")
    quantity = raw.get("quantity")
    if quantity not in QUANTITIES:
        raise ObservationError(f"unknown quantity {quantity!r}")
    unit, bounds = QUANTITIES[quantity]
    if raw.get("unit", unit) != unit:
        raise ObservationError(f"{quantity} must be in {unit}")
    sequence = raw.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise ObservationError("sequence must be a non-negative integer")
    observed_at, received_at = raw.get("observed_at"), raw.get("received_at", now)
    for name, ts in (("observed_at", observed_at), ("received_at", received_at)):
        if not isinstance(ts, datetime) or ts.tzinfo is None:
            raise ObservationError(f"{name} must be a timezone-aware datetime")
    if observed_at > now + FUTURE_TOLERANCE:
        raise ObservationError("observed_at is in the future beyond tolerance")
    value = raw.get("value")
    quality = raw.get("quality", "GOOD" if value is not None else "MISSING")
    if quality not in QUALITIES:
        raise ObservationError(f"unknown quality {quality!r}")
    if value is None:
        quality = "MISSING"
    elif bounds is None:
        if not isinstance(value, bool):
            raise ObservationError(f"{quantity} must be a boolean")
    else:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ObservationError(f"{quantity} must be a finite number")
        if not bounds[0] <= value <= bounds[1]:
            raise ObservationError(f"{quantity} outside physical range")
        value = float(value)
    uncertainty = raw.get("uncertainty")
    return Observation(asset, quantity, value, unit, observed_at.astimezone(timezone.utc),
                       received_at.astimezone(timezone.utc), sequence, quality,
                       raw.get("provenance", "SIMULATED_SENSOR"), uncertainty)
