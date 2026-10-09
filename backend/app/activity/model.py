"""Local occupancy proxy inference from environmental sensor readings."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

FEATURES = ["temperature_c", "humidity_pct", "co2_ppm", "humidity_ratio"]
MODEL_DIR = Path(__file__).resolve().parents[2] / "models"


class ActivityModel:
    def __init__(self, model_dir: Path | str = MODEL_DIR):
        self.model_dir = Path(model_dir)
        self._model = None
        self._manifest = {}
        self._fallback = None
        try:
            manifest = json.loads((self.model_dir / "manifest.json").read_text())
            artifact = self.model_dir / manifest["artifact"]
            if hashlib.sha256(artifact.read_bytes()).hexdigest() != manifest["sha256"]:
                raise ValueError("model artifact hash mismatch")
            if manifest["features"] != FEATURES:
                raise ValueError("model feature schema mismatch")
            import joblib

            self._model = joblib.load(artifact)
            self._manifest = manifest
        except Exception as exc:
            self._fallback = f"model unavailable: {exc}"

    def status(self) -> dict:
        report = self._manifest.get("evaluation", {})
        return {
            "ready": self._model is not None,
            "model_version": self._manifest.get("model_version", "unavailable"),
            "model_type": self._manifest.get("model_type", "unavailable"),
            "features": FEATURES.copy(),
            "data_source": self._manifest.get("data_source", "UCI Occupancy Detection"),
            "evaluation": report,
            "fallback_reason": self._fallback,
        }

    def predict(self, features: dict) -> dict:
        result = {"state": "UNKNOWN", "score": None,
                  "model_version": self._manifest.get("model_version", "unavailable"),
                  "reason": "model unavailable" if self._model is None else "invalid or missing sensor evidence"}
        if self._model is None or not isinstance(features, dict):
            return result
        bounds = ((-10, 60), (0, 100), (250, 10000), (0, 0.05))
        values = []
        for key, (low, high) in zip(FEATURES, bounds):
            value = features.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                return result
            values.append(float(value))
        import numpy as np

        score = float(self._model.predict_proba(np.asarray([values]))[0][1])
        result["score"] = score
        threshold = float(self._manifest.get("decision_threshold", 0.5))
        margin = float(self._manifest.get("abstain_margin", 0.0))
        if abs(score - threshold) < margin:
            result["reason"] = "model uncertain; abstained"
        else:
            result["state"] = "ACTIVE" if score >= threshold else "INACTIVE"
            result["reason"] = "local environmental occupancy estimate"
        return result
