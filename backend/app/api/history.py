import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from app.storage.history import HistoryStore
from app.storage.recorder import HistoryRecorder, utc

router = APIRouter(prefix="/api/v1/history", tags=["read-only history"])

def attach_history(grid, run_id):
    if grid.history is None:
        path = Path(os.environ.get("PRIORITYGRID_HISTORY_DB", str(Path(__file__).resolve().parents[2] / "history.sqlite3")))
        store = HistoryStore(path)
        store.prune(utc(datetime.now(timezone.utc) - timedelta(days=30)))
        grid.history = HistoryRecorder(store, run_id)
    return grid.history

def register_history(site_provider):
    def recorder():
        history = site_provider().grid.history
        if history is None:
            raise HTTPException(503, "History not initialized; start the application lifespan")
        return history

    @router.get("/runs")
    def runs(site_id: Literal["campus"] = "campus"):
        history = recorder()
        return {"current_run_id": site_provider().run_id, "runs": history.store.runs(site_id)}

    @router.get("/records")
    def records(run_id: str = Query(min_length=1, max_length=100),
                site_id: Literal["campus"] = "campus",
                kind: Literal["event", "decision", "telemetry"] | None = None,
                after: int = Query(default=0, ge=0), limit: int = Query(default=200, ge=1, le=1000),
                start: datetime | None = None, end: datetime | None = None):
        if any(value and value.tzinfo is None for value in (start, end)):
            raise HTTPException(422, "History timestamps require a UTC offset")
        if start and end and start > end:
            raise HTTPException(422, "start must not exceed end")
        return recorder().store.page(
            site_id, run_id, after=after, limit=limit, kind=kind,
            start=utc(start) if start else None, end=utc(end) if end else None)
    return router

