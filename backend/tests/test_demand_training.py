"""Synthetic forecasting evidence must keep whole sessions apart and beat persistence."""
import json
from pathlib import Path

from scripts.train_demand_forecast import rows, sessions


def test_synthetic_sessions_and_causal_windows():
    data = sessions()
    assert data == sessions()
    assert len(data) == 120
    hashes = [tuple(session) for session in data]
    assert len(set(hashes)) == len(hashes)
    x, y = rows([data[0]])
    assert list(x[0] * 14000) == data[0][:4]
    assert list(y[0]) == data[0][4:10]


def test_frozen_forecast_evidence():
    import hashlib
    models = Path(__file__).resolve().parents[1] / "models"
    report = json.loads((models / "DEMAND_FORECAST_REPORT.json").read_text())
    assert report["artifact_sha256"] == hashlib.sha256((models / "demand-forecast.json").read_bytes()).hexdigest()
    assert report["sessions"] == {"train": 80, "calibration": 20, "test": 20}
    assert report["mae_w"][-1] < report["persistence_mae_w"][-1]
    assert 0 <= report["empirical_band_coverage"][-1] <= 1
