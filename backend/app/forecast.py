"""Causal, advisory demand forecast. Never changes allocation or restoration."""
import json
import threading
import time
from collections import deque
from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "demand-forecast.json"
RISING_REPLAY = [3900, 4100, 4400, 4750, 5100, 5450, 5800, 6150]


class DemandForecast:
    def __init__(self, clock=time.monotonic, model_path=MODEL_PATH):
        self.clock = clock
        self.lock = threading.RLock()
        self.samples = deque(maxlen=12)
        self.run_id = None
        self.last_at = None
        self.load_error = None
        try:
            self.model = json.loads(model_path.read_text())
        except (OSError, ValueError) as exc:
            self.model = None
            self.load_error = f"Forecast artifact unavailable: {type(exc).__name__}"

    def observe(self, run_id, demand_w):
        with self.lock:
            now = self.clock()
            if run_id != self.run_id or (self.last_at is not None and now - self.last_at > 20):
                self.samples.clear()
                self.last_at = None
            self.run_id = run_id
            if self.last_at is not None and now - self.last_at < 10:
                return
            if type(demand_w) is not int or not 0 <= demand_w <= 14000:
                self.samples.clear()
                self.last_at = None
                return
            self.samples.append(demand_w)
            self.last_at = now

    def predict(self, capacity_w, source="LIVE_REQUESTED_DEMAND", replay_index=3):
        with self.lock:
            history = list(self.samples) if source == "LIVE_REQUESTED_DEMAND" else RISING_REPLAY[:replay_index + 1]
            age = None if self.last_at is None else round(self.clock() - self.last_at, 2)
            out = dict(source=source, model_version=self.model["model_version"] if self.model else "unavailable",
                       sample_s=10, sample_age_s=age if source == "LIVE_REQUESTED_DEMAND" else None,
                       observations_w=history, points=[], status="UNKNOWN", reason="Collecting four demand readings (30 seconds).",
                       first_shortage_s=None, capacity_w=capacity_w)
            if not self.model:
                out["reason"] = self.load_error
            elif source == "LIVE_REQUESTED_DEMAND" and (age is None or age > 20):
                out["reason"] = "Demand observations are missing or stale."
            elif len(history) >= 4:
                recent = history[-4:]
                if any(abs(b - a) > 2500 for a, b in zip(recent, recent[1:])):
                    out["reason"] = "Abrupt demand change: wait for four stable readings; sensor history is insufficient."
                    return out
                x = [value / self.model["scale_w"] for value in recent]
                for i, (coefficients, intercept, band) in enumerate(zip(self.model["coefficients"], self.model["intercepts"], self.model["error_band_w"])):
                    watts = max(0, min(14000, round(intercept + sum(a * b for a, b in zip(coefficients, x)))))
                    out["points"].append(dict(ahead_s=(i + 1) * 10, demand_w=watts,
                                              lower_w=max(0, watts - band), upper_w=min(14000, watts + band)))
                out["first_shortage_s"] = next((p["ahead_s"] for p in out["points"] if p["upper_w"] > capacity_w), None)
                out["status"] = "SHORTAGE_RISK" if out["first_shortage_s"] else "WITHIN_CAPACITY"
                out["reason"] = "Synthetic-trained Ridge forecast with empirical synthetic error bands; advisory only."
            return out
