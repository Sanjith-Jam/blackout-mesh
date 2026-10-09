"""Export API responses used as frontend component-test fixtures (#16).

    PYTHONPATH=backend python backend/scripts/export_frontend_fixtures.py

backend/tests/test_frontend_contract.py fails if the API shape drifts from these fixtures.
"""
from __future__ import annotations

import json
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "frontend" / "src" / "test" / "fixtures"
VOLATILE = {"generated_at", "sent_at", "run_id", "last_tick_at", "timestamp", "observed_at", "recorded_at"}


def scrub(value):
    """Replace volatile identity/time fields so fixtures are deterministic."""
    if isinstance(value, dict):
        return {k: ("<volatile>" if k in VOLATILE and v is not None else scrub(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


def build() -> dict:
    from fastapi.testclient import TestClient

    import app.main as main
    client = TestClient(main.app)
    post = lambda path, body: client.post(path, json=body)
    post("/api/v1/visualizers/classrooms", {"action": "reset"})
    post("/api/v1/visualizers/classrooms", {"action": "replay_pause"})
    post("/api/v1/visualizers/classrooms", {"action": "scan", "classroom_id": "CR1"})
    post("/api/v1/visualizers/classrooms", {"action": "scan", "classroom_id": "CR2"})
    classrooms = post("/api/v1/visualizers/classrooms", {"action": "set_capacity", "capacity_w": 3000}).json()
    post("/api/v1/visualizers/hospital", {"action": "reset"})
    hospital = client.get("/api/v1/visualizers/hospital").json()
    abstained = post("/api/v1/visualizers/hospital", {"scenario": "missing_sensor"}).json()
    campus = client.get("/api/v1/snapshot").json()
    post("/api/v1/visualizers/classrooms", {"action": "reset"})
    return {name: scrub(data) for name, data in
            {"classrooms": classrooms, "hospital": hospital, "hospital_missing_sensor": abstained, "campus": campus}.items()}


def main():
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for name, data in build().items():
        (FIXTURE_DIR / f"{name}.json").write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print("wrote", FIXTURE_DIR / f"{name}.json")


if __name__ == "__main__":
    main()
