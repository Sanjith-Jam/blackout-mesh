import json
import sys
from pathlib import Path

from app.activity.model import ActivityModel, FEATURES


MODELS = Path(__file__).resolve().parents[1] / "models"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from train_activity import metrics


def test_trained_model_infers_and_rejects_bad_evidence():
    model = ActivityModel()
    status = model.status()
    assert status["ready"] is True
    assert status["features"] == FEATURES
    json.dumps(status)

    replay = json.loads((MODELS / "replay.json").read_text())
    obs = {key: replay["CR1"][0][key] for key in FEATURES}
    prediction = model.predict(obs)
    assert prediction["state"] in {"ACTIVE", "INACTIVE", "UNKNOWN"}
    assert prediction["model_version"] == status["model_version"]
    assert isinstance(prediction["score"], float)

    assert model.predict({})["state"] == "UNKNOWN"
    assert model.predict({**obs, "co2_ppm": True})["state"] == "UNKNOWN"
    assert model.predict({**obs, "co2_ppm": float("nan")})["state"] == "UNKNOWN"


def test_replay_contains_only_validation_style_observations():
    replay = json.loads((MODELS / "replay.json").read_text())
    assert set(replay) == {"CR1", "CR2", "CR3"}
    for room, samples in replay.items():
        assert samples
        assert all(sample["classroom_id"] == room for sample in samples)
        assert all(sample["source"] == "RECORDED_REPLAY" for sample in samples)
        assert all(set(FEATURES).issubset(sample) for sample in samples)
        assert all("Occupancy" not in sample and "Light" not in sample for sample in samples)


def test_unknown_sentinel_counts_as_abstention_and_error():
    report = metrics([0, 1], [0, -1])
    assert report["unknown_count"] == 1
    assert report["coverage"] == 0.5
    assert report["occupancy_recall_all_rows_unknown_counts_as_miss"] == 0.0
    assert report["macro_f1_all_rows_unknown_as_error"] < report["macro_f1_covered"]
