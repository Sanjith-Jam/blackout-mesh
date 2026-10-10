"""Cross-route contract (#24): every route at one revision reports the same shared facts."""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from conftest import session_request

ROUTES = ("/api/v1/snapshot", "/api/v1/visualizers/classrooms", "/api/v1/visualizers/hospital")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def contracts(client):
    out = {route: client.get(route).json()["contract"] for route in ROUTES}
    with client.websocket_connect("/ws/live") as ws:
        out["/ws/live"] = json.loads(ws.receive_text())["payload"]["contract"]
    return out


def shared(contract):
    return {k: v for k, v in contract.items() if k != "view_totals"}


def assert_routes_agree(client):
    seen = contracts(client)
    first = shared(next(iter(seen.values())))
    for route, contract in seen.items():
        assert shared(contract) == first, route
    return seen


def test_all_routes_agree_on_identity_and_totals(client):
    seen = assert_routes_agree(client)
    contract = seen["/api/v1/snapshot"]
    assert contract["identity"]["run_id"] == client.get("/api/v1/snapshot").json()["site"]["run_id"]
    assert contract["campus_totals"]["scope"] == "campus"
    assert set(contract["zone_totals"]) == {"hospital", "classroom"}


def test_zone_totals_add_up_to_campus_totals(client):
    client.post("/api/v1/simulation/capacity", json={"capacity_w": 5000})
    contract = assert_routes_agree(client)["/api/v1/snapshot"]
    campus, zones = contract["campus_totals"], contract["zone_totals"].values()
    assert campus["unit"] == "W" and all(z["unit"] == "W" for z in zones)
    assert sum(z["requested_w"] for z in zones) == campus["requested_w"]
    assert sum(z["served_w"] for z in zones) == campus["served_w"]
    assert campus["served_w"] <= campus["capacity_w"]
    # Zones have no capacity of their own; unknown is null, never zero.
    assert all(z["capacity_w"] is None for z in zones)


def test_view_totals_are_scoped_to_their_route_and_match_its_numbers(client):
    seen = contracts(client)
    assert seen["/api/v1/snapshot"].get("view_totals") is None
    for route, scope in (("/api/v1/visualizers/classrooms", "view:classroom_demo"),
                         ("/api/v1/visualizers/hospital", "view:hospital_demo")):
        data = client.get(route).json()
        view = data["contract"]["view_totals"]
        assert view["scope"] == scope
        assert (view["capacity_w"], view["requested_w"], view["served_w"]) == (
            data["effective_capacity_w"], data["requested_w"], data["served_w"])


def test_commands_advance_every_route_to_the_same_revision(client):
    before = assert_routes_agree(client)["/api/v1/snapshot"]["identity"]["state_revision"]
    client.post("/api/v1/visualizers/classrooms", json=session_request(client, {"action": "scan", "classroom_id": "CR1"}))
    client.post("/api/v1/simulation/feeder", json={"feeder": "A", "available": False})
    after = assert_routes_agree(client)["/api/v1/snapshot"]
    assert after["identity"]["state_revision"] > before
    assert after["zone_totals"]["hospital"]["served_w"] == 0


def test_new_run_replaces_the_previous_run_on_every_route(client):
    old = assert_routes_agree(client)["/api/v1/snapshot"]["identity"]["run_id"]
    new = app.state.site.new_run()
    seen = assert_routes_agree(client)
    assert new != old
    assert {c["identity"]["run_id"] for c in seen.values()} == {new}
