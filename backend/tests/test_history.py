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

