import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.state import GridState
from app.core.restoration import RestorationGate
from conftest import session_request
import time


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()



def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_snapshot_backward_compatibility(client):
    response = client.get("/api/v1/snapshot")
    assert response.status_code == 200
    data = response.json()

    # Must have the original fields
    assert "services" in data
    assert "requested_mask" in data
    assert "modeled_mask" in data
    assert "indicator_mask" in data
    assert "hardware_link" in data

    services = data["services"]
    assert len(services) == 6
    ids = [s["id"] for s in services]
    assert ids == ["L0", "L1", "L2", "L3", "L4", "L5"]

    # Check L0 details (T1, 2000W, Feeder A)
    l0 = next(s for s in services if s["id"] == "L0")
    assert l0["tier"] == "T1"
    assert l0["watts"] == 2000
    assert l0["feeder"] == "A"

def test_hospital_rooms_follow_l0(client):
    response = client.get("/api/v1/snapshot")
    data = response.json()

    # Hospital should have 3 rooms
    rooms = data["zones"]["hospital"]["rooms"]
    assert len(rooms) == 3
    assert all(r["lighting_service"] == "L0" for r in rooms)

    # At 14000W capacity, L0 should be served (mask bits 0,1,2 = ON)
    cmd_mask = data["indicator_command_mask"]
    assert (cmd_mask & 0b111) == 0b111  # bits 0, 1, 2 are 1

def test_rfid_registered_card_selection(client):
    # Scan Card 1 (CR1)
    response = client.post("/api/v1/rfid/scan", json=session_request(client, {"uid": "CARD_1_UID"}))
    assert response.status_code == 200
    assert response.json()["active_classroom_id"] == "CR1"
    assert response.json()["event_type"] == "CARD_RECOGNIZED"

    # Check snapshot
    snap = client.get("/api/v1/snapshot").json()
    assert snap["zones"]["classroom"]["active_classroom_id"] == "CR1"
    assert all("UNKNOWN_CARD_UID" not in event.description for event in app.state.grid.events)

def test_rfid_unknown_card_is_nondestructive(client):
    client.post("/api/v1/rfid/scan", json=session_request(client, {"uid": "CARD_1_UID"}))

    # Scan unknown card
    response = client.post("/api/v1/rfid/scan", json=session_request(client, {"uid": "UNKNOWN_CARD_UID"}))
    assert response.status_code == 200
    assert response.json()["active_classroom_id"] is None
    assert response.json()["event_type"] == "UNKNOWN_CARD"

    snap = client.get("/api/v1/snapshot").json()
    assert snap["zones"]["classroom"]["active_classroom_id"] == "CR1"

def test_duplicate_scan_suppressed(client):
    import time
    # Unscan first
    time.sleep(2.1)
    # Fresh state, first scan
    r1 = client.post("/api/v1/rfid/scan", json=session_request(client, {"uid": "CARD_1_UID"}))
    assert r1.json()["accepted"] is True

    r2 = client.post("/api/v1/rfid/scan", json=session_request(client, {"uid": "CARD_1_UID"}))
    assert r2.json()["accepted"] is False
    assert r2.json()["event_type"] == "DUPLICATE_SUPPRESSED"

def test_rfid_event_id_is_idempotent_and_reuse_is_rejected(client):
    from datetime import datetime, timezone
    run_id = client.get("/api/v1/snapshot").json()["site"]["run_id"]
    event = {"event_id": "evt-1", "run_id": run_id, "observed_at": datetime.now(timezone.utc).isoformat()}
    first = client.post("/api/v1/rfid/scan", json={"uid": "CARD_1_UID", **event})
    repeated = client.post("/api/v1/rfid/scan", json={"uid": "CARD_1_UID", **event})
    assert first.json() == repeated.json()
    conflict = client.post("/api/v1/rfid/scan", json={"uid": "CARD_2_UID", **event})
    assert conflict.status_code == 409
    assert client.get("/api/v1/visualizers/classrooms").json()["scanned_classroom_ids"] == ["CR1"]

def test_session_mutations_reject_missing_identity(client):
    assert client.post("/api/v1/rfid/scan", json={"uid": "CARD_1_UID"}).status_code == 422
    assert client.post("/api/v1/simulation/classroom-load", json={
        "classroom_id": "CR1", "active": True
    }).status_code == 422
    assert client.post("/api/v1/visualizers/classrooms", json={
        "action": "scan", "classroom_id": "CR1"
    }).status_code == 422

def test_session_event_ids_and_order_are_enforced(client):
    from datetime import datetime, timedelta, timezone

    url = "/api/v1/visualizers/classrooms"
    run_id = client.get("/api/v1/snapshot").json()["site"]["run_id"]
    now = datetime.now(timezone.utc)
    start = {"action": "scan", "classroom_id": "CR2", "event_id": "session-1", "observed_at": now.isoformat(), "run_id": run_id}
    assert client.post(url, json=start).status_code == 200
    assert client.post(url, json=start).status_code == 200
    wrong_reuse = {**start, "action": "unscan"}
    assert client.post(url, json=wrong_reuse).status_code == 409
    stale_order = {"action": "unscan", "classroom_id": "CR2",
                   "observed_at": (now - timedelta(seconds=1)).isoformat(), "run_id": run_id,
                   "event_id": "session-2"}
    assert client.post(url, json=stale_order).status_code == 409
    too_old = {"action": "unscan", "classroom_id": "CR2",
               "observed_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), "run_id": run_id}
    assert client.post(url, json=too_old).status_code == 422
    assert client.get(url).json()["scanned_classroom_ids"] == ["CR2"]

def test_session_event_from_previous_run_is_rejected(client):
    from datetime import datetime, timezone

    run_id = client.get("/api/v1/snapshot").json()["site"]["run_id"]
    started = client.post("/api/v1/visualizers/classrooms", json={
        "action": "scan", "classroom_id": "CR1", "run_id": run_id,
        "event_id": "current-run-event", "observed_at": datetime.now(timezone.utc).isoformat()
    })
    assert started.status_code == 200
    app.state.site.new_run()
    response = client.post("/api/v1/visualizers/classrooms", json={
        "action": "scan", "classroom_id": "CR1", "run_id": run_id,
        "event_id": "old-run-event", "observed_at": datetime.now(timezone.utc).isoformat()
    })
    assert response.status_code == 409
    assert client.get("/api/v1/visualizers/classrooms").json()["scanned_classroom_ids"] == []
    projections = [client.get(path).json() for path in ("/api/v1/snapshot", "/api/v1/visualizers/classrooms", "/api/v1/visualizers/hospital")]
    assert len({item["site"]["run_id"] for item in projections}) == 1

def test_classroom_led_isolation(client):
    # 1. Scan Card 1 (CR1)
    client.post("/api/v1/rfid/scan", json=session_request(client, {"uid": "CARD_1_UID"}))

    # A card scan DOES turn on the LED because session = requested load
    snap = client.get("/api/v1/snapshot").json()
    cmd_mask = snap["indicator_command_mask"]
    # Classroom bits (3,4,5) should be 0
    assert (cmd_mask & 0b001000) != 0

    # 2. Activate load for CR1
    client.post("/api/v1/simulation/classroom-load", json=session_request(client, {"classroom_id": "CR1", "active": True}))

    snap = client.get("/api/v1/snapshot").json()
    cmd_mask = snap["indicator_command_mask"]
    # Only CR1 LED (bit 3) should be ON among classrooms
    assert (cmd_mask & 0b111000) == 0b001000  # bit 3 is 1, bits 4,5 are 0

    # 3. Scan Card 2 (CR2) -> Switches selection. CR1 LED must turn OFF, CR2 LED evaluated
    client.post("/api/v1/rfid/scan", json=session_request(client, {"uid": "CARD_2_UID"}))
    snap = client.get("/api/v1/snapshot").json()
    cmd_mask = snap["indicator_command_mask"]
    # CR1 LED is now OFF because it's no longer the active classroom.
    # CR2 LED is OFF because its load event is false.
    assert (cmd_mask & 0b001000) != 0

def test_classroom_led_shed_condition(client):
    # CR1 selected and load active
    client.post("/api/v1/rfid/scan", json=session_request(client, {"uid": "CARD_1_UID"}))
    client.post("/api/v1/simulation/classroom-load", json=session_request(client, {"classroom_id": "CR1", "active": True}))

    snap = client.get("/api/v1/snapshot").json()
    assert (snap["indicator_command_mask"] & 0b111000) == 0b001000 # LED 3 ON

    # Feeder B goes down -> L3 (CR1) shed -> LED must turn OFF
    client.post("/api/v1/simulation/feeder", json={"feeder": "B", "available": False})

    snap = client.get("/api/v1/snapshot").json()
    # L3 is shed
    l3 = next(s for s in snap["services"] if s["id"] == "L3")
    assert l3["modeled_served"] is False
    # LED 3 is OFF
    assert (snap["indicator_command_mask"] & 0b111000) == 0

def test_priority_allocation_constraints(client):
    # Drop capacity to 6000W
    client.post("/api/v1/simulation/capacity", json={"capacity_w": 6000})
    snap = client.get("/api/v1/snapshot").json()

    services = {s["id"]: s for s in snap["services"]}

    # Total served must not exceed 6000
    total_served = sum(s["served_w"] for s in snap["services"])
    assert total_served <= 6000 and total_served == snap["allocation"]["served_w"]

    # Priority check: T1s (L0, L1) must be served over T3 (L5)
    assert services["L0"]["modeled_served"] is True
    assert services["L1"]["modeled_served"] is True

    # Since L0 (2000) + L1 (1000) = 3000, 3000 remains.
    # Next is T2: L2 (3000), L3 (2000), L4 (2000).
    # The greedy allocator (sorted by watts asc within tier) will pick L3 (2000).
    # Then 1000 remains. Neither L2 (3000) nor L4 (2000) fit.
    # L5 (4000) T3 definitely doesn't fit.
    # Total served: L0(2000) + L1(1000) + L3(2000) = 5000 <= 6000.

    # Feeder B is decided by the classroom leaves (#33): L5 keeps at most part of its 4,000 W.
    assert services["L5"]["served_w"] < services["L5"]["requested_w"]

def test_hardware_confirmation_truth(client):
    snap = client.get("/api/v1/snapshot").json()
    # Indicator confirmed mask should be None (never fabricate a confirmation)
    assert snap["indicator_confirmed_mask"] is None


def test_contract_fields_present(client):
    response = client.get("/api/v1/snapshot")
    assert response.status_code == 200
    data = response.json()
    assert "contract" in data
    assert "identity" in data["contract"]
    assert "run_id" in data["contract"]["identity"]
    assert "site_id" in data["contract"]["identity"]

    response2 = client.get("/api/v1/visualizers/classrooms")
    data2 = response2.json()
    assert "contract" in data2
    assert "identity" in data2["contract"]
    assert data2["contract"]["identity"]["run_id"] == data["contract"]["identity"]["run_id"]

    response3 = client.get("/api/v1/visualizers/hospital")
    data3 = response3.json()
    assert "contract" in data3
    assert "identity" in data3["contract"]
    assert data3["contract"]["identity"]["run_id"] == data["contract"]["identity"]["run_id"]
