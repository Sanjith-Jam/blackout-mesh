"""Evidence-backed power-path edges (#23)."""
from fastapi.testclient import TestClient

import app.main as main
from app.core.edges import STATES, edge
from app.visualizers import HOSP_LOADS, LOADS, ClassroomDemo

client = TestClient(main.app)


def by_id(edges):
    ids = [e["id"] for e in edges]
    assert len(ids) == len(set(ids)), "edge ids must be unique"
    return {e["id"]: e for e in edges}


def test_every_classroom_load_maps_to_one_edge_matching_its_served_state():
    snap = client.get("/api/v1/visualizers/classrooms").json()
    edges = by_id(snap["edges"])
    for room in snap["rooms"]:
        assert f"classroom:BUS>{room['id']}" in edges
        for load in room["loads"]:
            e = edges[f"classroom:{room['id']}>{load['id']}"]
            assert (e["state"] == "ENERGIZED") == load["served"]
            assert e["unit"] == "W" and e["provenance"] == "MODELED" and e["physical"] == "NOT_CONNECTED"
    assert all(e["state"] in STATES for e in snap["edges"])
    assert len(snap["edges"]) == 1 + len(LOADS) + sum(len(v) for v in LOADS.values())


def test_no_flow_across_an_open_feeder():
    client.post("/api/v1/simulation/feeder", json={"feeder": "B", "available": False})
    snap = client.get("/api/v1/visualizers/classrooms").json()
    assert all(e["state"] == "OPEN" and e["served_w"] == 0 and not e["applied"] for e in snap["edges"])
    assert all("feeder B is unavailable" in e["reason"] for e in snap["edges"])
    campus = client.get("/api/v1/snapshot").json()
    campus_edges = by_id(campus["edges"])
    for sid in ("L3", "L4", "L5"):
        assert campus_edges[f"campus:B>{sid}"]["state"] == "OPEN"
    assert campus_edges["campus:A>L0"]["state"] == "ENERGIZED"


def test_pending_restoration_is_not_shown_as_energized():
    now = [0.0]
    demo = ClassroomDemo(lambda: now[0])
    demo.act("set_capacity", capacity_w=3400)
    now[0] = 1.0
    snap = demo.act("normal")  # commanded back on, but the restoration gate holds them
    pending = [e for e in snap["edges"] if e["state"] == "PENDING_RESTORATION"]
    assert pending and all(e["commanded"] and not e["applied"] for e in pending)
    load_edges = [e for e in pending if "." in e["to"]]
    assert load_edges and all("waiting for the restoration delay" in e["reason"] for e in load_edges)


def test_shed_edges_explain_why():
    snap = client.post("/api/v1/visualizers/classrooms", json={"action": "set_capacity", "capacity_w": 2500}).json()
    shed = [e for e in snap["edges"] if e["state"] == "SHED" and e["to"].count(".") == 1]
    assert shed and all("did not fit" in e["reason"] for e in shed)


def test_hospital_edges_keep_observed_voltage_separate_and_unknown_when_abstained():
    snap = client.get("/api/v1/visualizers/hospital").json()
    edges = by_id(snap["edges"])
    feed = edges["hospital:BUS>TX1"]
    assert feed["observed"]["provenance"] == "SIMULATED_SENSOR"
    assert "no measured branch current" in feed["observed"]["note"]
    assert len(snap["edges"]) == 1 + 3 + sum(len(v) for v in HOSP_LOADS.values())
    # An abstained diagnosis must not look healthy even if the model says the path is applied.
    e = edge("x", "a", "b", connected=True, commanded=True, applied=True, requested_w=10, served_w=10,
             reason="r", evidence_unknown=True)
    assert e["state"] == "UNKNOWN"


def test_generated_at_only_changes_with_the_published_revision():
    a = client.get("/api/v1/visualizers/classrooms").json()
    b = client.get("/api/v1/visualizers/classrooms").json()
    assert a["generated_at"] == b["generated_at"] and a["published_revision"] == b["published_revision"]
    c = client.post("/api/v1/visualizers/classrooms", json={"action": "set_capacity", "capacity_w": 5000}).json()
    assert c["published_revision"] > a["published_revision"] and c["generated_at"] >= a["generated_at"]
