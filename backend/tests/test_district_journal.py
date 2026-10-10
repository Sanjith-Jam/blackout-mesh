"""District audit: idempotent actions, atomic commits, restart rehydration, read-only playback."""
import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import district as district_api
from app.api.district import initialize_district
from app.district.journal import DistrictJournal


def post(client, snapshot, action, action_id=None, **extra):
    return client.post("/api/v1/district/action", json={"action_id": action_id or str(uuid.uuid4()),
        "run_id": snapshot["identity"]["run_id"], "expected_revision": snapshot["identity"]["revision"],
        "action": action, **extra})


def restart():
    holder = SimpleNamespace(state=SimpleNamespace())
    initialize_district(holder)
    return holder.state.district


def first_line(snapshot):
    return next(edge["id"] for edge in snapshot["topology"]["edges"] if edge["kind"] != "tie")


def test_duplicate_action_id_is_idempotent():
    from app.main import create_app
    with TestClient(create_app()) as client:
        start = client.get("/api/v1/district").json()
        first = post(client, start, "advance_hour", action_id="retry-0001")
        again = post(client, start, "advance_hour", action_id="retry-0001")
        assert first.status_code == again.status_code == 200
        assert again.json()["energy"]["hour"] == first.json()["energy"]["hour"] == (start["energy"]["hour"] + 1) % 24
        assert again.json()["identity"]["revision"] == start["identity"]["revision"] + 1
        records = client.get("/api/v1/district/history", params={"run_id": start["identity"]["run_id"]}).json()["items"]
        assert [r["record_id"] for r in records].count("retry-0001") == 1


def test_failed_commit_rolls_back_and_publishes_nothing(monkeypatch):
    from app.main import create_app
    with TestClient(create_app()) as client:
        start = client.get("/api/v1/district").json()
        monkeypatch.setattr(DistrictJournal, "commit", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
        failed = post(client, start, "inject_fault", component_id=first_line(start), fault_kind="line_open")
        assert failed.status_code == 503
        after = client.get("/api/v1/district").json()
        assert after["identity"]["revision"] == start["identity"]["revision"]
        assert after["state"]["faults"] == []
        monkeypatch.undo()
        # Crash before commit: a restart restores the last *committed* revision only.
        assert restart().faults == set()


def test_restart_restores_committed_state_with_new_run_and_stale_observations():
    from app.main import create_app
    with TestClient(create_app()) as client:
        snapshot = client.get("/api/v1/district").json()
        transformer = snapshot["state"]["transformers"][0]["component_id"]
        snapshot = post(client, snapshot, "inject_fault", component_id=first_line(snapshot), fault_kind="line_open").json()
        snapshot = post(client, snapshot, "transformer_scenario", component_id=transformer, fault_kind="overload").json()
        assert next(t for t in snapshot["state"]["transformers"] if t["component_id"] == transformer)["sensor"]["status"] == "SIMULATED"
        committed = snapshot["identity"]

    revived = restart()
    restored = revived.snapshot()
    assert restored["identity"]["revision"] == committed["revision"]
    assert restored["identity"]["run_id"] != committed["run_id"]
    assert restored["audit"]["rehydration"]["status"] == "RESTORED"
    assert restored["audit"]["rehydration"]["from_run_id"] == committed["run_id"]
    assert [f["component_id"] for f in restored["state"]["faults"]] == [first_line(snapshot)]
    sensor = next(t for t in restored["state"]["transformers"] if t["component_id"] == transformer)
    assert sensor["sensor"]["status"] == "STALE" and sensor["diagnosis"]["status"] == "UNKNOWN"
    assert restored["state"]["restoration"]["stable_evidence_count"] == 0
    assert not restored["state"]["restoration"]["evidence_ready"]
    # A second restart chains from the rehydration record, not the stale earlier run.
    assert restart().snapshot()["audit"]["rehydration"]["from_run_id"] == restored["identity"]["run_id"]


def test_old_run_cannot_command_after_restart():
    from app.main import create_app
    with TestClient(create_app()) as client:
        old = client.get("/api/v1/district").json()
        assert post(client, old, "advance_hour").status_code == 200
    with TestClient(create_app()) as client:
        live = client.get("/api/v1/district").json()
        assert live["identity"]["run_id"] != old["identity"]["run_id"]
        stale = client.post("/api/v1/district/action", json={"action_id": str(uuid.uuid4()), "run_id": old["identity"]["run_id"],
                                                             "expected_revision": live["identity"]["revision"], "action": "advance_hour"})
        assert stale.status_code == 409


def test_playback_is_read_only_and_records_hashes():
    from app.main import create_app
    with TestClient(create_app()) as client:
        snapshot = client.get("/api/v1/district").json()
        post(client, snapshot, "advance_hour")
        page = client.get("/api/v1/district/history", params={"run_id": snapshot["identity"]["run_id"]}).json()
        record = page["items"][-1]
        assert record["payload"]["action"]["action"] == "advance_hour"
        assert set(record["payload"]["state"]["hashes"]) == {"profile", "electrical", "topology"}
        assert "served_w" in record["payload"]["summary"]
        assert client.post("/api/v1/district/history", json={}).status_code == 405
        runs = client.get("/api/v1/district/history/runs").json()
        assert runs["current_run_id"] == snapshot["identity"]["run_id"]


def test_changed_profile_refuses_rehydration(monkeypatch):
    from app.main import create_app
    with TestClient(create_app()) as client:
        snapshot = client.get("/api/v1/district").json()
        post(client, snapshot, "advance_hour")
    monkeypatch.setenv("DISTRICT_PROFILE", str(district_api.Path(district_api.__file__).resolve().parents[1]
                                               / "district/data/gnitc_appliance_profile.json"))
    revived = restart()
    assert revived.rehydration["status"] == "REJECTED" and revived.revision == 1
