"""Train a small causal demand forecaster on reproducible synthetic sessions.

No campus accuracy claim: separate sessions train, set error bands, and evaluate.
Run with the installed ML environment; inference needs only the saved coefficients.
"""
import hashlib
import json
import math
import random
import statistics
import time
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge

ROOT = Path(__file__).resolve().parents[1]
LAGS, HORIZONS, STEP_S = 4, 6, 10


def sessions():
    rng = random.Random(68123)
    result = []
    for _ in range(120):
        base, amplitude = rng.uniform(5500, 10000), rng.uniform(700, 2500)
        phase, period = rng.uniform(0, 2 * math.pi), rng.uniform(65, 110)
        slope = rng.uniform(-30, 30)
        result.append([round(max(0, min(14000, base + amplitude * math.sin(phase + t / period * 2 * math.pi)
                                       + slope * (t - 40) + rng.gauss(0, 35)))) for t in range(80)])
    return result


def rows(data):
    x, y = [], []
    for session in data:
        for t in range(LAGS - 1, len(session) - HORIZONS):
            history = session[t - LAGS + 1:t + 1]
            x.append([value / 14000 for value in history])
            y.append(session[t + 1:t + HORIZONS + 1])
    return np.array(x), np.array(y)


def train():
    data = sessions()
    train_x, train_y = rows(data[:80])
    calibration_x, calibration_y = rows(data[80:100])
    test_x, test_y = rows(data[100:])
    model = Ridge(alpha=0.0001).fit(train_x, train_y)
    bands = np.quantile(abs(model.predict(calibration_x) - calibration_y), 0.90, axis=0)
    predicted = np.clip(np.rint(model.predict(test_x)), 0, 14000)
    errors = abs(predicted - test_y)
    baseline = abs(test_x[:, -1, None] * 14000 - test_y)
    timings = []
    for _ in range(100):
        start = time.perf_counter()
        model.predict(test_x[:1])
        timings.append((time.perf_counter() - start) * 1000)
    artifact = dict(model_version="synthetic-demand-ridge-v1", training_source="SYNTHETIC_SESSIONS",
                    sample_s=STEP_S, lags=LAGS, horizons=HORIZONS, scale_w=14000,
                    coefficients=model.coef_.tolist(), intercepts=model.intercept_.tolist(),
                    error_band_w=[math.ceil(value) for value in bands])
    path = ROOT / "models" / "demand-forecast.json"
    path.write_text(json.dumps(artifact, indent=2) + "\n")
    report = dict(model_version=artifact["model_version"], artifact_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  source="Synthetic smooth demand sessions; no field or campus validation",
                  seed=68123, sessions=dict(train=80, calibration=20, test=20),
                  rows=dict(train=len(train_x), calibration=len(calibration_x), test=len(test_x)),
                  sample_s=STEP_S, horizon_s=[STEP_S * h for h in range(1, HORIZONS + 1)],
                  mae_w=[round(float(value), 2) for value in errors.mean(axis=0)],
                  persistence_mae_w=[round(float(value), 2) for value in baseline.mean(axis=0)],
                  empirical_band_coverage=[round(float(value), 4) for value in (errors <= bands).mean(axis=0)],
                  sklearn_predict_median_ms=statistics.median(timings), latency_calls=len(timings),
                  limits=["Smooth synthetic demand only; abrupt trips and new sessions cannot be predicted reliably.",
                          "Error bands use separate synthetic calibration sessions, not calibrated field confidence.",
                          "Advisory only; forecasts cannot shed loads or authorize restoration."])
    (ROOT / "models" / "DEMAND_FORECAST_REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    train()
