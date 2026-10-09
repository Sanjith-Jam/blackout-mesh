"""One site authority over campus, classroom and hospital (#3, first step)."""
from fastapi.testclient import TestClient

import app.main as main
from app.core.site import CATALOG_VERSION, classroom_headroom_w, reconcile_catalog
from app.core.state import SERVICE_CATALOG
from app.visualizers import LOADS

client = TestClient(main.app)
ROUTES = ("/api/v1/snapshot", "/api/v1/visualizers/classrooms", "/api/v1/visualizers/hospital")


def read_all():
    return [client.get(path).json() for path in ROUTES]


def test_classroom_leaves_reconcile_with_campus_services_without_double_counting():
    assert reconcile_catalog() == []
    feeder_b = sum(s["watts"] for s in SERVICE_CATALOG if s["feeder"] == "B")
    leaves = sum(item[2] for rows in LOADS.values() for item in rows)
    assert leaves == feeder_b == 8000
    campus, classroom, _ = read_all()
    assert classroom["requested_w"] == sum(s["watts"] for s in campus["services"] if s["feeder"] == "B" and s["requested"])


def test_one_command_updates_every_projection_under_one_run_and_revision():
    before = read_all()
    client.post("/api/v1/simulation/feeder", json={"feeder": "B", "available": False})
    campus, classroom, hospital = read_all()
    ids = {(p["site"]["run_id"], p["site"]["revision"]) for p in (campus, classroom, hospital)}
    assert len(ids) == 1
    assert campus["site"]["revision"] > before[0]["site"]["revision"]
    assert campus["site"]["catalog_version"] == CATALOG_VERSION
    # Feeder B trip reaches the classroom view in the same revision.
    assert all(not s["modeled_served"] for s in campus["services"] if s["feeder"] == "B")
    assert classroom["campus_limit_w"] == 0 and classroom["served_w"] == 0
    assert classroom["limited_by"] == "campus feeder B"
    assert classroom["safety"]["status"] == "PROTECTED_SHORTFALL"


def test_campus_shortage_bounds_the_classroom_view():
    client.post("/api/v1/simulation/capacity", json={"capacity_w": 9000})
    campus, classroom, _ = read_all()
    feeder_a_served = sum(s["watts"] for s in campus["services"] if s["feeder"] == "A" and s["modeled_served"])
    headroom = min(8000, 9000 - feeder_a_served)
    assert classroom["campus_limit_w"] == headroom == classroom["effective_capacity_w"]
    assert classroom["served_w"] <= headroom
    assert classroom["capacity_w"] == 8000  # the classroom limit itself is unchanged and still named


def test_multi_scan_shortage_keeps_essentials_and_ranks_within_campus_budget():
    for cid in ("CR1", "CR2"):
        client.post("/api/v1/visualizers/classrooms", json={"action": "scan", "classroom_id": cid})
    client.post("/api/v1/simulation/capacity", json={"capacity_w": 9000})
    _, classroom, _ = read_all()
    assert classroom["scanned_classroom_ids"] == ["CR1", "CR2"]
    assert classroom["safety"]["protected_served_w"] == 2100
    assert classroom["served_w"] <= classroom["effective_capacity_w"] < 8000


def test_slider_still_limits_below_campus_headroom():
    reply = client.post("/api/v1/visualizers/classrooms", json={"action": "set_capacity", "capacity_w": 3000}).json()
    assert reply["effective_capacity_w"] == 3000 and reply["limited_by"] == "classroom limit"
    assert reply["command"]["run_id"] == reply["site"]["run_id"]
    assert reply["command"]["applied_revision"] == reply["site"]["revision"]


def test_hospital_commands_share_the_site_revision_and_reads_never_bump_it():
    reply = client.post("/api/v1/visualizers/hospital", json={"action": "set_capacity", "capacity_w": 2000}).json()
    assert reply["site"]["revision"] == reply["command"]["applied_revision"]
    assert reply["transformers"][0]["diagnosis"]["status"] == "ALARM"
    main.site.tick()  # the control loop's next tick confirms the cause
    revision = read_all()[0]["site"]["revision"]
    assert revision > reply["site"]["revision"]
    for _ in range(50):
        for p in read_all():
            assert p["site"]["revision"] == revision
    hospital = read_all()[2]
    assert hospital["served_w"] <= 2000 and hospital["safety"]["status"] == "PROTECTED_SHORTFALL"


def test_headroom_is_zero_without_feeder_b_and_capped_by_its_limit():
    grid = main.site.grid
    assert classroom_headroom_w(grid) == 8000
    grid.set_feeder("B", False)
    assert classroom_headroom_w(grid) == 0
