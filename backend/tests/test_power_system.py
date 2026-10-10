"""The appliance-level decision end to end: Fault Lab commands -> state -> diagnosis -> CP-SAT ->
validation -> restoration -> projections. Every route must describe the same decision."""
from fastapi.testclient import TestClient

import app.main as main
from app.core import appliances as cat
from app.core.appliance_control import ApplianceController

client = TestClient(main.app)


def fake_clock():
    now = [0.0]
    main.app.state.site.appliances = ApplianceController(lambda: now[0])
    main.app.state.site.tick()
    return now


def advance(now, seconds, step=0.25):
    end = now[0] + seconds
    while now[0] < end:
        now[0] += step
        main.app.state.site.tick()


def ps():
    return client.get("/api/v1/power-system").json()


def states(data):
    return {a["id"]: a["state"] for a in data["appliances"]}


def assert_views_agree(data):
    campus = client.get("/api/v1/snapshot").json()
    hospital = client.get("/api/v1/visualizers/hospital").json()
    classroom = client.get("/api/v1/visualizers/classrooms").json()
    served = {a["id"] for a in data["appliances"] if a["served"]}
    hosp_served = {f"{t['zone']}.{load['id']}" for t in hospital["transformers"] for load in t["loads"] if load["served"]}
    class_served = {f"{r['id']}.{load['id']}" for r in classroom["rooms"] for load in r["loads"] if load["served"]}
    assert hosp_served | class_served == served
    assert campus["allocation"]["served_w"] == data["source"]["served_w"] == sum(a["served_w"] for a in data["appliances"])
    for svc in campus["services"]:
        assert svc["served_w"] == sum(a["served_w"] for a in data["appliances"] if a["service_id"] == svc["id"])
    assert data["optimizer"]["validated"] and data["optimizer"]["status"] == "OPTIMAL"
    # Served never exceeds any configured limit.
    assert data["source"]["served_w"] <= data["source"]["capacity_w"]
    for f in data["feeders"]:
        assert f["served_w"] <= (f["limit_w"] if f["available"] else 0)


def test_projection_lists_every_appliance_with_identity_and_configured_topology():
    data = ps()
    assert len(data["appliances"]) == len(cat.APPLIANCES) == 31
    assert {r["id"] for r in data["rooms"]} == {"ICU", "Theatre", "Wards", "CR1", "CR2", "CR3"}
    edge_ids = {e["id"] for e in data["edges"]}
    assert edge_ids == {e["id"] for e in cat.edges()}
    for a in data["appliances"]:
        assert a["provenance"] == "CONFIGURED_SIMULATED_ASSUMPTION" and a["demand_w"] > 0
        assert all(f"{s}>{d}" in edge_ids for s, d in zip(a["path"], a["path"][1:]))
    assert all(a["state"] == "SERVED" for a in data["appliances"])
    assert data["diagnosis"]["overall"] == "NORMAL"
    assert_views_agree(data)


def test_overload_keeps_essentials_and_sheds_optional_equipment_in_the_same_room():
    fake_clock()
    client.post("/api/v1/simulation/capacity", json={"capacity_w": 6000})
    data = ps()
    s = states(data)
    # Protected demand is 5,100 W. The 900 W left goes to hospital support equipment; of the 900 W
    # combinations, fans + water pump needs fewer switches than the Theatre climate unit.
    support = [a for a in data["appliances"] if a["priority_class"] == "hospital_support" and a["served"]]
    assert sum(a["demand_w"] for a in support) == 900
    # Wards: critical bed lights and nurse call stay on while its AC is shed on its own.
    assert s["Wards.bed_lights"] == s["Wards.nurse_call"] == s["Wards.fans"] == s["Wards.water_pump"] == "SERVED"
    assert s["Wards.ac"] == s["Theatre.ac"] == "SHED"
    assert all(s[a.id] == "SERVED" for a in cat.APPLIANCES if a.zone == "hospital" and a.essential)
    assert all(s[a.id] == "SERVED" for a in cat.APPLIANCES if a.zone == "classroom" and a.essential)
    assert data["source"]["served_w"] == 6000  # the optimizer uses the full capacity, appliance by appliance
    shed = [a for a in data["appliances"] if a["state"] == "SHED"]
    assert shed and all(a["reason_code"].startswith("SHED_") and "W left" in a["reason"] for a in shed)
    source_check = next(c for c in data["constraint_checks"] if c["id"] == "source")
    assert source_check["exceeded"] and source_check["deficit_w"] == 8000 and source_check["requested_w"] == 14000
    assert data["diagnosis"]["overall"] == "CONSTRAINT_ACTIVE"
    assert data["diagnosis"]["campus"]["status"] == "NORMAL"  # capacity is a constraint, not fault evidence
    assert [f["kind"] for f in data["faults"]] == ["CAPACITY_REDUCED"]
    assert_views_agree(data)


def test_feeder_outage_marks_only_downstream_unreachable_then_recovers_in_stages():
    now = fake_clock()
    before = ps()
    client.post("/api/v1/simulation/feeder", json={"feeder": "A", "available": False})
    advance(now, 1.0)
    data = ps()
    s = states(data)
    assert all(s[a.id] == "UNREACHABLE" for a in cat.APPLIANCES if a.feeder == "A")
    assert all(s[a.id] == "SERVED" for a in cat.APPLIANCES if a.feeder == "B")  # unrelated loads untouched
    assert all(a["reason_code"] == "FEEDER_OPEN" for a in data["appliances"] if a["feeder"] == "A")
    assert {e["state"] for e in data["edges"] if "A" in (e["from_node"], e["to_node"]) or e["to_node"] in ("TX1", "TX2", "TX3")} == {"OPEN"}
    hyp = data["diagnosis"]["campus"]["hypotheses"]
    assert data["diagnosis"]["overall"] == "FAULT_DETECTED"
    assert [(h["code"], h["asset_id"]) for h in hyp] == [("FEEDER_DISCONNECTED", "FEEDER_A")]
    assert "voltage" in hyp[0]["supporting_evidence"][0]  # cites telemetry, not the switch state
    assert any(e["type"] == "FEEDER_CHANGE" for e in data["events"])
    assert any(e["appliance_id"] == "ICU.ventilator" and e["to"] == "UNREACHABLE" and e["command"] == "campus.feeder"
               for e in data["appliance_events"])
    assert_views_agree(data)

    client.post("/api/v1/simulation/feeder", json={"feeder": "A", "available": True})
    advance(now, 0.5)
    s = states(ps())
    assert all(s[a.id] == "PENDING_RESTORATION" for a in cat.APPLIANCES if a.feeder == "A")  # gate holds
    advance(now, 4.0)
    assert states(ps())["ICU.ventilator"] == "PENDING_RESTORATION"
    advance(now, 1.5)
    s = states(ps())
    restored = [a for a in cat.APPLIANCES if a.feeder == "A" and s[a.id] == "SERVED"]
    assert restored and all(a.essential for a in restored)  # highest priority group first
    advance(now, 6.0)
    after = ps()
    assert states(after) == states(before)
    assert after["diagnosis"]["overall"] == "NORMAL"
    assert_views_agree(after)


def test_coexisting_outage_and_overload_neither_clears_the_other():
    now = fake_clock()
    client.post("/api/v1/simulation/feeder", json={"feeder": "A", "available": False})
    client.post("/api/v1/simulation/capacity", json={"capacity_w": 5000})
    advance(now, 1.0)
    data = ps()
    assert {f["kind"] for f in data["faults"]} == {"FEEDER_OPEN", "CAPACITY_REDUCED"}
    s = states(data)
    assert all(s[a.id] == "UNREACHABLE" for a in cat.APPLIANCES if a.feeder == "A")
    assert data["feeders"][1]["served_w"] == 5000
    client.post("/api/v1/simulation/capacity", json={"capacity_w": 14000})  # restore capacity only
    advance(now, 1.0)
    data = ps()
    assert [f["kind"] for f in data["faults"]] == ["FEEDER_OPEN"]
    assert all(a["state"] == "UNREACHABLE" for a in data["appliances"] if a["feeder"] == "A")
    assert data["diagnosis"]["overall"] == "FAULT_DETECTED"
    assert_views_agree(data)


def test_requesting_one_appliance_off_changes_only_that_decision():
    fake_clock()
    client.post("/api/v1/simulation/capacity", json={"capacity_w": 9000})
    before = states(ps())
    reply = client.post("/api/v1/appliances/request", json={"appliance_id": "CR3.instruments", "requested": False})
    assert reply.status_code == 200 and reply.json()["accepted"]
    data = ps()
    s = states(data)
    assert s["CR3.instruments"] == "NOT_REQUESTED"
    assert data["source"]["requested_w"] == 12000
    assert sum(a["served_w"] for a in data["appliances"]) <= 9000
    assert all(s[k] == v or v == "SHED" for k, v in before.items() if k != "CR3.instruments")
    assert client.post("/api/v1/appliances/request", json={"appliance_id": "nope", "requested": True}).status_code == 422
    assert_views_agree(data)


def test_missing_or_insufficient_diagnosis_is_never_reported_as_normal():
    main.app.state.site.grid.campus_diagnosis = None
    data = client.get("/api/v1/power-system").json()
    assert data["diagnosis"]["campus"]["status"] == "UNKNOWN"
    assert data["diagnosis"]["overall"] == "INCONCLUSIVE"
    main.app.state.site.tick()
    client.post("/api/v1/visualizers/hospital", json={"action": "inject_fault", "fault": "sensor_dropout", "zone_id": "ICU"})
    for _ in range(4):
        main.app.state.site.tick()
    data = ps()
    icu = next(r for r in data["rooms"] if r["id"] == "ICU")
    assert icu["evidence_status"] == "INCONCLUSIVE"
    assert data["diagnosis"]["overall"] in ("INCONCLUSIVE", "SUSPECTED", "FAULT_DETECTED")
    assert data["diagnosis"]["overall"] != "NORMAL"


def test_indicators_summarize_rooms_and_are_unconfirmed_without_hardware():
    data = ps()
    assert [i["led_bit"] for i in data["indicators"]] == [0, 1, 2, 3, 4, 5]
    assert all(i["confirmed"] is None for i in data["indicators"])
    assert data["hardware_link"] == "NOT_CONFIGURED"
    assert "does not prove" in data["boundary"]


def test_facility_full_supply_and_reset_close_their_feeder_and_restore_the_source():
    """Rayna's report: after feeder A was opened elsewhere, /hospital Full supply stayed at 0 W forever."""
    now = fake_clock()
    client.post("/api/v1/simulation/feeder", json={"feeder": "A", "available": False})
    client.post("/api/v1/simulation/capacity", json={"capacity_w": 6000})
    advance(now, 1.0)
    assert client.get("/api/v1/visualizers/hospital").json()["effective_capacity_w"] == 0

    client.post("/api/v1/visualizers/hospital", json={"action": "normal"})
    advance(now, 15.0)
    data = ps()
    assert data["feeders"][0]["available"] and data["source"]["capacity_w"] == data["source"]["normal_capacity_w"]
    assert all(a["state"] == "SERVED" for a in data["appliances"] if a["zone"] == "hospital")
    hospital = client.get("/api/v1/visualizers/hospital").json()
    assert hospital["served_w"] == hospital["capacity_w"] == 6000
    assert_views_agree(data)

    # Overload then sheds per policy: essentials stay on, optional equipment goes.
    client.post("/api/v1/visualizers/hospital", json={"action": "overload"})
    advance(now, 1.0)
    data = ps()
    hosp = [a for a in data["appliances"] if a["zone"] == "hospital"]
    assert all(a["state"] == "SERVED" for a in hosp if a["protected"])
    assert any(a["state"] == "SHED" and a["reason_code"] == "SHED_ZONE_BUDGET" for a in hosp)
    assert sum(a["served_w"] for a in hosp) <= client.get("/api/v1/visualizers/hospital").json()["capacity_w"]

    # The classroom page's Reset closes feeder B the same way.
    client.post("/api/v1/simulation/feeder", json={"feeder": "B", "available": False})
    client.post("/api/v1/visualizers/classrooms", json={"action": "reset"})
    advance(now, 15.0)
    assert all(f["available"] for f in ps()["feeders"])
    client.post("/api/v1/site/scenario", json={"scenario": "normal"})
