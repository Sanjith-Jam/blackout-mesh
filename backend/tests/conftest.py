"""A fresh application state and in-memory audit store for each test."""
import pytest
import app.main as main


@pytest.fixture(autouse=True)
def default_site(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    initialize = main.initialize_state
    initialize(main.app)
    # Legacy route tests construct multiple clients for the same prepared application.
    monkeypatch.setattr(main, "initialize_state", lambda app: None if app is main.app else initialize(app))
    dispose = main.app.state.grid.storage.engine.dispose
    monkeypatch.setattr(main.app.state.grid.storage.engine, "dispose", lambda: None)
    yield
    dispose()
