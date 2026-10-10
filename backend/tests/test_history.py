from app.storage.history import HistoryStore
STAMP = "2026-10-10T00:00:00.000000Z"

def test_pagination_duplicates_equal_timestamps_restart(tmp_path):
    path = tmp_path / "history.sqlite3"
    store = HistoryStore(path)
    for n in range(5):
        store.append("campus", "run", "event", str(n), STAMP, n, {"n": n})
    store.append("campus", "run", "event", "0", STAMP, 0, {"n": 99})
    page = store.page("campus", "run", limit=2)
    assert [r["payload"]["n"] for r in page["items"]] == [0, 1]
    next_page = HistoryStore(path).page("campus", "run", after=page["next_cursor"], limit=3)
    assert [r["payload"]["n"] for r in next_page["items"]] == [2, 3, 4]
    assert next_page["next_cursor"] is None
    assert store.page("other", "run")["items"] == []
    assert store.page("campus", "run", start=STAMP, end=STAMP)["items"] == page["items"] + next_page["items"]

def test_retention_gap_and_monotonic_ids(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    old = store.append("campus", "run", "telemetry", "old", "2020-01-01T00:00:00.000000Z", 0, {})
    store.append("campus", "run", "decision", "keep", STAMP, 1, {})
    assert store.prune("2021-01-01T00:00:00.000000Z") == 1
    page = store.page("campus", "run", after=old)
    assert page["retention_gap"] is True
    assert page["items"][0]["record_id"] == "keep"
    assert store.append("campus", "run", "event", "new", STAMP, 2, {}) > old

def test_readonly_replay_is_persisted_not_recomputed(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    evidence = {"snapshot": {"modeled_mask": 3, "indicator_confirmed_mask": None},
                "inputs": {"capacity_w": 3000}, "policy": "test"}
    store.append("campus", "run", "decision", "decision", STAMP, 1, evidence)
    first = store.page("campus", "run", kind="decision")
    assert first == HistoryStore(tmp_path / "history.sqlite3").page("campus", "run", kind="decision")
    assert first["items"][0]["payload"] == evidence


def test_recording_is_sampled_and_readonly_api_does_not_advance_grid(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import time
    from app.main import create_app
    monkeypatch.setenv("PRIORITYGRID_HISTORY_DB", str(tmp_path / "api.sqlite3"))
    application = create_app()
    with TestClient(application) as client:
        grid, site = application.state.grid, application.state.site
        store = grid.history.store
        run_id = site.run_id
        clock = [time.monotonic()]
        grid.history.clock = lambda: clock[0]
        site.tick()
        for _ in range(10):
            site.tick()
        assert len(store.page("campus", run_id, kind="decision")["items"]) == 1
        assert len(store.page("campus", run_id, kind="telemetry")["items"]) == 1
        clock[0] += 1
        assert client.post("/api/v1/simulation/capacity", json={"capacity_w": 6000}).status_code == 200
        decisions = store.page("campus", run_id, kind="decision")["items"]
        event = store.page("campus", run_id, kind="event")["items"][0]
        assert event["record_id"] in decisions[-1]["payload"]["event_ids"]
        trail = decisions[-1]["payload"]["trail"]
        assert trail["validated_ack"] is None
        assert trail["command_identity"]["action"] == "campus.capacity"
        assert trail["command_identity"]["command_id"]
        from app.storage.models import Command
        from sqlmodel import Session, select
        with Session(grid.storage.engine) as audit:
            command = audit.exec(select(Command).where(
                Command.command_id == trail["command_identity"]["command_id"])).one()
            assert command.action == "campus.capacity"
        before = (grid.control_revision, grid.last_allocation_mask, grid.replay_index, grid.tick_count, grid.published_revision)
        url = f"/api/v1/history/records?run_id={run_id}&kind=decision&limit=1"
        assert client.get("/api/v1/history/runs").json()["current_run_id"] == run_id
        assert decisions[-1]["payload"]["snapshot"]["site"]["run_id"] == run_id
        rows_before = store.page("campus", run_id)
        first = client.get(url).json()
        assert client.get(url).json() == first
        assert store.page("campus", run_id) == rows_before
        assert before == (grid.control_revision, grid.last_allocation_mask, grid.replay_index, grid.tick_count, grid.published_revision)
        assert client.get(url + "&start=2026-10-10T00:00:00").status_code == 422
        assert client.get(url + "&after=-1").status_code == 422
        assert client.get(url + "&site_id=invalid").status_code == 422


def test_session_commands_never_persist_raw_card_uid(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.storage.models import Command
    from sqlmodel import Session, select
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'uid.db'}")
    with TestClient(create_app()) as client:
        app = client.app
        assert client.post("/api/v1/rfid/scan", json={"uid": "CARD_1_UID"}).status_code == 200
        with Session(app.state.grid.storage.engine) as session:
            payloads = " ".join(str(row.payload) for row in session.exec(select(Command)).all())
        assert "CARD_1_UID" not in payloads


def test_public_history_fixture_and_restart_run_identity(tmp_path):
    import json
    from pathlib import Path
    from app.storage.recorder import HistoryRecorder
    fixture = json.loads((Path(__file__).resolve().parents[2] / "contracts/schema_examples/history_v1.json").read_text(encoding="utf-8"))
    row = fixture["items"][0]
    path = tmp_path / "restart.sqlite3"
    store = HistoryStore(path)
    assert store.append(row["site_id"], row["run_id"], row["kind"], row["record_id"], row["timestamp"], row["revision"], row["payload"]) == row["seq"]
    assert store.page("campus", "example-run") == fixture
    previous = HistoryRecorder(store)
    restarted = HistoryRecorder(HistoryStore(path))
    assert restarted.run_id != previous.run_id
    assert restarted.store.page("campus", "example-run") == fixture

def test_new_site_run_rotates_history_and_keeps_previous_evidence(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app
    monkeypatch.setenv("PRIORITYGRID_HISTORY_DB", str(tmp_path / "rotated.sqlite3"))
    with TestClient(create_app()) as client:
        app = client.app
        site, grid = app.state.site, app.state.grid
        previous_run = site.run_id
        previous = grid.history.store.page("campus", previous_run)
        current = site.new_run()
        site.tick()
        assert current != previous_run
        assert grid.run_id == current
        from app.storage.models import Run
        from sqlmodel import Session, select
        with Session(grid.storage.engine) as audit:
            assert audit.exec(select(Run).where(Run.run_id == current)).first()
        assert grid.history.run_id == current
        assert grid.history.store.page("campus", previous_run) == previous
        assert grid.history.store.page("campus", current)["items"][0]["payload"]["snapshot"]["site"]["run_id"] == current


def test_history_get_does_not_initialize_or_tick_the_live_controller(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    client = TestClient(app)
    assert client.get("/api/v1/history/runs").status_code == 503
    assert client.get("/api/v1/history/records?run_id=unknown").status_code == 503

def test_incident_open_and_resolve_are_replayable_timeline_events(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.storage.models import Incident
    from sqlmodel import Session, select
    monkeypatch.setenv("PRIORITYGRID_HISTORY_DB", str(tmp_path / "incidents.sqlite3"))
    with TestClient(create_app()) as client:
        app = client.app
        grid = app.state.grid
        hypothesis = {"code": "COOLING_FAILURE", "asset_id": "TX2", "severity": "high",
                      "evidence_score": 0.8, "supporting_evidence": ["cooling unavailable"]}
        grid._sync_incidents([hypothesis])
        grid._sync_incidents([hypothesis])
        grid._sync_incidents([])
        with Session(grid.storage.engine) as session:
            incident = session.exec(select(Incident).where(Incident.run_id == grid.run_id)).one()
            assert incident.status == "RESOLVED"
        history = grid.history.store.page("campus", grid.history.run_id, kind="event")
        assert [row["payload"]["event"]["type"] for row in history["items"]].count("INCIDENT_OPENED") == 1
        assert [row["payload"]["event"]["type"] for row in history["items"]].count("INCIDENT_RESOLVED") == 1
