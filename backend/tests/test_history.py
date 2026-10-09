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
    from app.main import app, grid, site
    from app.storage.recorder import HistoryRecorder
    store = HistoryStore(tmp_path / "history.sqlite3")
    clock = [0.0]
    run_id = site.run_id
    recorder = HistoryRecorder(store, run_id, lambda: clock[0])
    monkeypatch.setattr(grid, "history", recorder)
    site.tick()
    for _ in range(10):
        site.tick()
    assert len(store.page("campus", run_id, kind="decision")["items"]) == 1
    assert len(store.page("campus", run_id, kind="telemetry")["items"]) == 1
    grid.set_capacity(6000)
    site.tick()
    clock[0] = 1
    site.tick()
    decisions = store.page("campus", run_id, kind="decision")["items"]
    event = store.page("campus", run_id, kind="event")["items"][0]
    assert event["record_id"] in decisions[-1]["payload"]["event_ids"]
    assert decisions[-1]["payload"]["trail"]["validated_ack"] is None
    assert decisions[-1]["payload"]["trail"]["command_identity"] is None
    before = (grid.control_revision, grid.last_allocation_mask, grid.replay_index, grid.tick_count, grid.published_revision)
    client = TestClient(app)
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
    from app.main import site, grid
    from app.storage.recorder import HistoryRecorder
    store = HistoryStore(tmp_path / "rotated.sqlite3")
    monkeypatch.setattr(site, "run_id", site.run_id)
    previous_run = site.run_id
    monkeypatch.setattr(grid, "history", HistoryRecorder(store, previous_run))
    site.tick()
    previous = store.page("campus", previous_run)
    current = site.new_run()
    site.tick()
    assert current != previous_run
    assert grid.history.run_id == current
    assert store.page("campus", previous_run) == previous
    assert store.page("campus", current)["items"][0]["payload"]["snapshot"]["site"]["run_id"] == current


def test_history_get_does_not_initialize_or_tick_the_live_controller(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app, site, grid
    monkeypatch.setattr(grid, "history", None)
    before = (grid.tick_count, site.revision, grid.published_revision)
    client = TestClient(app)
    assert client.get("/api/v1/history/runs").status_code == 503
    assert client.get("/api/v1/history/records?run_id=unknown").status_code == 503
    assert grid.history is None
    assert before == (grid.tick_count, site.revision, grid.published_revision)
