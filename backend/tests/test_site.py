"""One site authority over campus, classroom and hospital (#3, first step)."""
from fastapi.testclient import TestClient
import time

import app.main as main
from conftest import session_request
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
        client.post("/api/v1/visualizers/classrooms", json=session_request(client, {"action": "scan", "classroom_id": cid}))
    client.post("/api/v1/simulation/capacity", json={"capacity_w": 9000})
    _, classroom, _ = read_all()
    assert classroom["scanned_classroom_ids"] == ["CR1", "CR2"]
    assert classroom["safety"]["protected_served_w"] == 2100
    assert classroom["served_w"] <= classroom["effective_capacity_w"] < 8000


def test_rfid_and_classroom_view_share_sessions_and_requested_loads():
    client.post("/api/v1/visualizers/classrooms", json={"action": "reset"})
    classroom = client.post("/api/v1/visualizers/classrooms", json=session_request(
        client, {"action": "scan", "classroom_id": "CR1"})).json()
    campus = client.get("/api/v1/snapshot").json()
    services = {item["id"]: item for item in campus["services"]}
    assert classroom["scanned_classroom_ids"] == ["CR1"]
    assert campus["zones"]["classroom"]["active_classroom_id"] == "CR1"
    sessions = {c["id"]: c["load_event_active"] for c in campus["zones"]["classroom"]["classrooms"]}
    assert sessions == {"CR1": True, "CR2": False, "CR3": False}

    client.post("/api/v1/rfid/scan", json=session_request(client, {"uid": "CARD_2_UID"}))
    classroom = client.get("/api/v1/visualizers/classrooms").json()
    assert classroom["scanned_classroom_ids"] == ["CR1", "CR2"]

    client.post("/api/v1/visualizers/classrooms", json=session_request(
        client, {"action": "unscan", "classroom_id": "CR1"}))
    campus = client.get("/api/v1/snapshot").json()
    classroom = client.get("/api/v1/visualizers/classrooms").json()
    services = {item["id"]: item for item in campus["services"]}
    assert classroom["scanned_classroom_ids"] == ["CR2"]
    assert campus["zones"]["classroom"]["active_classroom_id"] == "CR2"
    sessions = {c["id"]: c["load_event_active"] for c in campus["zones"]["classroom"]["classrooms"]}
    assert sessions == {"CR1": False, "CR2": True, "CR3": False}
    # Sessions rank rooms; the requested watts are the room's leaves on both routes (#33).
    assert services["L3"]["requested_w"] == services["L4"]["requested_w"] == 2000


def test_board_gateway_events_and_expiry_share_the_same_room_sessions():
    client.post("/api/v1/visualizers/classrooms", json={"action": "reset"})
    assert main.handle_gateway_event(main.app, "START_SESSION", "C")
    assert client.get("/api/v1/visualizers/classrooms").json()["scanned_classroom_ids"] == ["CR3"]
    assert main.handle_gateway_event(main.app, "START_SESSION", "B")
    grid = main.app.state.grid
    grid.active_sessions["CR3"]["last_scan"] = time.time() - 7201
    grid.expire_sessions()
    main.app.state.site.tick()
    assert client.get("/api/v1/visualizers/classrooms").json()["scanned_classroom_ids"] == ["CR2"]
    assert main.handle_gateway_event(main.app, "END_SESSION", "B")
    assert client.get("/api/v1/visualizers/classrooms").json()["scanned_classroom_ids"] == []


def test_slider_still_limits_below_campus_headroom():
    reply = client.post("/api/v1/visualizers/classrooms", json={"action": "set_capacity", "capacity_w": 3000}).json()
    assert reply["effective_capacity_w"] == 3000 and reply["limited_by"] == "classroom limit"
    assert reply["command"]["run_id"] == reply["site"]["run_id"]
    assert reply["command"]["applied_revision"] == reply["site"]["revision"]


def test_hospital_commands_share_the_site_revision_and_reads_never_bump_it():
    reply = client.post("/api/v1/visualizers/hospital", json={"action": "set_capacity", "capacity_w": 2000}).json()
    assert reply["site"]["revision"] == reply["command"]["applied_revision"]
    revision = reply["site"]["revision"]
    for _ in range(50):
        for p in read_all():
            assert p["site"]["revision"] == revision
    hospital = read_all()[2]
    assert hospital["served_w"] <= 2000 and hospital["safety"]["status"] == "PROTECTED_SHORTFALL"


def test_headroom_is_zero_without_feeder_b_and_capped_by_its_limit():
    site = main.app.state.site
    grid = site.grid
    assert classroom_headroom_w(grid, site.appliances) <= 8000
    grid.set_feeder("B", False)
    assert classroom_headroom_w(grid, site.appliances) == 0
    grid.set_feeder("B", True)


def test_hospital_leaves_reconcile_with_campus_feeder_a():
    from app.visualizers import HOSP_LOADS, HOSP_PARENT
    feeder_a = {s["id"]: s for s in SERVICE_CATALOG if s["feeder"] == "A"}
    for sid, svc in feeder_a.items():
        leaves = [item for z, rows in HOSP_LOADS.items() for item in rows if HOSP_PARENT[(z, item[0])] == sid]
        assert sum(item[2] for item in leaves) == svc["watts"]
        assert all(item[3] == (svc["tier"] == "T1") for item in leaves)
    campus, _, hospital = read_all()
    assert hospital["requested_w"] == sum(s["watts"] for s in campus["services"] if s["feeder"] == "A") == 6000


def test_feeder_a_trip_opens_the_hospital_view_in_the_same_revision():
    client.post("/api/v1/simulation/feeder", json={"feeder": "A", "available": False})
    campus, classroom, hospital = read_all()
    assert len({(p["site"]["run_id"], p["site"]["revision"]) for p in (campus, classroom, hospital)}) == 1
    assert hospital["campus_limit_w"] == 0 and hospital["served_w"] == 0
    assert hospital["limited_by"] == "campus feeder A"
    assert hospital["safety"]["status"] == "PROTECTED_SHORTFALL"
    assert hospital["edges"] and all(e["state"] == "OPEN" for e in hospital["edges"])


def test_campus_shortage_bounds_the_hospital_to_what_the_campus_served_on_feeder_a():
    client.post("/api/v1/simulation/capacity", json={"capacity_w": 4000})
    campus, _, hospital = read_all()
    served_a = sum(s["watts"] for s in campus["services"] if s["feeder"] == "A" and s["modeled_served"])
    assert hospital["campus_limit_w"] == served_a == hospital["effective_capacity_w"]
    assert hospital["served_w"] <= served_a
    assert hospital["safety"]["protected_served_w"] == 3000  # L0 + L1 essentials


def _rooms_by_service(classroom):
    parent = {"CR1": "L3", "CR2": "L4", "CR3": "L5"}
    return {parent[r["id"]]: (sum(x["watts"] for x in r["loads"]),
                              sum(x["watts"] for x in r["loads"] if x["served"])) for r in classroom["rooms"]}


def test_feeder_b_has_one_decision_with_partial_service_on_every_route():
    """Campus service watts are the appliance-level decision, not a second whole-service decision."""
    client.post("/api/v1/visualizers/classrooms", json={"action": "reset"})
    for capacity in (14000, 9000, 7000, 3500):
        client.post("/api/v1/simulation/capacity", json={"capacity_w": capacity})
        campus, classroom, hospital = read_all()
        services = {s["id"]: s for s in campus["services"]}
        rooms = _rooms_by_service(classroom)
        for sid, (requested, served) in rooms.items():
            assert (services[sid]["requested_w"], services[sid]["served_w"]) == (requested, served)
            assert services[sid]["modeled_served"] == (served > 0)
        # Leaves -> feeders -> source reconcile on every route.
        feeder = {e["to"]: e for e in campus["edges"] if e["from"] == "SRC"}
        assert feeder["B"]["served_w"] == classroom["served_w"] == sum(served for _, served in rooms.values())
        assert feeder["A"]["served_w"] == sum(s["served_w"] for s in campus["services"] if s["feeder"] == "A")
        assert hospital["served_w"] == feeder["A"]["served_w"]
        assert hospital["campus_limit_w"] == min(6000, capacity - classroom["served_w"])
        assert campus["allocation"]["served_w"] == feeder["A"]["served_w"] + feeder["B"]["served_w"] <= capacity
        assert campus["contract"]["campus_totals"]["served_w"] == campus["allocation"]["served_w"]
        assert campus["contract"]["zone_totals"]["classroom"]["served_w"] == classroom["served_w"]
    # At 7,000 W the classrooms get a partial budget: some room is energized but not fully served.
    client.post("/api/v1/simulation/capacity", json={"capacity_w": 7000})
    campus, classroom, _ = read_all()
    partial = [s for s in campus["services"] if s["feeder"] == "B" and 0 < s["served_w"] < s["requested_w"]]
    assert partial and all("Partly served" in s["model_reason"] for s in partial)
    decisions = {d["service_id"]: d for d in campus["allocation"]["explanation"]["decisions"]}
    assert all(decisions[s]["decided_by"] == "appliance_allocation" for s in ("L0", "L1", "L2", "L3", "L4", "L5"))


def test_named_scenario_switches_every_route_in_one_revision():
    """#33: teaching scenarios are named and switched by one explicit command."""
    listing = client.get("/api/v1/site/scenarios").json()
    assert listing["active"] == listing["site"]["scenario"] == "normal"
    assert {"normal", "source_shortage", "feeder_b_trip", "classroom_overload", "hospital_overload"} == {
        p["name"] for p in listing["scenarios"]}

    reply = client.post("/api/v1/site/scenario", json={"scenario": "source_shortage"}).json()
    assert reply["active"] == reply["site"]["scenario"] == "source_shortage"
    assert reply["command"]["applied_revision"] == reply["site"]["revision"]
    campus, classroom, hospital = read_all()
    assert {(p["site"]["revision"], p["site"]["scenario"]) for p in (campus, classroom, hospital)} == {
        (reply["site"]["revision"], "source_shortage")}
    assert campus["source"]["capacity_w"] == 6000 and campus["allocation"]["served_w"] <= 6000

    client.post("/api/v1/site/scenario", json={"scenario": "classroom_overload"})
    campus, classroom, hospital = read_all()
    assert campus["source"]["capacity_w"] == 14000  # every budget is set, not just the one that differs
    assert classroom["classroom_limit_w"] == 3400 and hospital["capacity_w"] == 6000

    client.post("/api/v1/site/scenario", json={"scenario": "feeder_b_trip"})
    campus, classroom, _ = read_all()
    assert classroom["served_w"] == 0 and classroom["classroom_limit_w"] == 8000
    assert all(s["served_w"] == 0 for s in campus["services"] if s["feeder"] == "B")

    # A hand-changed budget no longer matches the scenario, and says so.
    client.post("/api/v1/visualizers/classrooms", json={"action": "set_capacity", "capacity_w": 5000})
    assert client.get("/api/v1/snapshot").json()["site"]["scenario"] == "custom"
    client.post("/api/v1/site/scenario", json={"scenario": "normal"})
    campus, classroom, _ = read_all()
    assert campus["site"]["scenario"] == "normal" and classroom["classroom_limit_w"] == 8000
    assert campus["site"]["profile"] == "campus"  # the site profile (#26) is a separate, restart-only choice


def test_unknown_or_malformed_scenario_is_rejected_without_a_change():
    before = client.get("/api/v1/site/scenarios").json()["site"]["revision"]
    assert client.post("/api/v1/site/scenario", json={"scenario": "mains_power"}).status_code == 422
    assert client.post("/api/v1/site/scenario", json={"scenario": "normal", "extra": 1}).status_code == 422
    assert client.post("/api/v1/site/scenario", json={"scenario": 3}).status_code == 422
    assert client.get("/api/v1/site/scenarios").json()["site"]["revision"] == before
