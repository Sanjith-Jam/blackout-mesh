from fastapi.testclient import TestClient

from app.main import app
from app.visualizers import ClassroomDemo, diagnose, hospital_snapshot


def test_classroom_demo_exact_shortage_and_isolated_reset():
    with TestClient(app) as client:
        normal = client.post("/api/v1/visualizers/classrooms", json={"action": "normal"}).json()
        assert normal["capacity_w"] == 8000
        assert normal["served_w"] == 8000
        scanned = client.post("/api/v1/visualizers/classrooms", json={"action": "scan", "classroom_id": "CR1"}).json()
        assert scanned["capacity_w"] == 8000 and scanned["served_w"] == 8000
        overloaded = client.post("/api/v1/visualizers/classrooms", json={"action": "overload"}).json()
        assert overloaded["capacity_w"] == 3400
        assert overloaded["served_w"] == 3400
        scanned = overloaded
        assert scanned["requested_w"] == 8000
        assert scanned["selected_classroom_id"] == "CR1"
        rooms = {room["id"]: room for room in scanned["rooms"]}
        assert all(load["served"] for load in rooms["CR1"]["loads"])
        assert all(load["served"] for room in ("CR2", "CR3") for load in rooms[room]["loads"] if load["essential"])
        assert all(not load["served"] for room in ("CR2", "CR3") for load in rooms[room]["loads"] if not load["essential"])
        assert client.post("/api/v1/visualizers/classrooms", json={"action": "reset"}).json()["selected_classroom_id"] is None
        # The six-service production snapshot remains independently owned.
        assert client.get("/api/v1/snapshot").status_code == 200


def test_classroom_demo_validation_and_constraints():
    with TestClient(app) as client:
        assert client.post("/api/v1/visualizers/classrooms", json={"action": "scan", "classroom_id": "CR4"}).status_code == 422
        assert client.post("/api/v1/visualizers/classrooms", json={"action": "scan"}).status_code == 422
        assert client.post("/api/v1/visualizers/classrooms", json={"action": "normal", "extra": True}).status_code == 422
        assert client.post("/api/v1/visualizers/classrooms", json={"action": "normal", "classroom_id": "CR1"}).status_code == 422
        client.post("/api/v1/visualizers/classrooms", json={"action": "reset"})
        snapshot = client.post("/api/v1/visualizers/classrooms", json={"action": "overload"}).json()
        assert snapshot["selected_classroom_id"] is None
        assert snapshot["served_w"] <= snapshot["capacity_w"]


def test_hospital_diagnosis_uses_sensor_values_only():
    overload = diagnose(100, 130, 70, 230, 220, True)
    cooling = diagnose(100, 45, 91, 230, 220, False)
    upstream = diagnose(100, 0, 40, 90, 20, True)
    missing = diagnose(100, None, 55, 230, 220, True)
    assert overload["code"] == "OVERLOAD"
    assert cooling["code"] == "COOLING_FAILURE"
    assert upstream["code"] == "UPSTREAM_LOSS"
    assert missing["code"] == "UNKNOWN"
    with TestClient(app) as client:
        cooling = client.post("/api/v1/visualizers/hospital", json={"scenario": "cooling_failure"}).json()
        assert [t["diagnosis"]["code"] for t in cooling["transformers"]] == ["NORMAL", "COOLING_FAILURE", "NORMAL"]
        assert client.post("/api/v1/visualizers/hospital", json={"scenario": "normal", "code": "OVERLOAD"}).status_code == 422


def test_classroom_restoration_uses_time_not_snapshot_count():
    now = [0.0]
    demo = ClassroomDemo(lambda: now[0])
    initial = demo.snapshot()
    assert initial["served_w"] == 8000
    demo.act("scan", "CR1")
    assert demo.snapshot()["served_w"] == 8000
    demo.act("overload", None)
    assert demo.snapshot()["served_w"] == 3400
    demo.act("normal", None)
    for _ in range(100):
        waiting = demo.snapshot()
        assert waiting["served_w"] == 3400
    assert any(load["reason"] == "Waiting for simulated restoration delay"
               for room in waiting["rooms"] for load in room["loads"] if not load["served"])
    now[0] = 2.99
    assert demo.snapshot()["served_w"] == 3400
    now[0] = 5.0
    first = demo.snapshot()["served_w"]
    assert first > 3400
    for _ in range(100):
        assert demo.snapshot()["served_w"] == first
    now[0] = 6.0
    assert demo.snapshot()["served_w"] > first


def test_hospital_faults_are_local_except_upstream_loss():
    for scenario, expected in (("overload", "OVERLOAD"), ("cooling_failure", "COOLING_FAILURE"), ("missing_sensor", "UNKNOWN")):
        transformers = hospital_snapshot(scenario)["transformers"]
        assert [t["diagnosis"]["code"] for t in transformers] == ["NORMAL", expected, "NORMAL"]
    upstream = hospital_snapshot("upstream_loss")["transformers"]
    assert [t["diagnosis"]["code"] for t in upstream] == ["UPSTREAM_LOSS"] * 3
    assert [t["zone"] for t in upstream] == ["ICU", "Theatre", "Wards"]
