"""A fresh application state and in-memory audit store for each test."""
import pytest
from datetime import datetime, timezone
import uuid
import app.main as main


def session_request(client, payload):
    run_id = client.get("/api/v1/snapshot").json()["site"]["run_id"]
    return {**payload, "run_id": run_id, "event_id": str(uuid.uuid4()),
            "observed_at": datetime.now(timezone.utc).isoformat()}


@pytest.fixture(autouse=True)
def default_site(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("PRIORITYGRID_HISTORY_DB", str(tmp_path / "history.sqlite3"))
    initialize = main.initialize_state
    initialize(main.app)
    # Legacy route tests construct multiple clients for the same prepared application.
    monkeypatch.setattr(main, "initialize_state", lambda app: None if app is main.app else initialize(app))
    dispose = main.app.state.grid.storage.engine.dispose
    history_engine = main.app.state.grid.history.store.engine
    monkeypatch.setattr(main.app.state.grid.storage.engine, "dispose", lambda: None)
    yield
    dispose()
    history_engine.dispose()
