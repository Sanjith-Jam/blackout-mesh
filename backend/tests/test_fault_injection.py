"""Hospital fault injection is persistent site state; diagnosis still reads only telemetry (A4)."""
import pytest
from fastapi.testclient import TestClient

import app.main as main

client = TestClient(main.app)
URL = "/api/v1/visualizers/hospital"


def tick(n=4):
    for _ in range(n):
        main.app.state.site.tick()
    return client.get(URL).json()


def tx(snapshot, asset):
    return next(t for t in snapshot["transformers"] if t["id"] == asset)


def test_injected_fault_persists_across_ticks_and_reads_until_cleared():
    reply = client.post(URL, json={"action": "inject_fault", "fault": "cooling_failure", "zone_id": "Theatre"}).json()
    assert reply["fault"] == {"kind": "cooling_failure", "zone_id": "Theatre", "asset_id": "TX2",
                              "provenance": "INJECTED_SIMULATION"}
    assert reply["command"]["name"] == "hospital.inject_fault"
    snap = tick()
    for _ in range(3):
        snap = tick(2)
        diagnosis = tx(snap, "TX2")["diagnosis"]
        assert diagnosis["status"] == "FAULT_DETECTED"
        assert "COOLING_FAILURE" in {h["code"] for h in diagnosis["hypotheses"]}
        assert tx(snap, "TX1")["diagnosis"]["status"] == "NORMAL"
    cleared = client.post(URL, json={"action": "clear_fault"}).json()
    assert cleared["fault"] is None
    assert tx(tick(), "TX2")["diagnosis"]["status"] == "NORMAL"


def test_overload_and_cooling_reports_both_hypotheses():
    client.post(URL, json={"action": "inject_fault", "fault": "overload_cooling", "zone_id": "ICU"})
    codes = {h["code"] for h in tx(tick(6), "TX1")["diagnosis"]["hypotheses"]}
    assert {"OVERLOAD", "COOLING_FAILURE"} <= codes


def test_sensor_dropout_abstains_instead_of_reporting_normal():
    client.post(URL, json={"action": "inject_fault", "fault": "sensor_dropout", "zone_id": "Wards"})
    diagnosis = tx(tick(), "TX3")["diagnosis"]
    assert diagnosis["status"] == "ABSTAINED" and "current_a" in diagnosis["missing"]


def test_upstream_loss_opens_every_hospital_wire_and_serves_nothing():
    client.post(URL, json={"action": "inject_fault", "fault": "upstream_loss"})
    snap = tick()
    assert snap["served_w"] == 0 and snap["effective_capacity_w"] == 0
    assert all(e["state"] == "OPEN" for e in snap["edges"])
    assert snap["safety"]["status"] == "PROTECTED_SHORTFALL"
    assert all(t["diagnosis"]["status"] != "NORMAL" for t in snap["transformers"])


def test_scenario_alias_is_persistent_and_reset_clears_the_fault():
    reply = client.post(URL, json={"scenario": "overload", "zone_id": "Theatre"}).json()
    assert reply["fault"]["kind"] == "overload"
    assert tx(tick(6), "TX2")["diagnosis"]["code"] == "OVERLOAD"
    assert client.post(URL, json={"scenario": "normal"}).json()["fault"] is None
    client.post(URL, json={"action": "inject_fault", "fault": "overload"})
    assert client.post(URL, json={"action": "reset"}).json()["fault"] is None


@pytest.mark.parametrize("body", [
    {"action": "inject_fault"},
    {"action": "scan", "zone_id": "ICU", "fault": "overload"},
    {"action": "inject_fault", "fault": "meltdown"},
    {"scenario": "overload", "action": "scan"},
])
def test_invalid_fault_requests_are_rejected(body):
    assert client.post(URL, json=body).status_code == 422


def test_stuck_current_sensor_abstains_and_stays_untrusted():
    tick(6)
    client.post(URL, json={"action": "inject_fault", "fault": "stuck_sensor", "zone_id": "Theatre"})
    for n in range(10):
        diagnosis = tx(tick(2), "TX2")["diagnosis"]
        assert diagnosis["status"] != "NORMAL", f"stuck sensor reported NORMAL after {2 * (n + 1)} ticks"
    assert diagnosis["status"] == "ABSTAINED"
    assert diagnosis["abstention"]["reason"] == "SUSPECTED_STUCK_SENSOR"
    # Healthy, noisy sensors on the other transformers are never flagged.
    assert all(tx(tick(), a)["diagnosis"]["status"] == "NORMAL" for a in ("TX1", "TX3"))
